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
from proposal_app.document_builder import build_docx
from proposal_app.file_ingest import UploadedDocument
from proposal_app.knowledge import choose_template, load_index, retrieve_references
from proposal_app.models import CostLineItem, ProposalFacts
from proposal_app.pdf_builder import build_pdf_package
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


def uploaded_documents(files) -> list[UploadedDocument]:
    return [
        UploadedDocument(file.name, file.getvalue(), file.type or "")
        for file in (files or [])
    ]


def initial_facts(proposal_number: str) -> ProposalFacts:
    return ProposalFacts(
        proposal_number=proposal_number.strip(),
        proposal_date=date.today().isoformat(),
    )


def cost_dataframe(facts: ProposalFacts) -> pd.DataFrame:
    rows = [
        {
            "Section": item.section,
            "Item": item.item,
            "Description": item.description,
            "Unit": item.unit,
            "Est.": item.estimate,
            "Rate": item.rate,
            "Total": item.total,
        }
        for item in facts.cost_items
    ]
    return pd.DataFrame(
        rows,
        columns=["Section", "Item", "Description", "Unit", "Est.", "Rate", "Total"],
    )


def dataframe_costs(frame: pd.DataFrame) -> list[CostLineItem]:
    items: list[CostLineItem] = []
    for row in frame.fillna("").to_dict(orient="records"):
        if not any(str(value).strip() for value in row.values()):
            continue
        items.append(
            CostLineItem(
                section=str(row.get("Section", "")),
                item=str(row.get("Item", "")),
                description=str(row.get("Description", "")),
                unit=str(row.get("Unit", "")),
                estimate=row.get("Est.") or None,
                rate=row.get("Rate") or None,
                total=row.get("Total") or None,
            )
        )
    return items


def facts_from_editor(current: ProposalFacts, edited_costs: pd.DataFrame) -> ProposalFacts:
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
        requested_services=[x.strip() for x in st.session_state.edit_requested_services.splitlines() if x.strip()],
        investigation_methods=list(st.session_state.edit_methods),
        borehole_quantity=st.session_state.edit_borehole_quantity,
        borehole_depth_m=st.session_state.edit_borehole_depth,
        test_pit_quantity=st.session_state.edit_test_pit_quantity,
        test_pit_depth_m=st.session_state.edit_test_pit_depth,
        access_notes=st.session_state.edit_access_notes.strip(),
        utility_locate_notes=st.session_state.edit_locate_notes.strip(),
        groundwater_notes=st.session_state.edit_groundwater_notes.strip(),
        laboratory_tests=[x.strip() for x in st.session_state.edit_lab_tests.splitlines() if x.strip()],
        reporting_requirements=[x.strip() for x in st.session_state.edit_reporting.splitlines() if x.strip()],
        other_notes=st.session_state.edit_other_notes.strip(),
        cost_items=dataframe_costs(edited_costs),
    )


def initialize_editor(facts: ProposalFacts) -> None:
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
        "edit_requested_services": "\n".join(facts.requested_services),
        "edit_methods": facts.investigation_methods,
        "edit_borehole_quantity": facts.borehole_quantity,
        "edit_borehole_depth": facts.borehole_depth_m,
        "edit_test_pit_quantity": facts.test_pit_quantity,
        "edit_test_pit_depth": facts.test_pit_depth_m,
        "edit_access_notes": facts.access_notes,
        "edit_locate_notes": facts.utility_locate_notes,
        "edit_groundwater_notes": facts.groundwater_notes,
        "edit_lab_tests": "\n".join(facts.laboratory_tests),
        "edit_reporting": "\n".join(facts.reporting_requirements),
        "edit_other_notes": facts.other_notes,
    }
    for key, value in defaults.items():
        st.session_state[key] = value
    st.session_state.cost_frame = cost_dataframe(facts)


st.title("Almor Proposal Builder")
st.caption("Geotechnical proposals assembled from your request and the closest historical ATS/Almor examples.")

with st.expander("How it works", expanded=False):
    st.write(
        "Paste or upload the request, verify the extracted project and cost information, then generate "
        "a complete Word proposal, a compact authorization PDF, and the client email draft. Uploaded "
        "files are processed for the current session and are not saved by this app."
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
        q1, q2, q3, q4 = st.columns(4)
        with q1:
            st.number_input("Boreholes", min_value=0, step=1, value=None, key="edit_borehole_quantity")
        with q2:
            st.number_input("Borehole depth (m)", min_value=0.0, step=0.5, value=None, key="edit_borehole_depth")
        with q3:
            st.number_input("Test pits", min_value=0, step=1, value=None, key="edit_test_pit_quantity")
        with q4:
            st.number_input("Test-pit depth (m)", min_value=0.0, step=0.5, value=None, key="edit_test_pit_depth")
        st.text_area("Requested services (one per line)", key="edit_requested_services", height=110)
        st.text_area("Laboratory tests (one per line)", key="edit_lab_tests", height=110)
        st.text_area("Reporting requirements (one per line)", key="edit_reporting", height=110)
        st.text_area("Access notes", key="edit_access_notes", height=80)
        st.text_area("Utility locate notes", key="edit_locate_notes", height=80)
        st.text_area("Groundwater notes", key="edit_groundwater_notes", height=80)
        st.text_area("Other notes", key="edit_other_notes", height=90)

    with cost_tab:
        st.caption("Zero or blank quantities are removed. Rates and totals are checked before generation.")
        edited_costs = st.data_editor(
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
                "Est.": st.column_config.NumberColumn(min_value=0.0),
                "Rate": st.column_config.NumberColumn(min_value=0.0, format="$%.2f"),
                "Total": st.column_config.NumberColumn(min_value=0.0, format="$%.2f"),
            },
            key="cost_editor",
        )

    facts = facts_from_editor(current, edited_costs)
    st.session_state.proposal_facts = facts.model_dump(mode="json")
    st.session_state.cost_frame = edited_costs
    missing = validate_facts(facts)
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

with st.sidebar:
    st.write("Private proposal workspace")
    st.caption(f"Knowledge base: {len(load_index())} historical geotechnical proposals")
    st.caption(
        f"Extraction model: {secret('OPENAI_EXTRACTION_MODEL', DEFAULT_EXTRACTION_MODEL)}"
    )
    st.caption(
        f"Draft model: {secret('OPENAI_DRAFT_MODEL', secret('OPENAI_MODEL', DEFAULT_DRAFT_MODEL))}"
    )
