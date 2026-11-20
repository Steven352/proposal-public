import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from proposal_app.models import ReferenceMatch


class WorkflowGuideTest(unittest.TestCase):
    def test_editor_does_not_show_private_reference_matches(self):
        match = ReferenceMatch(
            filename="Private Historical Proposal.docx", project_type="building",
            methods=["drilling"], score=1, has_cost_table=True, sections={},
        )
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "streamlit_app.py"))
        app.secrets["GITHUB_LIBRARY_TOKEN"] = ""
        with (
            patch("proposal_app.secure_bundle.ensure_private_assets"),
            patch("proposal_app.knowledge.retrieve_references", return_value=[match]),
        ):
            app.run()
            app.text_input[0].set_value("805443")
            app.button[0].click().run()
            next(button for button in app.button if button.label == "Enter manually").click().run()

        self.assertFalse(app.exception)
        self.assertTrue(any(button.label == "Generate Word proposal" for button in app.button))
        self.assertFalse(any("Historical proposal matches" == item.label for item in app.expander))
        self.assertFalse(any(match.filename in item.value for item in app.markdown))
