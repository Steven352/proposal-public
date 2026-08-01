import io
import unittest

from pypdf import PdfReader
from reportlab.pdfgen import canvas

from proposal_app.pdf_builder import rasterize_pdf_page


class PdfImagePageTest(unittest.TestCase):
    def test_rasterized_page_has_no_selectable_text(self):
        source = io.BytesIO()
        pdf = canvas.Canvas(source, pagesize=(612, 792))
        pdf.drawString(72, 720, "Prepared by Steven Lai")
        pdf.save()
        page = PdfReader(io.BytesIO(source.getvalue())).pages[0]

        rasterized = PdfReader(io.BytesIO(rasterize_pdf_page(page, dpi=100)))

        self.assertEqual(len(rasterized.pages), 1)
        self.assertEqual(rasterized.pages[0].extract_text() or "", "")
        self.assertAlmostEqual(float(rasterized.pages[0].mediabox.width), 612)
        self.assertAlmostEqual(float(rasterized.pages[0].mediabox.height), 792)


if __name__ == "__main__":
    unittest.main()
