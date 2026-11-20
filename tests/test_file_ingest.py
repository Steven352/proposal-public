import io
import unittest
import subprocess
import tempfile
from pathlib import Path
from proposal_app.pdf_builder import find_soffice
from email.message import EmailMessage
from docx import Document
from openpyxl import Workbook
from PIL import Image
from msg_fixture import msg_bytes
from proposal_app.file_ingest import UploadedDocument, build_openai_content, extract_text


class FileIngestTest(unittest.TestCase):
    def test_outlook_unicode_headers_body_and_attachment_reach_analysis(self):
        content = build_openai_content('', '', [UploadedDocument('Request.MSG', msg_bytes())])
        text = content[0]['text']
        for expected in ('Alex Example', 'proposals@example.com', 'reviewer@example.com',
                         'E2E-TEST-610', '測試', 'site-notes.txt', 'ATTACHMENT-MARKER-610'):
            self.assertIn(expected, text)
        self.assertEqual(len(content), 1)

    def test_outlook_html_only_body(self):
        text, _ = extract_text(UploadedDocument('request.msg', msg_bytes(html=True)))
        self.assertIn('HTML-only warehouse request', text)

    def test_invalid_outlook_has_useful_error(self):
        with self.assertRaisesRegex(ValueError, r'broken.msg'):
            build_openai_content('', '', [UploadedDocument('broken.msg', b'not an outlook file')])

    def test_word_excel_and_eml_still_reach_analysis(self):
        word = Document()
        word.add_paragraph('WORD-MARKER')
        docx = io.BytesIO()
        word.save(docx)
        book = Workbook()
        book.active.append(['EXCEL-MARKER', 125.5])
        xlsx = io.BytesIO()
        book.save(xlsx)
        email = EmailMessage()
        email['Subject'] = 'EML-MARKER'
        email.set_content('Email body')
        email.add_attachment(docx.getvalue(), maintype='application', subtype='octet-stream', filename='scope.docx')
        content = build_openai_content('', '', [UploadedDocument('request.eml', email.as_bytes()),
                    UploadedDocument('cost.xlsx', xlsx.getvalue())])
        for marker in ('WORD-MARKER', 'EXCEL-MARKER', '125.5', 'EML-MARKER'):
            self.assertIn(marker, content[0]['text'])

    def test_tiff_is_converted_to_supported_image_input(self):
        data = io.BytesIO()
        Image.new('RGB', (20, 20), 'white').save(data, format='TIFF')
        content = build_openai_content('', '', [UploadedDocument('scan.tiff', data.getvalue())])
        self.assertTrue(content[1]['image_url'].startswith('data:image/png;base64,'))

    def test_corrupt_word_names_failed_file(self):
        with self.assertRaisesRegex(ValueError, 'broken.docx'):
            build_openai_content('', '', [UploadedDocument('broken.docx', b'bad')])

    def test_legacy_word_and_excel_content_reach_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            word = Document()
            word.add_paragraph('LEGACY-WORD-MARKER')
            word.save(root / 'request.docx')
            book = Workbook()
            book.active.append(['LEGACY-EXCEL-MARKER', 345.5])
            book.save(root / 'cost.xlsx')
            for source, target in [('request.docx', 'doc'), ('cost.xlsx', 'xls')]:
                result = subprocess.run([find_soffice(), '--headless',
                    '-env:UserInstallation=' + (root / 'profile').as_uri(),
                    '--convert-to', target, '--outdir', str(root), str(root / source)],
                    capture_output=True, timeout=120)
                self.assertEqual(result.returncode, 0, result.stderr)
            documents = [UploadedDocument(name, (root / name).read_bytes())
                         for name in ('request.doc', 'cost.xls')]
            content = build_openai_content('', '', documents)
            for marker in ('LEGACY-WORD-MARKER', 'LEGACY-EXCEL-MARKER', '345.5'):
                self.assertIn(marker, content[0]['text'])

    def test_pdf_text_and_binary_both_reach_analysis(self):
        from reportlab.pdfgen.canvas import Canvas
        buffer = io.BytesIO()
        canvas = Canvas(buffer)
        canvas.drawString(72, 720, 'PDF-MARKER')
        canvas.save()
        content = build_openai_content('', '', [UploadedDocument('report.pdf', buffer.getvalue())])
        self.assertIn('PDF-MARKER', content[0]['text'])
        self.assertEqual(content[1]['type'], 'input_file')
        self.assertTrue(content[1]['file_data'].startswith('data:application/pdf;base64,'))

    def test_oversized_file_does_not_silently_skip_analysis(self):
        from unittest.mock import patch
        with patch('proposal_app.file_ingest.MAX_FILE_BYTES', 5):
            with self.assertRaisesRegex(ValueError, 'large.txt.*20 MB'):
                build_openai_content('', '', [UploadedDocument('large.txt', b'123456')])

    def test_unknown_file_is_reported_as_not_analyzed(self):
        content = build_openai_content('', '', [UploadedDocument('unknown.xyz', b'unknown')])
        self.assertIn('unknown.xyz', content[0]['text'])
        self.assertIn('not analyzed', content[0]['text'])

    def test_macro_enabled_word_content_is_read_without_running_macros(self):
        from zipfile import ZipFile
        word = Document()
        word.add_paragraph('DOCM-MARKER')
        original = io.BytesIO()
        word.save(original)
        output = io.BytesIO()
        with ZipFile(original) as source, ZipFile(output, 'w') as target:
            for name in source.namelist():
                data = source.read(name)
                if name == '[Content_Types].xml':
                    data = data.replace(
                        b'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml',
                        b'application/vnd.ms-word.document.macroEnabled.main+xml')
                target.writestr(name, data)
        content = build_openai_content('', '', [UploadedDocument('scope.docm', output.getvalue())])
        self.assertIn('DOCM-MARKER', content[0]['text'])

    def test_unicode_excel_text_export(self):
        content = build_openai_content('', '', [UploadedDocument('notes.tsv', '工作\t2'.encode('utf-16'))])
        self.assertIn('工作\t2', content[0]['text'])
