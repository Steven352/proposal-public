import io
import unittest
import zipfile

from proposal_app.document_builder import find_header_project_replacements


def docx_with_header(paragraphs: list[str]) -> bytes:
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        + "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
        + "</w:hdr>"
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("word/header1.xml", xml)
    return output.getvalue()


class DocumentHeaderTest(unittest.TestCase):
    def test_replaces_short_template_project_name(self):
        data = docx_with_header(
            [
                "Strathmore Golf Club",
                "Proposal for Geotechnical Services",
                "Proposed Clubhouse Expansion",
                "Almor Proposal No.: P026-121",
            ]
        )
        replacements = find_header_project_replacements(
            data,
            "Strathmore Golf Club",
            "New Full Project Name",
        )
        self.assertEqual(replacements, {"Proposed Clubhouse Expansion": "New Full Project Name"})

    def test_replaces_project_inside_combined_header_text(self):
        data = docx_with_header(
            [
                "Client Proposal for Geotechnical Services Old Short Project "
                "Almor Proposal No.: P026-121"
            ]
        )
        replacements = find_header_project_replacements(data, "Client", "New Project")
        self.assertEqual(replacements, {"Old Short Project": "New Project"})


if __name__ == "__main__":
    unittest.main()
