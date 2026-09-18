import unittest

from proposal_app.ai import DRAFT_INSTRUCTIONS


GROUNDWATER_SCOPE = (
    "Installation of 25 mm diameter standpipe piezometers in all boreholes, backfilled with "
    "cuttings and capped with bentonite. Groundwater readings will be taken at the end of "
    "drilling and during one follow-up visit two weeks after the field program."
)


class GroundwaterScopeInstructionTest(unittest.TestCase):
    def test_uses_required_groundwater_scope_wording(self):
        normalized_instructions = " ".join(DRAFT_INSTRUCTIONS.split())
        self.assertIn(GROUNDWATER_SCOPE, normalized_instructions)

    def test_includes_borehole_scope_without_monitoring_selection(self):
        normalized_instructions = " ".join(DRAFT_INSTRUCTIONS.split())
        self.assertIn(
            "Every proposal with boreholes must include this standard scope, even when groundwater monitoring is not selected",
            normalized_instructions,
        )


if __name__ == "__main__":
    unittest.main()
