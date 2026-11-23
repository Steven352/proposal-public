import unittest

import pandas as pd

from proposal_app.draft_state import DRAFT_SCHEMA, cost_frame_from_rows, export_draft, import_draft
from tests.test_standard_document import sample_facts


class DraftStateTest(unittest.TestCase):
    def test_export_import_round_trip_preserves_editable_progress(self):
        facts = sample_facts()
        payload = export_draft(
            facts=facts,
            scope_frame=pd.DataFrame([{"Category": "Access note", "Value": "Use east gate"}]),
            cost_frame=pd.DataFrame([{"Section": "Field Program", "Item": "Excavator", "Description": "Field", "Unit": "hr", "Est.": 3, "Rate": 150.0, "Total": 450.0}]),
            request_email="Original request",
            notes="Follow up with client",
            include_proposed_project_personnel=False,
        )
        self.assertEqual(payload["schema"], DRAFT_SCHEMA)
        restored = import_draft(payload)
        self.assertEqual(restored.facts.proposal_number, "P026-999")
        self.assertEqual(restored.scope_rows[0]["Value"], "Use east gate")
        self.assertEqual(restored.cost_rows[0]["Rate"], 150.0)
        self.assertEqual(restored.request_email, "Original request")
        self.assertFalse(restored.include_proposed_project_personnel)

    def test_restored_cost_frame_keeps_numeric_columns_editable(self):
        frame = pd.DataFrame([
            {"Section": "Field Program", "Item": "A", "Description": "", "Unit": "hr", "Est.": None, "Rate": 185.0, "Total": None},
            {"Section": "Field Program", "Item": "B", "Description": None, "Unit": "Ea", "Est.": 2, "Rate": None, "Total": 0.0},
        ])
        payload = export_draft(facts=sample_facts(), scope_frame=None, cost_frame=frame)
        restored = cost_frame_from_rows(import_draft(payload).cost_rows)
        for column in ("Est.", "Rate", "Total"):
            self.assertEqual(str(restored[column].dtype), "float64")
        self.assertEqual(list(restored.columns), ["Section", "Item", "Description", "Unit", "Est.", "Rate", "Total"])
        self.assertEqual(restored.loc[1, "Description"], "")

    def test_import_rejects_unknown_schema_and_missing_facts(self):
        with self.assertRaises(ValueError):
            import_draft({"schema": "other", "facts": {}})
        with self.assertRaises(ValueError):
            import_draft({"schema": DRAFT_SCHEMA})


if __name__ == "__main__":
    unittest.main()
