import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from proposal_app import complete_package
from proposal_app.models import ProposalFacts
from tests.test_uploaded_proposal_fields import reviewed_proposal


class CompletePackageWorkflowTest(unittest.TestCase):
    def test_pdf_and_email_are_available_without_archiving(self):
        facts = ProposalFacts(
            proposal_number="P026-200",
            project_name="Warehouse",
            client_name="Client",
            contact_email="client@example.com",
        )
        with (
            patch.object(complete_package, "build_complete_pdf_package", return_value=(b"pdf", "package.pdf")),
            patch.object(complete_package, "save_pdf_source_to_library") as save,
        ):
            output = complete_package.generate_complete_package(
                b"original", "reviewed.docx", facts, "Scope", 100, False, object(),
                archive_source=False,
            )

        self.assertEqual(output["pdf"], b"pdf")
        self.assertIn("P026-200", output["email_subject"])
        self.assertIn("client@example.com", output["email_body"])
        self.assertFalse(output["signed"])
        self.assertEqual(output["library_path"], "")
        self.assertEqual(output["library_error"], "")
        save.assert_not_called()

    def test_archives_original_after_conversion_and_reports_storage_failure_with_pdf(self):
        facts = ProposalFacts(proposal_number='P026-200', project_name='Example', client_name='Client')
        with patch.object(
            complete_package, 'build_complete_pdf_package', return_value=(b'pdf', 'package.pdf')
        ) as convert, patch.object(
            complete_package, 'save_pdf_source_to_library', side_effect=RuntimeError('Storage unavailable')
        ) as save:
            output = complete_package.generate_complete_package(b'original', 'reviewed.docx', facts, 'Scope', 100, False, object())
        self.assertEqual(output['pdf'], b'pdf')
        self.assertEqual(output['word'], b'original')
        self.assertIn('Storage unavailable', output['library_error'])
        self.assertEqual(convert.call_args.args[0], b'original')
        self.assertEqual(save.call_args.args[2], b'original')

    def test_conversion_failure_does_not_archive(self):
        with patch.object(
            complete_package, 'build_complete_pdf_package', side_effect=RuntimeError('Conversion failed')
        ), patch.object(complete_package, 'save_pdf_source_to_library') as save:
            with self.assertRaisesRegex(RuntimeError, 'Conversion failed'):
                complete_package.generate_complete_package(b'original', 'reviewed.docx', ProposalFacts(), '', 100, False, object())
        save.assert_not_called()

    def test_unconfigured_library_keeps_pdf_and_explains_missing_save(self):
        with patch.object(
            complete_package, 'build_complete_pdf_package', return_value=(b'pdf', 'package.pdf')
        ):
            output = complete_package.generate_complete_package(b'original', 'reviewed.docx', ProposalFacts(), '', 100, False, None)
        self.assertEqual(output['pdf'], b'pdf')
        self.assertEqual(output['library_path'], '')
        self.assertIn('GITHUB_LIBRARY_TOKEN', output['library_error'])


class StandardLibraryAccessTest(unittest.TestCase):
    def test_standard_login_keeps_pdf_workflow_and_hides_library_tools(self):
        with patch("proposal_app.secure_bundle.ensure_private_assets"):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "streamlit_app.py"))
            app.secrets["APP_ACCESS_CODE"] = "fixture-standard"
            app.secrets["GITHUB_LIBRARY_TOKEN"] = ""
            app.run()
            app.text_input[0].set_value("fixture-standard")
            app.button[0].click().run()

        self.assertFalse(app.exception)
        self.assertIn("Generate PDF and email", [button.label for button in app.button])
        self.assertNotIn("Add Final Proposal to Library", [button.label for button in app.button])
        headings = [heading.value for heading in app.subheader]
        self.assertNotIn("5. Add Final Proposal to Library", headings)
        self.assertNotIn("Repeated edits awaiting rule approval", headings)

    @unittest.skipUnless(hasattr(AppTest, "file_uploader"), "requires AppTest file upload support")
    def test_standard_reviewed_upload_does_not_archive_with_connected_library(self):
        with (
            patch("proposal_app.secure_bundle.ensure_private_assets"),
            patch("proposal_app.github_library.sync_runtime_knowledge"),
            patch.object(complete_package, "build_complete_pdf_package", return_value=(b"pdf", "package.pdf")),
            patch.object(complete_package, "save_pdf_source_to_library") as save,
        ):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "streamlit_app.py"))
            app.secrets["APP_ACCESS_CODE"] = "fixture-standard"
            app.secrets["GITHUB_LIBRARY_TOKEN"] = "fixture-library-token"
            app.run()
            app.text_input[0].set_value("fixture-standard")
            app.button[0].click().run()
            app.file_uploader(key="complete_pdf_word_upload").set_value(
                ("P026-200 Road Assessment.docx", reviewed_proposal("Example Engineering Ltd."),
                 "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            ).run()
            next(button for button in app.button if button.label == "Generate PDF and email").click().run()

        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        output = app.session_state["complete_pdf_output"]
        self.assertEqual(output["pdf"], b"pdf")
        self.assertFalse(output["signed"])
        self.assertIn("Road Assessment", output["email_subject"])
        self.assertNotIn("library_state", app.session_state)
        save.assert_not_called()
