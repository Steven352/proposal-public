from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from pypdf import PdfReader, PdfWriter
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


def convert_docx_to_pdf(docx_bytes: bytes, output_dir: Path, stem: str) -> Path:
    docx_path = output_dir / f"{stem}.docx"
    docx_path.write_bytes(docx_bytes)
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
    pdf_path = output_dir / f"{stem}.pdf"
    if result.returncode != 0 or not pdf_path.exists() or pdf_path.stat().st_size == 0:
        detail = (result.stderr or result.stdout or "unknown conversion error").strip()
        raise RuntimeError(f"Word-to-PDF conversion failed: {detail}")
    return pdf_path


def find_signature_page(reader: PdfReader) -> int:
    for index, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        required = ("Prepared by", "Reviewed By", "Steven Lai", "Abdul Alemi")
        if all(value.lower() in text.lower() for value in required):
            return index
    raise RuntimeError("Could not locate the proposal signature page in the rendered Word document.")


def signature_overlay(width: float, height: float) -> bytes:
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(width, height))
    scale_x = width / 612.0
    scale_y = height / 792.0
    pdf.drawImage(
        str(STEVEN_SIGNATURE_PATH),
        82 * scale_x,
        310 * scale_y,
        width=75 * scale_x,
        height=90 * scale_y,
        preserveAspectRatio=True,
        mask="auto",
    )
    pdf.drawImage(
        str(ABDUL_SIGNATURE_PATH),
        360 * scale_x,
        325 * scale_y,
        width=120 * scale_x,
        height=55 * scale_y,
        preserveAspectRatio=True,
        mask="auto",
    )
    pdf.save()
    return output.getvalue()


def extract_signature_page(rendered_pdf: Path, add_signatures: bool) -> bytes:
    reader = PdfReader(rendered_pdf)
    page = reader.pages[find_signature_page(reader)]
    if add_signatures:
        overlay = PdfReader(io.BytesIO(signature_overlay(float(page.mediabox.width), float(page.mediabox.height))))
        page.merge_page(overlay.pages[0])
    writer = PdfWriter()
    writer.add_page(page)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def filled_work_authorization(facts: ProposalFacts, draft: DraftContent) -> bytes:
    summary = normalize_cost_items(facts.cost_items)
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
        "Scope_of_Work": draft.work_authorization_scope,
        "Budget": format_money(summary.final_total),
        "Budget_Manhour_Estimate": format_money(summary.final_total),
        "Additional_Comments": " ".join(draft.warnings),
    }
    filtered = {key: value for key, value in values.items() if key in available_fields}
    for page in writer.pages:
        writer.update_page_form_field_values(page, filtered, auto_regenerate=False)
    writer.set_need_appearances_writer(True)
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

