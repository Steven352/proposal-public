import io
import tempfile
import unittest
from pathlib import Path

from docx import Document

from proposal_app import document_builder


class PersonnelDocumentTest(unittest.TestCase):
    def template(self, include_personnel=True):
        document = Document()
        document.sections[0].header.paragraphs[0].text = "Current project header"
        document.add_heading("Introduction", 1)
        document.add_paragraph("Introduction content")
        if include_personnel:
            document.add_heading("Proposed Project Personnel", 1)
            document.add_paragraph("Approved personnel biography")
        document.add_heading("Scope of Work and Cost Summary", 1)
        document.add_paragraph("Scope content")
        return document

    def test_unchecked_removes_entire_section_and_preserves_header(self):
        document = self.template()
        document_builder.configure_personnel_section(document, False)
        text = "\n".join(p.text for p in document.paragraphs)
        self.assertNotIn("Proposed Project Personnel", text)
        self.assertNotIn("Approved personnel biography", text)
        self.assertIn("Introduction content", text)
        self.assertIn("Scope content", text)
        self.assertEqual(document.sections[0].header.paragraphs[0].text, "Current project header")

    def test_checked_preserves_existing_template_section(self):
        document = self.template()
        original = document.element.xml
        document_builder.configure_personnel_section(document, True)
        self.assertEqual(document.element.xml, original)

    def test_checked_imports_template_section_if_selected_layout_lacks_it(self):
        document = self.template(False)
        with tempfile.TemporaryDirectory() as directory:
            self.template().save(Path(directory) / "approved-template.docx")
            document_builder.configure_personnel_section(document, True, Path(directory))
        texts = [p.text for p in document.paragraphs]
        self.assertIn("Approved personnel biography", texts)
        self.assertLess(texts.index("Introduction content"), texts.index("Proposed Project Personnel"))
        self.assertLess(texts.index("Approved personnel biography"), texts.index("Scope of Work and Cost Summary"))
        buffer = io.BytesIO()
        document.save(buffer)
        self.assertEqual(Document(buffer).sections[0].header.paragraphs[0].text, "Current project header")

    def test_missing_approved_personnel_template_reports_actionable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "personnel.*template|template.*personnel"):
                document_builder.configure_personnel_section(self.template(False), True, Path(directory))
