import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class PersonnelOptionTest(unittest.TestCase):
    def setUp(self):
        for target, kwargs in (
            ("proposal_app.secure_bundle.ensure_private_assets", {}),
            ("proposal_app.knowledge.load_index", {"return_value": []}),
        ):
            mocked = patch(target, **kwargs)
            mocked.start()
            self.addCleanup(mocked.stop)

    def manual_editor(self):
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / "streamlit_app.py"),
            default_timeout=20,
        )
        app.session_state["access_granted"] = True
        app.session_state["access_role"] = "standard"
        app.run()
        next(button for button in app.button if button.label == "Enter manually").click().run()
        self.assertFalse(app.exception)
        return app

    def test_personnel_option_is_checked_directly_above_word_generation(self):
        app = self.manual_editor()
        option = next(
            (item for item in app.checkbox
             if item.label == "Include Proposed Project Personnel section"),
            None,
        )
        self.assertIsNotNone(option)
        self.assertTrue(option.value)
        children = list(app.main.children.values())
        generate_index = next(
            index for index, item in enumerate(children)
            if getattr(item, "label", "") == "Generate Word proposal"
        )
        self.assertEqual(children[generate_index - 1].label, option.label)

    def test_personnel_option_can_be_unchecked_and_retains_selection(self):
        app = self.manual_editor()
        option = next(
            (item for item in app.checkbox
             if item.label == "Include Proposed Project Personnel section"),
            None,
        )
        self.assertIsNotNone(option)
        option.uncheck().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.checkbox(key="include_proposed_project_personnel").value)
        app.run()
        self.assertFalse(app.checkbox(key="include_proposed_project_personnel").value)


if __name__ == "__main__":
    unittest.main()
