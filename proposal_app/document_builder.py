from __future__ import annotations

import io
import re
import zipfile
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path

from docx import Document
from docx.document import Document as DocumentType
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor, Twips
from docx.table import Table, _Row
from docx.text.paragraph import Paragraph
from lxml import etree

from .config import HISTORICAL_DIR, SECTION_ORDER, STANDARD_TEMPLATE_PATH
from .costs import format_money, normalize_cost_items
from .models import DraftContent, ParagraphBlock, ProposalFacts


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
STANDPIPE_SCOPE = (
    "Installation of 25 mm diameter standpipe piezometers in all boreholes, backfilled with "
    "cuttings and capped with bentonite. Groundwater readings will be taken at the end of "
    "drilling and during one follow-up visit two weeks after the field program."
)
STANDARD_FIELD_PROGRAM_WORDING = (
    "Based on information supplied by the Client, Almor provides the following estimated cost "
    "to perform the geotechnical assessment, and any additional work directed by the Client "
    "will constitute a change in the scope of work. "
    "The geotechnical field program could be initiated within two weeks subject to rig availability "
    "and locates, subsequent to authorization. The estimated costs do not include environmental "
    "considerations of the development.  The field program will include geotechnical boreholes "
    "advanced using a track mounted solid stem auger drilling rig. It is our understanding access "
    "and clearing, if required, to the boreholes is suitable for a track mounted drilling rig and "
    "will be provided by the client as this work is outside the scope of our proposal.  The proposed "
    "scope of work for this project includes:"
)

XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
STANDARD_COST_WIDTHS = (3114, 3580, 528, 510, 1312, 928)
STANDARD_CLOSING = (
    "Almor is interested in supporting the successful design and construction of the proposed project."
)


