from __future__ import annotations

from datetime import date
import hmac
import os

import pandas as pd
import streamlit as st

from proposal_app.ai import ProposalAI
from proposal_app.config import (
    DEFAULT_DRAFT_MODEL,
    DEFAULT_EXTRACTION_MODEL,
    KNOWLEDGE_INDEX,
    RULES_PATH,
)
from proposal_app.costs import (
    as_number,
    merge_standard_cost_items,
    normalize_cost_items,
    standard_cost_items,
)
from proposal_app.document_builder import build_docx
from proposal_app.file_ingest import UploadedDocument
from proposal_app.github_library import (
    GitHubLibrary,
    add_final_to_library,
    approve_rules,
    empty_state,
    sync_runtime_knowledge,
)
from proposal_app.knowledge import choose_template, load_index, retrieve_references
from proposal_app.investigation import (
    format_investigation_program,
    infer_methods_from_cost_items,
    legacy_program,
    parse_investigation_program,
)
from proposal_app.models import CostLineItem, ProposalFacts, RevisionAnalysis
from proposal_app.pdf_builder import build_pdf_package
from proposal_app.revision_learning import (
    aggregate_rule_candidates,
    compare_docx,
    proposal_index_record,
    revision_record,
)
from proposal_app.secure_bundle import ensure_private_assets, is_public_deployment
from proposal_app.validation import validate_facts


