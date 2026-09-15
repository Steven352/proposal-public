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

    def test_requires_groundwater_monitoring_before_adding_module(self):
        normalized_instructions = " ".join(DRAFT_INSTRUCTIONS.split())
        self.assertIn(
            "When groundwater monitoring is included in investigation_methods, use exactly:",
            normalized_instructions,
        )


if __name__ == "__main__":
    unittest.main()
