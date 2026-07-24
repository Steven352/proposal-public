from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import datetime

from docx import Document

from .costs import as_number
from .models import ProposalFacts


PROPOSAL_NUMBER_PATTERN = re.compile(r"P0\d{2}-[0-9A-Za-z]+", re.IGNORECASE)
MONEY_PATTERN = re.compile(r"\$\s*([\d,]+(?:\.\d{2})?)")


@dataclass(frozen=True)
class UploadedProposalDetails:
    facts: ProposalFacts
    work_authorization_scope: str
    budget: float


def _nonempty_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _money(value: str) -> float | None:
    matches = MONEY_PATTERN.findall(value)
    return as_number(matches[-1]) if matches else None


def _iso_date(value: str) -> str:
    for date_format in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), date_format).date().isoformat()
        except ValueError:
            continue
    return ""


def _proposal_budget(document) -> float | None:
    for table in document.tables:
        for row in reversed(table.rows):
            values = [cell.text.strip() for cell in row.cells]
            if any("estimated cost" in value.casefold() for value in values):
                amount = _money(" ".join(values))
                if amount is not None:
                    return amount
    for paragraph in document.paragraphs:
        if "total estimated" in paragraph.text.casefold():
            amount = _money(paragraph.text)
            if amount is not None:
                return amount
    return None


def _project_details(paragraphs, re_index: int, introduction_index: int | None) -> tuple[str, str]:
    end_index = introduction_index if introduction_index is not None else len(paragraphs)
    candidate_lines: list[str] = []
    for index, paragraph in enumerate(paragraphs[re_index:end_index], start=re_index):
        lines = _nonempty_lines(paragraph.text)
        if index == re_index and lines:
            lines[0] = re.sub(r"^re\s*:\s*", "", lines[0], flags=re.IGNORECASE).strip()
        candidate_lines.extend(
            line
            for line in lines
            if line and "request for proposal" not in line.casefold()
        )
    if not candidate_lines:
        return "", ""
    return candidate_lines[0], "\n".join(candidate_lines[1:])


def extract_uploaded_proposal(docx_bytes: bytes) -> UploadedProposalDetails:
    try:
        document = Document(io.BytesIO(docx_bytes))
    except Exception as exc:
        raise ValueError("The uploaded file is not a readable Word proposal.") from exc

    paragraphs = document.paragraphs
    proposal_line_index = next(
        (
            index
            for index, paragraph in enumerate(paragraphs)
            if "almor proposal no." in paragraph.text.casefold()
        ),
        None,
    )
    if proposal_line_index is None:
        raise ValueError("Could not find 'Almor Proposal No.' in the uploaded Word proposal.")

    proposal_line = paragraphs[proposal_line_index].text
    number_match = PROPOSAL_NUMBER_PATTERN.search(proposal_line)
    proposal_number = number_match.group(0).upper() if number_match else ""
    date_text = re.split(
        r"almor proposal no\.?:?",
        proposal_line,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    proposal_date = _iso_date(date_text.strip(" \t|-:"))

    introduction_index = next(
        (index for index, paragraph in enumerate(paragraphs) if paragraph.text.strip() == "Introduction"),
        None,
    )
    re_index = next(
        (
            index
            for index, paragraph in enumerate(paragraphs)
            if re.match(r"^re\s*:", paragraph.text.strip(), flags=re.IGNORECASE)
        ),
        None,
    )
    attention_index = next(
        (
            index
            for index, paragraph in enumerate(paragraphs)
            if paragraph.text.strip().casefold().startswith("attention:")
        ),
        None,
    )

    client_name = ""
    for paragraph in paragraphs[proposal_line_index + 1 : re_index or len(paragraphs)]:
        lines = _nonempty_lines(paragraph.text)
        if lines and not lines[0].casefold().startswith("attention:"):
            client_name = lines[0]
            break

    contact_name = ""
    contact_email = ""
    if attention_index is not None:
        attention = paragraphs[attention_index].text.strip()
        contact = attention.split(":", 1)[-1].strip()
        contact_parts = [part.strip() for part in contact.split("|", 1)]
        contact_name = contact_parts[0]
        if len(contact_parts) > 1:
            contact_email = contact_parts[1]

    project_name = ""
    project_location = ""
    if re_index is not None:
        project_name, project_location = _project_details(
            paragraphs,
            re_index,
            introduction_index,
        )

    budget = _proposal_budget(document)
    missing = [
        label
        for label, value in (
            ("proposal number", proposal_number),
            ("proposal date", proposal_date),
            ("client", client_name),
            ("project name", project_name),
            ("estimated cost", budget),
        )
        if not value
    ]
    if missing:
        raise ValueError("Could not read these required proposal fields: " + ", ".join(missing) + ".")

    facts = ProposalFacts(
        proposal_number=proposal_number,
        proposal_date=proposal_date,
        client_name=client_name,
        contact_name=contact_name,
        contact_email=contact_email,
        project_name=project_name,
        project_location=project_location,
    )
    scope = f"{project_name} - geotechnical services described in {proposal_number}."
    return UploadedProposalDetails(
        facts=facts,
        work_authorization_scope=scope,
        budget=float(budget),
    )