st.set_page_config(
    page_title="Almor Proposal Builder",
    page_icon="📄",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .block-container { max-width: 980px; padding-top: 2rem; padding-bottom: 4rem; }
    .small-note { color: #667085; font-size: 0.9rem; }
    div[data-testid="stDownloadButton"] button { width: 100%; }
    </style>
    """,
    unsafe_allow_html=True,
)


def secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, os.environ.get(name, default)))
    except FileNotFoundError:
        return os.environ.get(name, default)


def require_public_access_code() -> None:
    if not is_public_deployment():
        return
    configured_code = secret("APP_ACCESS_CODE")
    if not configured_code:
        st.error("APP_ACCESS_CODE is not configured in Streamlit Secrets.")
        st.stop()
    if st.session_state.get("access_granted"):
        return

    st.title("Almor Proposal Builder")
    entered_code = st.text_input("Access code", type="password")
    if st.button("Open Proposal Builder", type="primary", width="stretch"):
        if hmac.compare_digest(entered_code, configured_code):
            st.session_state.access_granted = True
            st.rerun()
        else:
            st.error("Incorrect access code.")
    st.stop()


require_public_access_code()

try:
    ensure_private_assets(secret("DATA_ENCRYPTION_KEY"))
except (FileNotFoundError, ValueError) as exc:
    st.error(str(exc))
    st.stop()


def api_client() -> ProposalAI:
    api_key = secret("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY is not configured. Add it in the Streamlit app's Secrets settings."
        )
    legacy_model = secret("OPENAI_MODEL")
    return ProposalAI(
        api_key=api_key,
        extraction_model=secret("OPENAI_EXTRACTION_MODEL", DEFAULT_EXTRACTION_MODEL),
        draft_model=secret("OPENAI_DRAFT_MODEL", legacy_model or DEFAULT_DRAFT_MODEL),
    )


@st.cache_resource
def cached_library_client(token: str, repository: str, branch: str) -> GitHubLibrary:
    return GitHubLibrary(token=token, repository=repository, branch=branch)


def library_client() -> GitHubLibrary | None:
    token = secret("GITHUB_LIBRARY_TOKEN")
    repository = secret("GITHUB_LIBRARY_REPO", "Steven352/proposal")
    branch = secret("GITHUB_LIBRARY_BRANCH", "main")
    if not token:
        return None
    return cached_library_client(token, repository, branch)


library = library_client()
if library and not st.session_state.get("library_synced"):
    try:
        sync_runtime_knowledge(library)
        load_index.cache_clear()
        st.session_state.library_synced = True
    except Exception as error:
        st.session_state.library_sync_error = str(error)


def uploaded_documents(files) -> list[UploadedDocument]:
    return [
        UploadedDocument(file.name, file.getvalue(), file.type or "")
        for file in (files or [])
    ]


def initial_facts(proposal_number: str) -> ProposalFacts:
    return ProposalFacts(
        proposal_number=proposal_number.strip(),
        proposal_date=date.today().isoformat(),
        cost_items=standard_cost_items(),
    )


def prepare_extracted_facts(facts: ProposalFacts) -> ProposalFacts:
    """Keep project extraction, while leaving scope quantities and pricing for manual entry."""
    return facts.model_copy(
        update={
            "proposal_date": facts.proposal_date or date.today().isoformat(),
            "borehole_program": [],
            "test_pit_program": [],
            "borehole_quantity": None,
            "borehole_depth_m": None,
            "test_pit_quantity": None,
            "test_pit_depth_m": None,
            "cost_items": standard_cost_items(),
        }
    )


def cost_dataframe(facts: ProposalFacts) -> pd.DataFrame:
    rows = []
    for item in facts.cost_items:
        estimate = as_number(item.estimate)
        rate = as_number(item.rate)
        total = estimate * rate if estimate is not None and rate is not None else None
        rows.append(
            {
                "Section": item.section,
                "Item": item.item,
                "Description": item.description,
                "Unit": item.unit,
                "Est.": estimate,
                "Rate": rate,
                "Total": total,
            }
        )
    return pd.DataFrame(
        rows,
        columns=["Section", "Item", "Description", "Unit", "Est.", "Rate", "Total"],
    )


SCOPE_CATEGORIES = [
    "Requested service",
    "Laboratory test",
    "Reporting requirement",
    "Access note",
    "Utility locate note",
    "Groundwater note",
]


def scope_dataframe(facts: ProposalFacts) -> pd.DataFrame:
    grouped = {
        "Requested service": facts.requested_services,
        "Laboratory test": facts.laboratory_tests,
        "Reporting requirement": facts.reporting_requirements,
        "Access note": [facts.access_notes] if facts.access_notes else [],
        "Utility locate note": [facts.utility_locate_notes] if facts.utility_locate_notes else [],
        "Groundwater note": [facts.groundwater_notes] if facts.groundwater_notes else [],
    }
    rows = []
    for category in SCOPE_CATEGORIES:
        values = grouped[category] or [""]
        rows.extend({"Category": category, "Value": value} for value in values)
    return pd.DataFrame(rows, columns=["Category", "Value"])


def scope_values(frame: pd.DataFrame) -> dict[str, list[str]]:
    values = {category: [] for category in SCOPE_CATEGORIES}
    for row in frame.fillna("").to_dict(orient="records"):
        category = str(row.get("Category", "")).strip()
        value = str(row.get("Value", "")).strip()
        if category in values and value:
            values[category].append(value)
    return values


def dataframe_costs(frame: pd.DataFrame) -> list[CostLineItem]:
    items: list[CostLineItem] = []
    for row in frame.fillna("").to_dict(orient="records"):
        if not any(str(value).strip() for value in row.values()):
            continue
        estimate = as_number(row.get("Est."))
        rate = as_number(row.get("Rate"))
        total = estimate * rate if estimate is not None and rate is not None else None
        items.append(
            CostLineItem(
                section=str(row.get("Section", "")),
                item=str(row.get("Item", "")),
                description=str(row.get("Description", "")),
                unit=str(row.get("Unit", "")),
                estimate=estimate,
                rate=rate,
                total=total,
            )
        )
    return items


def recalculate_cost_frame(frame: pd.DataFrame) -> pd.DataFrame:
    updated = frame.copy()
    updated["Total"] = [
        (as_number(estimate) or 0.0) * (as_number(rate) or 0.0)
        for estimate, rate in zip(updated["Est."], updated["Rate"], strict=True)
    ]
    return updated


def facts_from_editor(
    current: ProposalFacts,
    edited_costs: pd.DataFrame,
    edited_scope: pd.DataFrame,
) -> ProposalFacts:
    borehole_program, borehole_errors = parse_investigation_program(
        st.session_state.edit_borehole_program,
        "borehole",
    )
    test_pit_program, test_pit_errors = parse_investigation_program(
        st.session_state.edit_test_pit_program,
        "test pit",
    )
    st.session_state.scope_program_errors = borehole_errors + test_pit_errors
    cost_items = dataframe_costs(edited_costs)
    scope = scope_values(edited_scope)
    methods = set(st.session_state.edit_methods)
    if borehole_program:
        methods.add("drilling")
    if test_pit_program:
        methods.add("test pits")
    methods.update(infer_methods_from_cost_items(cost_items))
    return ProposalFacts(
        proposal_number=st.session_state.edit_proposal_number.strip(),
        proposal_date=st.session_state.edit_proposal_date.isoformat(),
        client_name=st.session_state.edit_client_name.strip(),
        client_address=st.session_state.edit_client_address.strip(),
        contact_name=st.session_state.edit_contact_name.strip(),
        contact_title=st.session_state.edit_contact_title.strip(),
        contact_email=st.session_state.edit_contact_email.strip(),
        client_reference_number=st.session_state.edit_client_reference.strip(),
        project_name=st.session_state.edit_project_name.strip(),
        project_location=st.session_state.edit_project_location.strip(),
        development_description=st.session_state.edit_development_description.strip(),
        project_type=st.session_state.edit_project_type.strip(),
        requested_services=scope["Requested service"],
        investigation_methods=sorted(methods),
        borehole_program=borehole_program,
        test_pit_program=test_pit_program,
        borehole_quantity=borehole_program[0].quantity if len(borehole_program) == 1 else None,
        borehole_depth_m=(
            borehole_program[0].termination_depth_m if len(borehole_program) == 1 else None
        ),
        test_pit_quantity=test_pit_program[0].quantity if len(test_pit_program) == 1 else None,
        test_pit_depth_m=(
            test_pit_program[0].termination_depth_m if len(test_pit_program) == 1 else None
        ),
        access_notes="\n".join(scope["Access note"]),
        utility_locate_notes="\n".join(scope["Utility locate note"]),
        groundwater_notes="\n".join(scope["Groundwater note"]),
        laboratory_tests=scope["Laboratory test"],
        reporting_requirements=scope["Reporting requirement"],
        other_notes=st.session_state.edit_other_notes.strip(),
        cost_items=cost_items,
    )


def initialize_editor(facts: ProposalFacts) -> None:
    # A data editor keeps its own row/cell patch state under its widget key.
    # Clear that state only when loading a different proposal; changing the
    # editor's source frame on every rerun makes the first edit appear lost.
    st.session_state.pop("scope_editor", None)
    st.session_state.pop("cost_editor", None)
    borehole_program = facts.borehole_program or legacy_program(
        facts.borehole_quantity,
        facts.borehole_depth_m,
    )
    test_pit_program = facts.test_pit_program or legacy_program(
        facts.test_pit_quantity,
        facts.test_pit_depth_m,
    )
    defaults = {
        "edit_proposal_number": facts.proposal_number,
        "edit_proposal_date": date.fromisoformat(facts.proposal_date),
        "edit_client_name": facts.client_name,
        "edit_client_address": facts.client_address,
        "edit_contact_name": facts.contact_name,
        "edit_contact_title": facts.contact_title,
        "edit_contact_email": facts.contact_email,
        "edit_client_reference": facts.client_reference_number,
        "edit_project_name": facts.project_name,
        "edit_project_location": facts.project_location,
        "edit_development_description": facts.development_description,
        "edit_project_type": facts.project_type,
        "edit_methods": facts.investigation_methods,
        "edit_borehole_program": format_investigation_program(borehole_program, "borehole"),
        "edit_test_pit_program": format_investigation_program(test_pit_program, "test pit"),
        "edit_other_notes": facts.other_notes,
    }
    for key, value in defaults.items():
        st.session_state[key] = value
    facts_with_catalog = facts.model_copy(
        update={"cost_items": merge_standard_cost_items(facts.cost_items)}
    )
    st.session_state.cost_frame = cost_dataframe(facts_with_catalog)
    st.session_state.scope_frame = scope_dataframe(facts)


st.title("Almor Proposal Builder")
st.caption("Geotechnical proposals assembled from your request and the closest historical ATS/Almor examples.")

with st.expander("How it works", expanded=False):
    st.write(
        "Paste or upload the request, verify the extracted project and cost information, then generate "
        "a complete Word proposal, a compact authorization PDF, and the client email draft. Uploaded "
        "request files are processed for the current session. Only a reviewed Final Proposal that you "
        "explicitly confirm is saved to the private proposal library."
    )

st.subheader("1. Add the request")
proposal_number = st.text_input("Proposal number *", placeholder="P026-###")
email_text = st.text_area("Request email", height=220, placeholder="Paste the client's request email here...")
request_files = st.file_uploader(
    "Attachments",
    type=["eml", "pdf", "png", "jpg", "jpeg", "docx", "xlsx", "xlsm", "csv", "txt"],
    accept_multiple_files=True,
    help="Upload the request email, screenshots, PDFs, drawings, notes, and cost table.",
)
notes = st.text_area("Additional notes", height=100)

left, right = st.columns(2)
with left:
    analyze_clicked = st.button("Analyze request", type="primary", width="stretch")
with right:
    manual_clicked = st.button("Enter manually", width="stretch")

if analyze_clicked:
    if not proposal_number.strip():
        st.error("Enter the proposal number before analyzing the request.")
    elif not email_text.strip() and not request_files:
        st.error("Paste the request email or upload at least one source file.")
    else:
        try:
            with st.spinner("Extracting project facts and cost items..."):
                facts = api_client().extract_facts(
                    email_text=email_text,
                    notes=notes,
                    documents=uploaded_documents(request_files),
                    proposal_number=proposal_number,
                )
                facts = prepare_extracted_facts(facts)
            st.session_state.proposal_facts = facts.model_dump(mode="json")
            initialize_editor(facts)
            st.session_state.pop("generated_outputs", None)
            st.rerun()
        except Exception as error:
            st.error(str(error))

if manual_clicked:
    if not proposal_number.strip():
        st.error("Enter the proposal number first.")
    else:
        facts = initial_facts(proposal_number)
        st.session_state.proposal_facts = facts.model_dump(mode="json")
        initialize_editor(facts)
        st.session_state.pop("generated_outputs", None)
        st.rerun()

if "proposal_facts" in st.session_state:
    current = ProposalFacts.model_validate(st.session_state.proposal_facts)
    if "scope_frame" not in st.session_state:
        st.session_state.scope_frame = scope_dataframe(current)
    if "cost_frame" not in st.session_state:
        st.session_state.cost_frame = cost_dataframe(
            current.model_copy(update={"cost_items": merge_standard_cost_items(current.cost_items)})
        )
    st.divider()
    st.subheader("2. Verify the proposal information")

    project_tab, scope_tab, cost_tab = st.tabs(["Project", "Scope", "Cost table"])
    with project_tab:
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("Proposal number *", key="edit_proposal_number")
            st.date_input("Proposal date", key="edit_proposal_date")
            st.text_input("Client *", key="edit_client_name")
            st.text_area("Client address", key="edit_client_address", height=90)
            st.text_input("Client reference number", key="edit_client_reference")
        with col2:
            st.text_input("Contact name", key="edit_contact_name")
            st.text_input("Contact title", key="edit_contact_title")
            st.text_input("Contact email", key="edit_contact_email")
            st.text_input("Project name *", key="edit_project_name")
            st.text_area("Project location *", key="edit_project_location", height=90)
        st.text_area("Development description *", key="edit_development_description", height=110)
        st.text_input("Project type", key="edit_project_type")

    with scope_tab:
        st.multiselect(
            "Investigation methods",
            ["drilling", "test pits", "hand auger", "groundwater monitoring", "coring", "laboratory testing"],
            key="edit_methods",
        )
        st.caption(
            "Enter one quantity/depth group per line. These entries automatically enable drilling "
            "or test-pit wording; quantities are never inferred from cost-table hours."
        )
        q1, q2 = st.columns(2)
        with q1:
            st.text_area(
                "Borehole program",
                key="edit_borehole_program",
                height=110,
                placeholder="5 boreholes to 5 m\n3 boreholes to 6 m",
            )
        with q2:
            st.text_area(
                "Test-pit program",
                key="edit_test_pit_program",
                height=110,
                placeholder="4 test pits to 3 m",
            )
        st.caption("Add one scope item per row and select its category.")
        edited_scope = st.data_editor(
            st.session_state.scope_frame,
            num_rows="dynamic",
            width="stretch",
            hide_index=True,
            column_config={
                "Category": st.column_config.SelectboxColumn(
                    options=SCOPE_CATEGORIES,
                    required=True,
                ),
                "Value": st.column_config.TextColumn(),
            },
            key="scope_editor",
        )
        st.text_area("Other notes", key="edit_other_notes", height=90)

    with cost_tab:
        st.caption(
            "Edit the standard estimate below. Total is calculated automatically from Est. × Rate. "
            "Zero or blank quantities stay in this editor but are removed from the Word proposal."
        )
        edited_costs = recalculate_cost_frame(st.data_editor(
            st.session_state.cost_frame,
            num_rows="dynamic",
            width="stretch",
            hide_index=True,
            column_config={
                "Section": st.column_config.SelectboxColumn(
                    options=[
                        "Preliminary Work / Meetings",
                        "Field Program",
                        "Laboratory Testing Program",
                        "Engineering Analysis & Report Preparation",
                    ],
                    required=True,
                ),
                "Unit": st.column_config.SelectboxColumn(
                    options=["hr", "LS", "Ea"],
                    required=True,
                    help="Every line item can be changed to hourly, lump sum, or each.",
                ),
                "Est.": st.column_config.NumberColumn(min_value=0.0),
                "Rate": st.column_config.NumberColumn(min_value=0.0, format="$%.2f"),
                "Total": st.column_config.NumberColumn(min_value=0.0, format="$%.2f"),
            },
            key="cost_editor",
            disabled=["Total"],
        ))
        preview = normalize_cost_items(dataframe_costs(edited_costs))
        subtotal_columns = st.columns(4)
        for column, section in zip(subtotal_columns, preview.section_totals, strict=True):
            with column:
                st.metric(section, f"${preview.section_totals[section]:,.2f}")
        st.metric("Estimated Cost", f"${preview.final_total:,.2f}")

    facts = facts_from_editor(current, edited_costs, edited_scope)
    st.session_state.proposal_facts = facts.model_dump(mode="json")
    missing = st.session_state.get("scope_program_errors", []) + validate_facts(facts)
    if missing:
        st.warning("Please resolve before generating: " + "; ".join(missing))

    references = retrieve_references(facts)
    if references:
        selected_template = choose_template(references)
        with st.expander("Historical proposal matches", expanded=False):
            for match in references[:5]:
                st.write(
                    f"**{match.filename}** — {match.project_type}; "
                    f"{', '.join(match.methods) or 'general geotechnical'}"
                )

    st.divider()
    st.subheader("3. Generate the package")
    add_signatures = st.toggle(
        "Add signatures to PDF",
        value=True,
        help="When off, the compact PDF keeps the signature area blank. The Word proposal is never signed.",
    )
    generate_clicked = st.button(
        "Generate Word, PDF, and email",
        type="primary",
        width="stretch",
        disabled=bool(missing),
    )

    if generate_clicked:
        try:
            with st.spinner("Writing and assembling the closest-matching geotechnical proposal..."):
                ai = api_client()
                draft = ai.draft_content(facts, references, RULES_PATH)
                docx_bytes, docx_name = build_docx(selected_template, facts, draft)
                pdf_bytes, pdf_name = build_pdf_package(
                    docx_bytes,
                    facts,
                    draft,
                    add_signatures=add_signatures,
                )
            st.session_state.generated_outputs = {
                "docx": docx_bytes,
                "docx_name": docx_name,
                "pdf": pdf_bytes,
                "pdf_name": pdf_name,
                "email_subject": draft.email_subject,
                "email_body": draft.email_body,
                "template": selected_template.name,
                "signed": add_signatures,
            }
            st.success("Proposal package generated.")
        except Exception as error:
            st.error(str(error))

if "generated_outputs" in st.session_state:
    output = st.session_state.generated_outputs
    st.divider()
    st.subheader("Downloads")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Download complete Word proposal",
            data=output["docx"],
            file_name=output["docx_name"],
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    with col2:
        label = "Download signed PDF package" if output["signed"] else "Download unsigned PDF package"
        st.download_button(label, data=output["pdf"], file_name=output["pdf_name"], mime="application/pdf")
    st.caption(f"Word layout source: {output['template']}")
    st.subheader("Client email draft")
    st.text_input("Subject", value=output["email_subject"])
    st.text_area("Message", value=output["email_body"], height=220)

st.divider()
st.subheader("4. Add Final Proposal to Library")
st.caption(
    "Add only a reviewed Final Word proposal. The app privately records its differences from the AI "
    "draft; a repeated change must occur in at least 3 final proposals and still requires your approval "
    "before it becomes a drafting rule."
)

generated = st.session_state.get("generated_outputs")
draft_upload = None
if generated:
    st.info(f"AI draft selected: {generated['docx_name']}")
else:
    draft_upload = st.file_uploader(
        "AI draft Word file *",
        type=["docx"],
        key="library_draft_upload",
        help="Generate a proposal in this session or upload the original AI draft that was reviewed.",
    )

final_upload = st.file_uploader(
    "Reviewed Final Proposal Word file *",
    type=["docx"],
    key="library_final_upload",
)
final_confirmed = st.checkbox(
    "I confirm this is the reviewed Final Proposal approved for the proposal library.",
    key="library_final_confirmed",
)
add_final_clicked = st.button(
    "Add Final Proposal to Library",
    width="stretch",
    disabled=not final_confirmed,
)

if add_final_clicked:
    if library is None:
        st.error(
            "Private library storage is not configured. Add GITHUB_LIBRARY_TOKEN and "
            "GITHUB_LIBRARY_REPO in Streamlit Secrets."
        )
    elif final_upload is None:
        st.error("Upload the reviewed Final Proposal Word file.")
    elif not generated and draft_upload is None:
        st.error("Generate a proposal in this session or upload its original AI draft Word file.")
    else:
        try:
            draft_bytes = generated["docx"] if generated else draft_upload.getvalue()
            final_bytes = final_upload.getvalue()
            draft_name = generated["docx_name"] if generated else draft_upload.name
            draft_index = proposal_index_record(draft_bytes, draft_name)
            final_index = proposal_index_record(final_bytes, final_upload.name)
            final_number = final_index.get("proposal_number", "")
            if "P026-133" in final_upload.name.upper() or final_number == "P026-133":
                raise ValueError("P026-133 is excluded and cannot be added to the proposal library.")
            final_corpus = " ".join(final_index.get("sections", {}).values()).lower()
            if "geotechnical" not in final_corpus:
                raise ValueError("Only reviewed geotechnical proposals can be added to this library.")
            draft_number = draft_index.get("proposal_number", "")
            if draft_number and final_number and draft_number != final_number:
                raise ValueError(
                    f"The AI draft is {draft_number}, but the Final Proposal is {final_number}."
                )

            with st.spinner("Comparing the AI draft with the reviewed Final Proposal..."):
                comparison = compare_docx(draft_bytes, final_bytes)
                if comparison["differences"]:
                    analysis = api_client().analyze_revisions(comparison["differences"])
                else:
                    analysis = RevisionAnalysis(
                        summary="The reviewed Final Proposal matches the AI draft.", candidates=[]
                    )
                number = final_number or (
                    st.session_state.get("proposal_facts", {}).get("proposal_number", "")
                )
                provisional_path = f"data/historical_proposals/{final_upload.name}"
                record = revision_record(
                    proposal_number=number,
                    final_filename=final_upload.name,
                    repository_path=provisional_path,
                    comparison=comparison,
                    analysis=analysis,
                )
                _, state, repository_path = add_final_to_library(
                    client=library,
                    final_filename=final_upload.name,
                    final_bytes=final_bytes,
                    index_record=final_index,
                    revision_record=record,
                )
            load_index.cache_clear()
            st.session_state.library_state = state
            st.success(f"Added to the private proposal library: {repository_path}")
            st.write(analysis.summary)
            st.caption(f"Draft/final similarity: {comparison['similarity']:.1%}")
        except Exception as error:
            st.error(f"The Final Proposal was not fully added: {error}")

st.subheader("Repeated edits awaiting rule approval")
if library is None:
    st.caption(
        "Configure the private GitHub library connection to save Final Proposals and review repeated edits."
    )
else:
    try:
        if "library_state" not in st.session_state:
            st.session_state.library_state = library.read_json(
                "knowledge/library_state.json", empty_state()
            )
        ready_candidates = aggregate_rule_candidates(st.session_state.library_state)
        if not ready_candidates:
            st.caption("No repeated rule candidate has reached 3 reviewed Final Proposals yet.")
        else:
            selected_keys: list[str] = []
            for candidate in ready_candidates:
                checked = st.checkbox(
                    f"{candidate['instruction']} ({candidate['occurrences']} proposals)",
                    key=f"approve_rule_{candidate['key']}",
                )
                if checked:
                    selected_keys.append(candidate["key"])
            if st.button(
                "Approve selected rules",
                disabled=not selected_keys,
                width="stretch",
            ):
                state, _ = approve_rules(library, selected_keys)
                st.session_state.library_state = state
                st.success("Selected rules are now part of the approved drafting rules.")
                st.rerun()
    except Exception as error:
        st.warning(f"Could not load the private rule-review queue: {error}")
