import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class SigningAccessTest(unittest.TestCase):
    def setUp(self):
        # Deployment assets and private library are not needed to test access/UI permissions.
        assets = patch('proposal_app.secure_bundle.ensure_private_assets')
        index = patch('proposal_app.knowledge.load_index', return_value=[])
        assets.start()
        index.start()
        self.addCleanup(assets.stop)
        self.addCleanup(index.stop)

    def app(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'streamlit_app.py'))
        app.secrets['APP_ACCESS_CODE'] = '805443'
        return app

    def login(self, code):
        app = self.app().run()
        app.text_input[0].set_value(code)
        app.button[0].click().run()
        self.assertFalse(app.exception)
        return app

    def test_standard_code_has_no_signature_toggle(self):
        app = self.login('805443')
        self.assertFalse(any('Add signatures' in toggle.label for toggle in app.toggle))

    def test_signer_code_has_signature_toggle(self):
        app = self.login('806573')
        self.assertTrue(any('Add signatures' in toggle.label for toggle in app.toggle))
        self.assertEqual(app.session_state['access_role'], 'signer')

    def test_old_authenticated_session_must_log_in_again(self):
        app = self.app()
        app.session_state['access_granted'] = True
        app.session_state['complete_pdf_signatures'] = True
        app.run()
        self.assertEqual(app.text_input[0].label, 'Access code')
        self.assertFalse(any('Add signatures' in toggle.label for toggle in app.toggle))

    def test_standard_session_discards_stale_signing_state(self):
        app = self.login('805443')
        app.session_state['complete_pdf_signatures'] = True
        app.session_state['complete_pdf_output'] = {'signed': True, 'source_key': 'old-upload', 'pdf': b'pdf', 'name': 'signed.pdf',
            'word': b'word', 'word_changed': False, 'email_subject': 'Proposal',
            'email_body': 'Attached is the proposal.', 'library_error': '', 'library_path': 'saved.docx'}
        app.run()
        self.assertFalse(app.exception)
        self.assertNotIn('complete_pdf_output', app.session_state)
        self.assertFalse(any('Add signatures' in toggle.label for toggle in app.toggle))