def safe_filename(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', " ", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned or "Proposal"


def display_title(value: str) -> str:
    """Normalize display names while retaining legal identifiers and abbreviations."""
    abbreviations = {word: word.upper() for word in (
        "inc", "ltd", "llc", "ab", "bc", "sw", "se", "nw", "ne", "c/o", "ats"
    )}
    abbreviations.update({"inc": "Inc", "ltd": "Ltd"})
    def title_word(match):
        word = match.group(0)
        if any(char.isdigit() for char in word):
            return word.upper()
        return abbreviations.get(word.lower(), word.title())
    return re.sub(r"[\w/]+", title_word, value)


def output_stem(facts: ProposalFacts) -> str:
    number = safe_filename(facts.proposal_number) if facts.proposal_number.strip() else ""
    project = safe_filename(facts.project_name) if facts.project_name.strip() else ""
    client = safe_filename(facts.client_name) if facts.client_name.strip() else ""
    proposal = " ".join(value for value in (number, project) if value) or "Proposal"
    return f"{proposal} - {client}" if client else proposal


def parse_date(value: str) -> date:
    for parser in (
        lambda raw: date.fromisoformat(raw),
        lambda raw: datetime.strptime(raw, "%B %d, %Y").date(),
        lambda raw: datetime.strptime(raw, "%b %d, %Y").date(),
    ):
        try:
            return parser(value.strip())
        except (ValueError, TypeError):
            continue
    return date.today()


def format_date(value: str) -> str:
    parsed = parse_date(value)
    return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"


def set_paragraph_text(paragraph: Paragraph, text: str) -> None:
    if paragraph.runs:
        paragraph.runs[0].text = text
        for run in paragraph.runs[1:]:
            run._element.getparent().remove(run._element)
    else:
        paragraph.add_run(text)


def set_cell_text(cell, text: str) -> None:
    paragraph = cell.paragraphs[0]
    set_paragraph_text(paragraph, text)
    for extra in cell.paragraphs[1:]:
        extra._element.getparent().remove(extra._element)


def clean_cost_intro(text: str) -> str:
    return " ".join(line.strip() for line in text.splitlines() if line.strip() and "|" not in line)


def update_project_headers(document: DocumentType, facts: ProposalFacts) -> None:
    """Populate native repeating headers, preserving the first-page company letterhead."""
    values = [
        facts.client_name,
        "Proposal for Geotechnical Services",
        ", ".join(value.replace("\n", ", ") for value in
                  (facts.project_name, facts.project_location) if value.strip()),
        f"Almor Proposal No.: {facts.proposal_number}",
    ]
    seen = set()
    for section in document.sections:
        original_header_distance = section.header_distance
        section.header_distance = Inches(0.25)
        for header, first_page in (
            (section.header, False), (section.even_page_header, False),
            (section.first_page_header, True),
        ):
            if header.part.partname in seen:
                continue
            seen.add(header.part.partname)
            old_text = " ".join(header._element.xpath(".//w:t/text()"))
            if first_page and "Proposal for Geotechnical Services" not in old_text:
                # Keep the letterhead at its original page position when moving
                # the repeating text header closer to the top of later pages.
                for position in header._element.xpath(
                    ".//wp:positionV[@relativeFrom='paragraph']"
                ):
                    offset = position.find(qn("wp:posOffset"))
                    if offset is not None:
                        offset.text = str(int(offset.text) + int(original_header_distance or 0))
                        position.set("relativeFrom", "page")
                continue
            if first_page and "Project Name" in old_text:
                # The reference letterhead carries an invisible text-box copy
                # of its old project header. Keep the logo/drawing, but never
                # let that copy leak into a generated proposal.
                for text_node in header._element.xpath(".//w:t"):
                    text_node.text = ""
                continue
            # Textbox drawing/VML copies can disagree and clip long project names.
            # Native paragraphs give every page the same current facts and wrapping.
            for child in list(header._element):
                header._element.remove(child)
            for index, value in enumerate(values):
                paragraph = header.add_paragraph(value)
                style_name = "Header Client name" if index == 0 else "Header Body"
                if style_name in document.styles:
                    paragraph.style = document.styles[style_name]
                paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                fmt = paragraph.paragraph_format
                fmt.space_before = fmt.space_after = Pt(0)
                fmt.line_spacing = 1
                for run in paragraph.runs:
                    run.font.name = "Arial"
                    run.font.size = Pt(9 if index == 0 else 8)
                    run.font.color.rgb = RGBColor(102, 51, 0)
                    run.bold = index == 0
            border = OxmlElement("w:pBdr")
            bottom = OxmlElement("w:bottom")
            for key, value in (("val", "single"), ("sz", "6"), ("space", "6"), ("color", "663300")):
                bottom.set(qn("w:" + key), value)
            border.append(bottom)
            header.paragraphs[-1]._p.get_or_add_pPr().append(border)


def apply_standard_cost_table(document: DocumentType, existing: Table) -> Table:
    """Create one regular grid; historical merged cells and styles cannot affect it."""
    table = document.add_table(rows=5, cols=6)
    set_row_values(table.rows[0], ["Item", "Description", "Unit", "Est.", "Rate", "Total"])
    existing._tbl.addprevious(table._tbl)
    existing._tbl.getparent().remove(existing._tbl)
    return table


def format_standard_cost_table(table: Table) -> None:
    table.autofit = False
    for column, width in zip(table.columns, STANDARD_COST_WIDTHS, strict=True):
        column.width = Twips(width)
    properties = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        border = OxmlElement("w:" + side)
        for key, value in (("val", "single"), ("sz", "4"), ("color", "D9D9D9")):
            border.set(qn("w:" + key), value)
        borders.append(border)
    properties.append(borders)
    for index, row in enumerate(table.rows):
        row_properties = row._tr.get_or_add_trPr()
        row_properties.append(OxmlElement("w:cantSplit"))
        if index == 0:
            row_properties.append(OxmlElement("w:tblHeader"))
        section_row = bool(row.cells[0].text) and all(not cell.text for cell in row.cells[1:])
        total_row = row.cells[4].text in ("Subtotal", "Estimated Cost")
        fill = "D6DBD9" if index == 0 or index % 2 else "FFFFFF"
        for column_index, (cell, width) in enumerate(zip(row.cells, STANDARD_COST_WIDTHS, strict=True)):
            cell.width = Twips(width)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            cell_properties = cell._tc.get_or_add_tcPr()
            shading = OxmlElement("w:shd")
            shading.set(qn("w:fill"), fill)
            cell_properties.append(shading)
            margins = OxmlElement("w:tcMar")
            for side in ("top", "left", "bottom", "right"):
                margin = OxmlElement("w:" + side)
                margin.set(qn("w:w"), "50" if side in ("left", "right") else "0")
                margin.set(qn("w:type"), "dxa")
                margins.append(margin)
            cell_properties.append(margins)
            if index == 0:
                cell_properties.append(OxmlElement("w:noWrap"))
            for paragraph in cell.paragraphs:
                paragraph.style = "Normal"
                paragraph.alignment = (
                    WD_ALIGN_PARAGRAPH.RIGHT if column_index >= 4 else
                    WD_ALIGN_PARAGRAPH.CENTER if column_index in (2, 3) else
                    WD_ALIGN_PARAGRAPH.LEFT
                )
                fmt = paragraph.paragraph_format
                fmt.space_before = Pt(0)
                fmt.space_after = Pt(8)
                fmt.line_spacing = 1.07917
                fmt.keep_with_next = index == 0 or section_row
                for run in paragraph.runs:
                    run.font.name = "Arial"
                    run.font.size = Pt(8)
                    run.font.color.rgb = RGBColor(0, 0, 0)
                    run.bold = index == 0 or section_row or (total_row and column_index >= 4)


def format_standard_closure(document: DocumentType) -> None:
    paragraphs = paragraphs_between(document, "Closure", None)
    set_paragraph_text(paragraphs[0], STANDARD_CLOSING)
    paragraph_by_text(document, "Closure").paragraph_format.keep_with_next = True
    for paragraph in paragraphs:
        paragraph.paragraph_format.keep_with_next = True
    start = next(i for i, p in enumerate(paragraphs) if "Prepared by" in p.text)
    for index, paragraph in enumerate(paragraphs[start:]):
        # Replace inherited tabs/breaks that split the names onto a separate page.
        if paragraph._p.pPr is not None:
            paragraph._p.remove(paragraph._p.pPr)
        paragraph.style = "Body" if "Body" in document.styles else "Normal"
        parts = [part.strip() for part in paragraph.text.split("\t") if part.strip()]
        if len(parts) == 2:
            set_paragraph_text(paragraph, "\t".join(parts))
        fmt = paragraph.paragraph_format
        fmt.tab_stops.add_tab_stop(Inches(3.45))
        fmt.space_before = Pt(55 if index == 1 else 0)
        fmt.space_after = Pt(6)
        fmt.keep_with_next = index < len(paragraphs[start:]) - 1
        for run in paragraph.runs:
            run.font.name = "Arial"
            run.font.size = Pt(8 if index == len(paragraphs[start:]) - 1 else 11)


def paragraph_by_text(document: DocumentType, text: str) -> Paragraph:
    for paragraph in document.paragraphs:
        if paragraph.text.strip() == text:
            return paragraph
    raise ValueError(f"Required heading not found: {text}")


def paragraphs_between(document: DocumentType, start: str, end: str | None) -> list[Paragraph]:
    paragraphs = document.paragraphs
    start_index = next(i for i, p in enumerate(paragraphs) if p.text.strip() == start)
    if end is None:
        end_index = len(paragraphs)
    else:
        end_index = next(
            i for i, p in enumerate(paragraphs[start_index + 1 :], start_index + 1)
            if p.text.strip() == end
        )
    return paragraphs[start_index + 1 : end_index]


def following_section_heading(document: DocumentType, start_heading: str) -> Paragraph:
    """Find the template's section boundary without assuming its heading wording."""
    start = paragraph_by_text(document, start_heading)
    for paragraph in paragraphs_between(document, start_heading, None):
        if paragraph.text.strip() and (
            paragraph.style.style_id == start.style.style_id
            or paragraph.text.strip() == "Geotechnical Field Program"
        ):
            return paragraph
    raise ValueError(f"No following section heading found after {start_heading}")


def replace_xml_paragraph_text(paragraph_xml, text: str) -> None:
    text_nodes = paragraph_xml.xpath(".//w:t")
    if not text_nodes:
        return
    text_nodes[0].text = text
    text_nodes[0].set(XML_SPACE, "preserve")
    for node in text_nodes[1:]:
        node.text = ""


def clone_paragraph_before(anchor: Paragraph, prototype: Paragraph, text: str):
    clone = deepcopy(prototype._p)
    replace_xml_paragraph_text(clone, text)
    anchor._p.addprevious(clone)


def replace_section(
    document: DocumentType,
    start_heading: str,
    end_heading: str,
    blocks: list[ParagraphBlock],
) -> None:
    existing = paragraphs_between(document, start_heading, end_heading)
    if not existing:
        raise ValueError(f"No editable content found below {start_heading}")
    body_prototype = next((p for p in existing if p.style.name == "Body"), existing[0])
    list_prototype = next(
        (
            p
            for p in existing
            if p._p.pPr is not None and p._p.pPr.numPr is not None
        ),
        body_prototype,
    )
    for paragraph in existing:
        paragraph._element.getparent().remove(paragraph._element)
    anchor = paragraph_by_text(document, end_heading)
    for block in blocks:
        prototype = list_prototype if block.style == "list" else body_prototype
        clone_paragraph_before(anchor, prototype, block.text)


def update_front_matter(document: DocumentType, facts: ProposalFacts) -> dict[str, str]:
    introduction = paragraph_by_text(document, "Introduction")
    preceding = []
    for paragraph in document.paragraphs:
        if paragraph._p is introduction._p:
            break
        preceding.append(paragraph)
    if len(preceding) < 4:
        raise ValueError("Selected proposal does not have a compatible front matter layout.")

    # The P026-187 reference uses the compact ATS letter layout: date/number,
    # attention, a spacer, then one Re block containing project and location.
    # Keep that visual structure instead of forcing a client-address block into
    # the template and changing its page rhythm.
    attention_index = next(
        (index for index, paragraph in enumerate(preceding) if "Attention:" in paragraph.text),
        None,
    )
    re_index = next(
        (index for index, paragraph in enumerate(preceding) if paragraph.text.lstrip().startswith("Re:")),
        None,
    )
    if attention_index is not None and re_index is not None and re_index > attention_index:
        date_line_nodes = preceding[0]._p.xpath(".//w:t")
        old_date = preceding[0].text.split("\t", 1)[0].strip()
        old_number_match = re.search(r"P0\d{2}-[0-9A-Za-z]+", preceding[0].text)
        old_number = old_number_match.group(0) if old_number_match else "[Proposal Number]"
        replace_text_across_nodes(date_line_nodes, old_date, format_date(facts.proposal_date))
        if old_number:
            replace_text_across_nodes(date_line_nodes, old_number, facts.proposal_number)
        old_re_lines = preceding[re_index].text.splitlines()
        location_index = re_index + 1 if re_index + 1 < len(preceding) else None
        separate_location = bool(
            location_index is not None and preceding[location_index].text.strip()
        )
        if separate_location:
            client_index = next(
                (index for index in range(1, attention_index) if preceding[index].text.strip()),
                None,
            )
            old_client = (
                preceding[client_index].text.splitlines()[0].strip()
                if client_index is not None else ""
            )
            old_location = preceding[location_index].text.strip()
            client_block = "\n".join(
                value for value in [facts.client_name, facts.client_address] if value.strip()
            )
            if client_index is not None:
                set_paragraph_text(preceding[client_index], client_block)
            attention = f"Attention: {facts.contact_name}" if facts.contact_name else ""
            if facts.contact_title and facts.contact_name:
                attention = f"Attention: {facts.contact_name}, {facts.contact_title}"
            if facts.contact_email:
                attention = f"{attention} | {facts.contact_email}" if attention else facts.contact_email
            set_paragraph_text(preceding[attention_index], attention)
            set_paragraph_text(
                preceding[re_index],
                "Re:\tRequest for Proposal for Geotechnical Services",
            )
            set_paragraph_text(
                preceding[location_index],
                "\n".join([facts.project_name, *[line.strip() for line in facts.project_location.splitlines() if line.strip()]]),
            )
            return {
                "old_number": old_number,
                "old_client": old_client,
                "old_project": "",
                "old_location": old_location,
            }
        old_project = old_re_lines[1].strip() if len(old_re_lines) > 1 else ""
        old_location = "\n".join(line.strip() for line in old_re_lines[2:] if line.strip())
        attention = f"Attention: {facts.contact_name}" if facts.contact_name else ""
        if facts.contact_title and facts.contact_name:
            attention = f"Attention: {facts.contact_name}, {facts.contact_title}"
        if facts.contact_email:
            attention = f"{attention} | {facts.contact_email}" if attention else facts.contact_email
        set_paragraph_text(preceding[attention_index], attention)
        locations = [line.strip() for line in facts.project_location.splitlines() if line.strip()]
        set_paragraph_text(
            preceding[re_index],
            "Re:\tRequest for Proposal for Geotechnical Services\n"
            + "\n".join([facts.project_name, *locations]),
        )
        return {
            "old_number": old_number,
            "old_client": "",
            "old_project": old_project,
            "old_location": old_location,
        }

    old_number_match = re.search(r"P0\d{2}-[0-9A-Za-z]+", preceding[0].text)
    old_number = old_number_match.group(0) if old_number_match else ""
    old_client = preceding[1].text.splitlines()[0].strip() if len(preceding) > 1 else ""
    old_project = preceding[4].text.splitlines()[-1].strip() if len(preceding) > 4 else ""
    old_location = next(
        (
            line.strip().lstrip("\t")
            for paragraph in preceding[5:]
            for line in paragraph.text.splitlines()
            if line.strip()
        ),
        "",
    )

    date_line_nodes = preceding[0]._p.xpath(".//w:t")
    old_date = preceding[0].text.split("\t", 1)[0].strip()
    replace_text_across_nodes(date_line_nodes, old_date, format_date(facts.proposal_date))
    if old_number:
        replace_text_across_nodes(date_line_nodes, old_number, facts.proposal_number)
    client_block = "\n".join(
        value for value in [facts.client_name, facts.client_address] if value.strip()
    )
    set_paragraph_text(preceding[1], client_block)
    if len(preceding) > 2:
        set_paragraph_text(preceding[2], "")
    attention_parts = [facts.contact_name]
    if facts.contact_title:
        attention_parts[0] = f"{facts.contact_name}, {facts.contact_title}" if facts.contact_name else facts.contact_title
    attention = f"Attention: {attention_parts[0]}" if attention_parts[0] else ""
    if facts.contact_email:
        attention = f"{attention} | {facts.contact_email}" if attention else facts.contact_email
    if len(preceding) > 3:
        set_paragraph_text(preceding[3], attention)
    set_paragraph_text(
        preceding[4],
        f"Re:\tRequest for Proposal for Geotechnical Services\n{facts.project_name}",
    )
    location_lines = [line.strip() for line in facts.project_location.splitlines() if line.strip()]
    for index, paragraph in enumerate(preceding[5:]):
        set_paragraph_text(paragraph, location_lines[index] if index < len(location_lines) else "")

    return {
        "old_number": old_number,
        "old_client": old_client,
        "old_project": old_project,
        "old_location": old_location,
    }


def update_cost_table(table: Table, facts: ProposalFacts) -> float:
    summary = normalize_cost_items(facts.cost_items)
    if summary.warnings:
        raise ValueError(" ".join(summary.warnings))
    rows = table.rows
    if len(rows) < 4 or len(table.columns) != 6:
        raise ValueError("Selected proposal has an incompatible cost table.")
    section_template = deepcopy(rows[1]._tr)
    item_template = deepcopy(rows[2]._tr)
    subtotal_template = deepcopy(rows[3]._tr)
    final_template = deepcopy(rows[-1]._tr)
    for row in list(table.rows[1:]):
        table._tbl.remove(row._tr)

    by_section = {section: [] for section in SECTION_ORDER}
    for item in summary.items:
        by_section[item.section].append(item)

    for section in SECTION_ORDER:
        items = by_section[section]
        if not items:
            continue
        table._tbl.append(deepcopy(section_template))
        set_row_values(table.rows[-1], [section, "", "", "", "", ""])
        for item in items:
            table._tbl.append(deepcopy(item_template))
            estimate = "" if item.estimate is None else f"{item.estimate:g}"
            set_row_values(
                table.rows[-1],
                [
                    item.item,
                    item.description,
                    item.unit,
                    estimate,
                    format_money(item.rate),
                    format_money(item.total),
                ],
            )
        table._tbl.append(deepcopy(subtotal_template))
        set_row_values(
            table.rows[-1],
            ["", "", "", "", "Subtotal", format_money(summary.section_totals[section])],
        )

    table._tbl.append(deepcopy(final_template))
    set_row_values(
        table.rows[-1],
        ["", "", "", "", "Estimated Cost", format_money(summary.final_total)],
    )
    return summary.final_total


def set_row_values(row: _Row, values: list[str]) -> None:
    for cell, value in zip(row.cells, values, strict=True):
        set_cell_text(cell, value)


def update_cost_section(
    document: DocumentType,
    draft: DraftContent,
    facts: ProposalFacts,
    final_total: float,
) -> None:
    blocks = list(document.element.body.iterchildren())
    cost_heading = paragraph_by_text(document, "Cost of Geotechnical Services")._p
    terms_heading = paragraph_by_text(document, "Terms and Conditions")._p
    start = blocks.index(cost_heading)
    end = blocks.index(terms_heading)
    between = blocks[start + 1 : end]
    paragraphs = [Paragraph(node, document) for node in between if node.tag.endswith("}p")]
    if len(paragraphs) < 2:
        raise ValueError("Selected proposal cost section is incompatible.")
    set_paragraph_text(paragraphs[0], clean_cost_intro(draft.cost_intro))
    total_paragraph = next(
        (paragraph for paragraph in reversed(paragraphs) if re.search(r"\$[\d,]+\.\d{2}", paragraph.text)),
        None,
    )
    if total_paragraph is None:
        raise ValueError("Selected proposal fee paragraph has no replaceable total.")
    total_text, replacements = re.subn(
        r"\$[\d,]+\.\d{2}",
        format_money(final_total),
        total_paragraph.text,
        count=1,
    )
    if replacements != 1:
        raise ValueError("Selected proposal fee paragraph has no replaceable total.")
    set_paragraph_text(total_paragraph, total_text)


def update_closure(document: DocumentType, facts: ProposalFacts) -> None:
    paragraphs = paragraphs_between(document, "Closure", None)
    if len(paragraphs) < 8:
        raise ValueError("Selected proposal closure/signature block is incompatible.")
    # Standard closure and signature wording is controlled by the template.
    # Only the project-specific document identifier needs to change.
    identifier = next(
        (paragraph for paragraph in reversed(paragraphs) if paragraph.text.strip()),
        None,
    )
    if identifier is None:
        raise ValueError("Selected proposal signature block has no document identifier.")
    set_paragraph_text(identifier, output_stem(facts))


def patch_package_text(docx_bytes: bytes, replacements: dict[str, str]) -> bytes:
    source = io.BytesIO(docx_bytes)
    target = io.BytesIO()
    with zipfile.ZipFile(source) as zin, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.startswith("word/") and item.filename.endswith(".xml"):
                try:
                    root = etree.fromstring(data)
                    changed = False
                    for paragraph in root.xpath(".//w:p", namespaces={"w": W_NS}):
                        text_nodes = paragraph.xpath(".//w:t", namespaces={"w": W_NS})
                        if not text_nodes:
                            continue
                        for old, new in replacements.items():
                            if old and replace_text_across_nodes(text_nodes, old, new):
                                changed = True
                    if changed:
                        data = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")
                except etree.XMLSyntaxError:
                    pass
            zout.writestr(item, data)
    return target.getvalue()


def replace_text_across_nodes(text_nodes: list, old: str, new: str) -> bool:
    """Replace text without collapsing the template's separately formatted runs."""
    if not old or old == new:
        return False
    combined = "".join(node.text or "" for node in text_nodes)
    matches = [match.span() for match in re.finditer(re.escape(old), combined)]
    # Work backward through original matches so inserted text is never searched again.
    for start, end in reversed(matches):
        values = [node.text or "" for node in text_nodes]
        offsets = []
        cursor = 0
        for value in values:
            offsets.append((cursor, cursor + len(value)))
            cursor += len(value)

        start_index = next(
            index for index, (_, node_end) in enumerate(offsets) if start < node_end
        )
        end_index = next(
            index for index, (_, node_end) in enumerate(offsets) if end <= node_end
        )
        start_offset = start - offsets[start_index][0]
        end_offset = end - offsets[end_index][0]

        prefix = values[start_index][:start_offset]
        suffix = values[end_index][end_offset:]
        text_nodes[start_index].text = prefix + new + (suffix if start_index == end_index else "")
        text_nodes[start_index].set(XML_SPACE, "preserve")
        if start_index != end_index:
            for index in range(start_index + 1, end_index):
                text_nodes[index].text = ""
            text_nodes[end_index].text = suffix
            if suffix:
                text_nodes[end_index].set(XML_SPACE, "preserve")
    return bool(matches)


def find_header_location_replacements(
    docx_bytes: bytes,
    old_location: str,
    old_client: str,
    new_location: str,
) -> dict[str, str]:
    """Locate the template's visible header location slot without rebuilding its text box."""
    if not old_location:
        return {}
    replacements: dict[str, str] = {}
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
        for name in archive.namelist():
            if not name.startswith("word/header") or not name.endswith(".xml"):
                continue
            root = etree.fromstring(archive.read(name))
            for paragraph in root.xpath(
                ".//w:p[not(.//w:p)]",
                namespaces={"w": W_NS},
            ):
                text = "".join(
                    paragraph.xpath(".//w:t/text()", namespaces={"w": W_NS})
                ).strip()
                if (
                    old_location.casefold() in text.casefold()
                    and not (old_client and old_client.casefold() in text.casefold())
                    and "Almor Proposal No." not in text
                ):
                    replacements[text] = new_location
    return replacements


def find_header_project_replacements(
    docx_bytes: bytes,
    old_client: str,
    new_project: str,
) -> dict[str, str]:
    """Locate the primary header's project-name slot even when it differs from front matter."""
    replacements: dict[str, str] = {}
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
        header_names = sorted(
            name
            for name in archive.namelist()
            if name.startswith("word/header") and name.endswith(".xml")
        )
        for name in header_names:
            root = etree.fromstring(archive.read(name))
            paragraphs = root.xpath(
                ".//w:p[not(.//w:p)]",
                namespaces={"w": W_NS},
            )
            texts = [
                "".join(paragraph.xpath(".//w:t/text()", namespaces={"w": W_NS})).strip()
                for paragraph in paragraphs
            ]
            if not any("Proposal for Geotechnical Services" in text for text in texts):
                continue

            for text in texts:
                if not text:
                    continue
                if "Proposal for Geotechnical Services" in text:
                    match = re.search(
                        r"Proposal for Geotechnical Services\s+(.+?)\s+Almor Proposal No\.",
                        text,
                        flags=re.IGNORECASE,
                    )
                    if match:
                        replacements[match.group(1).strip()] = new_project
                    continue
                if "Almor Proposal No." in text:
                    continue
                if text == old_client or text == "Proposal for Geotechnical Services":
                    continue
                replacements[text] = new_project

            # The first qualifying header is the primary project header. Later
            # headers contain the project location and must remain independent.
            if replacements:
                break
    return replacements


def configure_personnel_section(
    document: DocumentType,
    include: bool,
    templates_dir: Path = HISTORICAL_DIR,
) -> None:
    """Keep/remove the complete section, or import its approved template wording."""
    heading = "Proposed Project Personnel"
    existing = next((p for p in document.paragraphs if p.text.strip() == heading), None)
    if existing is not None:
        if not include:
            end = following_section_heading(document, heading)._p
            node = existing._p
            while node is not end:
                following = node.getnext()
                node.getparent().remove(node)
                node = following
        return
    if not include:
        return

    anchor = following_section_heading(document, "Introduction")
    for path in sorted(templates_dir.glob("*.docx")):
        if path.name.startswith("~$"):
            continue
        source = Document(path)
        headings = [p.text.strip() for p in source.paragraphs]
        if heading not in headings:
            continue
        try:
            end_heading = following_section_heading(source, heading)
        except ValueError:
            continue
        personnel_paragraphs = [paragraph_by_text(source, heading)] + paragraphs_between(
            source, heading, end_heading.text.strip()
        )
        for paragraph in personnel_paragraphs:
            clone = deepcopy(paragraph._p)
            # A section break belongs to the source document, never the imported bio.
            for section in clone.xpath("./w:pPr/w:sectPr"):
                section.getparent().remove(section)
            anchor._p.addprevious(clone)
            imported = Paragraph(clone, document)
            style_name = paragraph.style.name
            imported.style = (
                document.styles[style_name]
                if style_name in document.styles else document.styles["Normal"]
            )
        return
    raise ValueError(
        "No approved personnel section was found in the historical templates. "
        "Uncheck Include Proposed Project Personnel section or add a template containing it."
    )


def build_docx(
    template_path: Path,
    facts: ProposalFacts,
    draft: DraftContent,
    include_proposed_project_personnel: bool = True,
    *,
    standard_layout: bool = False,
) -> tuple[bytes, str]:
    document = Document(template_path)
    if standard_layout:
        facts = facts.model_copy(update={key: display_title(getattr(facts, key)) for key in (
            "client_name", "client_address", "contact_name", "contact_title",
            "project_name", "project_location",
        )})
    configure_personnel_section(document, include_proposed_project_personnel)
    old_values = update_front_matter(document, facts)
    if standard_layout:
        update_project_headers(document, facts)

    replace_section(
        document,
        "Introduction",
        following_section_heading(document, "Introduction").text.strip(),
        [ParagraphBlock(text=draft.introduction, style="body")],
    )

    if standard_layout:
        # This paragraph is template-controlled and must remain verbatim;
        # generated project-specific bullets follow it without rewriting it.
        field_blocks = [ParagraphBlock(text=STANDARD_FIELD_PROGRAM_WORDING, style="body")]
    else:
        field_blocks = [ParagraphBlock(text=draft.field_program_intro, style="body")]
    field_blocks.extend(draft.field_program_paragraphs)
    replace_section(
        document,
        "Geotechnical Field Program",
        "Cost of Geotechnical Services",
        field_blocks,
    )

    cost_table = next((table for table in document.tables if len(table.columns) == 6), None)
    if cost_table is None:
        raise ValueError("Selected proposal does not contain a compatible six-column cost table.")
    if standard_layout:
        cost_table = apply_standard_cost_table(document, cost_table)
    final_total = update_cost_table(cost_table, facts)
    if standard_layout:
        format_standard_cost_table(cost_table)
    update_cost_section(document, draft, facts, final_total)

    if not paragraphs_between(document, "Terms and Conditions", "Closure"):
        raise ValueError("Selected proposal terms section is incompatible.")
    update_closure(document, facts)
    if standard_layout:
        identifier = next(p for p in reversed(document.paragraphs) if p.text.strip())
        set_paragraph_text(identifier, display_title(identifier.text))
        format_standard_closure(document)
        document.core_properties.title = output_stem(facts)
        document.core_properties.subject = "Proposal for Geotechnical Services"

    buffer = io.BytesIO()
    document.save(buffer)
    saved_bytes = buffer.getvalue()
    header_location = ", ".join(
        line.strip() for line in facts.project_location.splitlines() if line.strip()
    )
    replacements = {
        old_values["old_number"]: facts.proposal_number,
        old_values["old_client"]: facts.client_name,
        old_values["old_project"]: facts.project_name,
    }
    replacements.update(
        find_header_project_replacements(
            saved_bytes,
            old_values["old_client"],
            facts.project_name,
        )
    )
    replacements.update(
        find_header_location_replacements(
            saved_bytes,
            old_values["old_location"],
            old_values["old_client"],
            header_location,
        )
    )
    result = saved_bytes if standard_layout else patch_package_text(saved_bytes, replacements)
    return ensure_standpipe_scope(
        result, required=bool(facts.borehole_program or facts.borehole_quantity or "drilling" in facts.investigation_methods)
    ), output_stem(facts) + ".docx"


def build_standard_docx(
    facts: ProposalFacts,
    draft: DraftContent,
    include_proposed_project_personnel: bool = True,
) -> tuple[bytes, str]:
    """Generate every proposal from the same approved layout, independent of retrieval."""
    if not facts.proposal_number.strip():
        raise ValueError("Enter the proposal number before generating the Word proposal.")
    template_path = STANDARD_TEMPLATE_PATH
    if not template_path.is_file():
        # Resolve only after encrypted assets have been loaded. Search ranking
        # cannot change the approved baseline, and customer filenames stay private.
        candidates = list(HISTORICAL_DIR.glob("P026-121 *.docx"))
        if not candidates:
            raise FileNotFoundError("The standard Almor proposal template (P026-121) is missing.")
        if len(candidates) != 1:
            raise ValueError("Provide one standard Almor template; multiple P026-121 files were found.")
        template_path = candidates[0]
    return build_docx(
        template_path, facts, draft, include_proposed_project_personnel,
        standard_layout=True,
    )


def ensure_standpipe_scope(data: bytes, required: bool = False) -> bytes:
    """Ensure borehole proposals include the approved standpipe scope in the field program."""
    document = Document(io.BytesIO(data))
    headings = [p.text.strip() for p in document.paragraphs]
    if "Geotechnical Field Program" not in headings or "Cost of Geotechnical Services" not in headings:
        if required:
            raise ValueError("Cannot add standpipe scope: the proposal field-program headings are missing.")
        return data
    field = paragraphs_between(document, "Geotechnical Field Program", "Cost of Geotechnical Services")
    text = " ".join(p.text for p in field).lower()
    if not required and not re.search(r"\bboreholes?\b", text):
        return data
    existing = next((p for p in field if "standpipe" in p.text.lower()), None)
    if existing is not None:
        if not required or existing.text == STANDPIPE_SCOPE:
            return data
        set_paragraph_text(existing, STANDPIPE_SCOPE)
        output = io.BytesIO()
        document.save(output)
        return output.getvalue()
    anchor = next((p for p in field if "preparation of" in p.text.lower()),
                  paragraph_by_text(document, "Cost of Geotechnical Services"))
    prototype = next((p for p in field if p._p.pPr is not None and p._p.pPr.numPr is not None),
                     field[0] if field else anchor)
    clone_paragraph_before(anchor, prototype, STANDPIPE_SCOPE)
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()
