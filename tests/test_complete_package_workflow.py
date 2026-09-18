import unittest
from unittest.mock import patch
from proposal_app import complete_package
from proposal_app.models import ProposalFacts


class CompletePackageWorkflowTest(unittest.TestCase):
    def test_archives_original_after_conversion_and_reports_storage_failure_with_pdf(self):
        facts = ProposalFacts(proposal_number='P026-200', project_name='Example', client_name='Client')
        with patch.object(complete_package, 'ensure_standpipe_scope', return_value=b'prepared'), patch.object(
            complete_package, 'build_complete_pdf_package', return_value=(b'pdf', 'package.pdf')
        ) as convert, patch.object(
            complete_package, 'save_pdf_source_to_library', side_effect=RuntimeError('Storage unavailable')
        ) as save:
            output = complete_package.generate_complete_package(b'original', 'reviewed.docx', facts, 'Scope', 100, False, object())
        self.assertEqual(output['pdf'], b'pdf')
        self.assertEqual(output['word'], b'prepared')
        self.assertIn('Storage unavailable', output['library_error'])
        self.assertEqual(convert.call_args.args[0], b'prepared')
        self.assertEqual(save.call_args.args[2], b'original')

    def test_conversion_failure_does_not_archive(self):
        with patch.object(complete_package, 'ensure_standpipe_scope', return_value=b'prepared'), patch.object(
            complete_package, 'build_complete_pdf_package', side_effect=RuntimeError('Conversion failed')
        ), patch.object(complete_package, 'save_pdf_source_to_library') as save:
            with self.assertRaisesRegex(RuntimeError, 'Conversion failed'):
                complete_package.generate_complete_package(b'original', 'reviewed.docx', ProposalFacts(), '', 100, False, object())
        save.assert_not_called()

    def test_unconfigured_library_keeps_pdf_and_explains_missing_save(self):
        with patch.object(complete_package, 'ensure_standpipe_scope', return_value=b'prepared'), patch.object(
            complete_package, 'build_complete_pdf_package', return_value=(b'pdf', 'package.pdf')
        ):
            output = complete_package.generate_complete_package(b'original', 'reviewed.docx', ProposalFacts(), '', 100, False, None)
        self.assertEqual(output['pdf'], b'pdf')
        self.assertEqual(output['library_path'], '')
        self.assertIn('GITHUB_LIBRARY_TOKEN', output['library_error'])
