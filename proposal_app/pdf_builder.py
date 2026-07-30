from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from lxml import etree
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, TextStringObject
from reportlab.pdfgen import canvas

from .config import (
    ABDUL_SIGNATURE_PATH,
    ATS_CONTACT,
    STANDARD_TERMS_PATH,
    STEVEN_SIGNATURE_PATH,
    WORK_AUTHORIZATION_PATH,
)
from .costs import format_money, normalize_cost_items
from .document_builder import format_date, output_stem
from .models import DraftContent, ProposalFacts


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{W_NS}}}"
FORM_FONT_SIZE = 6
WORK_AUTHORIZATION_SCOPE = "geotechnical services"


def find_soffice() -> str:
    for name in ("libreoffice", "soffice"):
        found = shutil.which(name)
        if found:
            return found
    windows_candidates = [
        Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "LibreOffice/program/soffice.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "LibreOffice/program/soffice.exe",
    ]
    for candidate in windows_candidates:
        if candidate.exists():
            return str(candidate)
    raise RuntimeError(
        "LibreOffice is required to create the PDF package. The Streamlit deployment installs it "
        "from packages.txt."
    )


def run_soffice_conversion(docx_path: Path, output_dir: Path) -> Path:
    profile_dir = output_dir / "libreoffice-profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    profile_uri = profile_dir.resolve().as_uri()
    command = [
        find_soffice(),
        "--headless",
        f"-env:UserInstallation={profile_uri}",
        "--convert-to",
        "pdf",
        "--outdir",
        str(output_dir),
        str(docx_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
    pdf_path = output_dir / f"{docx_path.stem}.pdf"
    if result.returncode != 0 or not pdf_path.exists() or pdf_path.stat().st_size == 0:
        detail = (result.stderr or result.stdout or "unknown conversion error").strip()
        raise RuntimeError(f"Word-to-PDF conversion failed: {detail}")
    return pdf_path


def cost_fee_paragraph_is_split(pdf_path: Path) -> bool:
    reader = PdfReader(pdf_path)
    start_page = None
    end_page = None
    for index, page in enumerate(reader.pages):
        text = (page.extract_text() or "").casefold()
        if "the total estimated geotechnical" in text:
            start_page = index
        if "invoices would be forwarded" in text:
            end_page = index
    return start_page is not None and end_page is not None and start_page != end_page


def compact_cost_section_for_libreoffice(docx_bytes: bytes) -> bytes:
    source = io.BytesIO(docx_bytes)
    target = io.BytesIO()
    with zipfile.ZipFile(source) as zin, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                root = etree.fromstring(data)
                for table in root.xpath(".//w:tbl", namespaces={"w": W_NS}):
                    table_text = " ".join(
                        table.xpath(".//w:tr[1]//w:t/text()", namespaces={"w": W_NS})
                    ).casefold()
                    required = ("item", "description", "unit", "est", "rate", "total")
                    if not all(label in table_text for label in required):
                        continue
                    for spacing in table.xpath(
                        ".//w:pPr/w:spacing",
                        namespaces={"w": W_NS},
                    ):
                        spacing.set(W + "after", "0")

                for paragraph in root.xpath(".//w:p", namespaces={"w": W_NS}):
                    text = "".join(
                        paragraph.xpath(".//w:t/text()", namespaces={"w": W_NS})
                    ).strip().casefold()
                    if not text.startswith("the total estimated geotechnical"):
                        continue
                    properties = paragraph.find(W + "pPr")
                    if properties is None:
                        properties = etree.Element(W + "pPr")
                        paragraph.insert(0, properties)
                    spacing = properties.find(W + "spacing")
                    if spacing is None:
                        spacing = etree.SubElement(properties, W + "spacing")
                    spacing.set(W + "after", "0")
                    spacing.set(W + "line", "240")
                    spacing.set(W + "lineRule", "auto")
                data = etree.tostring(
                    root,
                    xml_declaration=True,
                    encoding="UTF-8",
                    standalone="yes",
                )
            zout.writestr(item, data)
    return target.getvalue()


def convert_docx_to_pdf(docx_bytes: bytes, output_dir: Path, stem: str) -> Path:
    docx_path = output_dir / f"{stem}.docx"
    docx_path.write_bytes(docx_bytes)
    pdf_path = run_soffice_conversion(docx_path, output_dir)
    if cost_fee_paragraph_is_split(pdf_path):
        docx_path.write_bytes(compact_cost_section_for_libreoffice(docx_bytes))
        pdf_path.unlink(missing_ok=True)
        pdf_path = run_soffice_conversion(docx_path, output_dir)
        if cost_fee_paragraph_is_split(pdf_path):
            raise RuntimeError(
                "Word-to-PDF conversion split the cost fee paragraph across pages."
            )
    return pdf_path


def find_signature_page(reader: PdfReader) -> int:
    for index, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        required = ("Prepared by", "Reviewed By", "Steven Lai", "Abdul Alemi")
        if all(value.lower() in text.lower() for value in required):
            return index
    raise RuntimeError("Could not locate the proposal signature page in the rendered Word document.")


def signature_anchors(page) -> dict[str, tuple[float, float, float]]:
    anchors: dict[str, tuple[float, float, float]] = {}

    def visitor(text, _cm, tm, _font, font_size):
        lowered = text.casefold()
        for key, marker in (
            ("prepared", "prepared by"),
            ("reviewed", "reviewed by"),
            ("steven", "steven lai"),
            ("abdul", "abdul alemi"),
        ):
            if marker in lowered:
                anchors[key] = (float(tm[4]), float(tm[5]), float(font_size))

    page.extract_text(visitor_text=visitor)
    return anchors


def signature_overlay(page) -> bytes:
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(width, height))
    scale_x = width / 612.0
    scale_y = height / 792.0
    anchors = signature_anchors(page)

    prepared_x, prepared_y, prepared_size = anchors.get(
        "prepared",
        (56.7 * scale_x, 401.2 * scale_y, 11.0 * scale_y),
    )
    reviewed_x, reviewed_y, reviewed_size = anchors.get(
        "reviewed",
        (344.7 * scale_x, prepared_y, prepared_size),
    )
    _, steven_y, steven_size = anchors.get(
        "steven",
        (prepared_x, 292.9 * scale_y, prepared_size),
    )
    _, abdul_y, abdul_size = anchors.get(
        "abdul",
        (reviewed_x, steven_y, reviewed_size),
    )
    if reviewed_x < width / 2:
        reviewed_x = 344.7 * scale_x

    left_bottom = steven_y + steven_size + 6 * scale_y
    left_top = prepared_y - 6 * scale_y
    left_height = left_top - left_bottom
    if left_height <= 0:
        raise RuntimeError("The Prepared by signature area has no usable blank space.")
    steven_height = min(90 * scale_y, left_height)
    steven_width = steven_height * 126 / 151
    steven_bottom = left_bottom + (left_height - steven_height) / 2

    right_bottom = abdul_y + abdul_size + 6 * scale_y
    right_top = reviewed_y - 6 * scale_y
    right_height = right_top - right_bottom
    if right_height <= 0:
        raise RuntimeError("The Reviewed By signature area has no usable blank space.")
    abdul_height = min(55 * scale_y, right_height)
    abdul_width = abdul_height * 228 / 99
    abdul_bottom = right_bottom + (right_height - abdul_height) / 2

    pdf.drawImage(
        str(STEVEN_SIGNATURE_PATH),
        prepared_x + 25 * scale_x,
        steven_bottom,
        width=steven_width,
        height=steven_height,
        preserveAspectRatio=False,
        mask="auto",
    )
    pdf.drawImage(
        str(ABDUL_SIGNATURE_PATH),
        reviewed_x + 15 * scale_x,
        abdul_bottom,
        width=abdul_width,
        height=abdul_height,
        preserveAspectRatio=False,
        mask="auto",
    )
    pdf.save()
    return output.getvalue()


def extract_signature_page(rendered_pdf: Path, add_signatures: bool) -> bytes:
    reader = PdfReader(rendered_pdf)
    page = reader.pages[find_signature_page(reader)]
    if add_signatures:
        overlay = PdfReader(io.BytesIO(signature_overlay(page)))
        page.merge_page(overlay.pages[0])
    writer = PdfWriter()
    writer.add_page(page)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def filled_work_authorization(facts: ProposalFacts, draft: DraftContent) -> bytes:
    summary = normalize_cost_items(facts.cost_items)
    return fill_work_authorization(
        facts,
        scope=draft.work_authorization_scope,
        budget=summary.final_total,
        additional_comments=" ".join(draft.warnings),
    )


def fill_work_authorization(
    facts: ProposalFacts,
    scope: str,
    budget: float,
    additional_comments: str = "",
) -> bytes:
    reader = PdfReader(WORK_AUTHORIZATION_PATH)
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    available_fields = set((reader.get_fields() or {}).keys())
    values = {
        "Project_Name": facts.project_name,
        "Proposal_No": facts.proposal_number,
        "Client": facts.client_name,
        "Date1": format_date(facts.proposal_date),
        "Date_1": format_date(facts.proposal_date),
        "Client_Contact": facts.contact_name,
        "ATS_Contact": ATS_CONTACT,
        "Client_Reference_No": facts.client_reference_number,
        "ATS_Project_No": facts.proposal_number,
        "Scope_of_Work": WORK_AUTHORIZATION_SCOPE,
        "Budget": format_money(budget),
        "Budget_Manhour_Estimate": format_money(budget),
        "Additional_Comments": additional_comments,
    }
    filtered = {key: value for key, value in values.items() if key in available_fields}
    default_appearance = TextStringObject(f"/Helv {FORM_FONT_SIZE} Tf 0 g")
    acroform = writer.root_object.get("/AcroForm")
    if acroform:
        acroform.get_object()[NameObject("/DA")] = default_appearance
    for page in writer.pages:
        for annotation_ref in page.get("/Annots", []):
            annotation = annotation_ref.get_object()
            parent_ref = annotation.get("/Parent")
            parent = parent_ref.get_object() if parent_ref else None
            field_type = annotation.get("/FT") or (parent and parent.get("/FT"))
            if annotation.get("/Subtype") == "/Widget" and field_type == "/Tx":
                annotation[NameObject("/DA")] = default_appearance
                if parent:
                    parent[NameObject("/DA")] = default_appearance
        writer.update_page_form_field_values(page, filtered, auto_regenerate=False)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def combine_package(signature_page: bytes, work_authorization: bytes) -> bytes:
    writer = PdfWriter()
    writer.append(io.BytesIO(signature_page))
    writer.append(str(STANDARD_TERMS_PATH))
    writer.append(io.BytesIO(work_authorization))
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def complete_proposal_pdf(rendered_pdf: Path, add_signatures: bool) -> bytes:
    reader = PdfReader(rendered_pdf)
    if add_signatures:
        page = reader.pages[find_signature_page(reader)]
        overlay = PdfReader(io.BytesIO(signature_overlay(page)))
        page.merge_page(overlay.pages[0])
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def combine_complete_package(proposal: bytes, work_authorization: bytes) -> bytes:
    writer = PdfWriter()
    writer.append(io.BytesIO(proposal))
    writer.append(str(STANDARD_TERMS_PATH))
    writer.append(io.BytesIO(work_authorization))
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def build_pdf_package(
    docx_bytes: bytes,
    facts: ProposalFacts,
    draft: DraftContent,
    add_signatures: bool,
) -> tuple[bytes, str]:
    with tempfile.TemporaryDirectory(prefix="proposal_pdf_") as temporary:
        output_dir = Path(temporary)
        stem = output_stem(facts)
        rendered_pdf = convert_docx_to_pdf(docx_bytes, output_dir, stem)
        signature_page = extract_signature_page(rendered_pdf, add_signatures=add_signatures)
        authorization = filled_work_authorization(facts, draft)
        package = combine_package(signature_page, authorization)
    return package, output_stem(facts) + ".pdf"


def build_complete_pdf_package(
    docx_bytes: bytes,
    facts: ProposalFacts,
    scope: str,
    budget: float,
    add_signatures: bool,
) -> tuple[bytes, str]:
    with tempfile.TemporaryDirectory(prefix="complete_proposal_pdf_") as temporary:
        output_dir = Path(temporary)
        stem = output_stem(facts)
        rendered_pdf = convert_docx_to_pdf(docx_bytes, output_dir, stem)
        proposal = complete_proposal_pdf(rendered_pdf, add_signatures=add_signatures)
        authorization = fill_work_authorization(facts, scope=scope, budget=budget)
        package = combine_complete_package(proposal, authorization)
    return package, output_stem(facts) + ".pdf"
