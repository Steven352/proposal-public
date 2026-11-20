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
        app.secrets['APP_ACCESS_CODE'] = 'standard-test-code'
        app.secrets['GITHUB_LIBRARY_TOKEN'] = ''
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
        with patch.multiple(
            'proposal_app.access',
            _SIGNER_SALT=bytes.fromhex('d50f92a086d284fcd97e1fe176fd8810'),
            _SIGNER_VERIFIER=bytes.fromhex('726a3013a8bc7e4e5c8daac360416a8e113761bd53ca8fe123767452905d02b1'),
            create=True,
        ):
            app = self.login('authorized-test-code')
        self.assertTrue(any('Add signatures' in toggle.label for toggle in app.toggle))
        self.assertEqual(app.session_state['access_role'], 'signer')

    def test_retired_signer_code_is_rejected_even_as_a_configured_standard_code(self):
        app = self.app()
        app.secrets['APP_ACCESS_CODE'] = 'retired-test-code'
        app.run()
        app.text_input[0].set_value('retired-test-code')
        with patch(
            'proposal_app.access._RETIRED_SIGNER_DIGEST',
            '2e324504d6972afec648357eadaadd0a6309f46c2e05941765a0c0d5e5d494f9',
            create=True,
        ):
            app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.assertEqual(app.text_input[0].label, 'Access code')

    def test_old_authenticated_session_must_log_in_again(self):
        app = self.app()
        app.session_state['access_granted'] = True
        app.session_state['complete_pdf_signatures'] = True
        app.run()
        self.assertEqual(app.text_input[0].label, 'Access code')
        self.assertFalse(any('Add signatures' in toggle.label for toggle in app.toggle))

    def test_pre_rotation_signing_session_must_reauthenticate(self):
        app = self.app()
        app.session_state['access_granted'] = True
        app.session_state['access_role'] = 'signer'
        app.session_state['complete_pdf_output'] = {'signed': True, 'source_key': 'old-upload'}
        app.session_state['library_final_confirmed'] = True
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.text_input[0].label, 'Access code')
        self.assertNotIn('complete_pdf_output', app.session_state)
        self.assertNotIn('library_final_confirmed', app.session_state)

    def test_switch_access_clears_protected_state(self):
        app = self.login('805443')
        app.session_state['complete_pdf_output'] = {'signed': True}
        app.session_state['library_final_confirmed'] = True
        app.session_state['library_state'] = {'rules': []}
        next(button for button in app.button if button.label == 'Switch access code').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.text_input[0].label, 'Access code')
        for key in ('access_role', 'complete_pdf_output', 'library_final_confirmed', 'library_state'):
            self.assertNotIn(key, app.session_state)

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
