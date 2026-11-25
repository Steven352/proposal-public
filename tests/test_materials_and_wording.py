import io
import unittest

from docx import Document

from proposal_app import document_builder
from proposal_app.costs import merge_standard_cost_items, normalize_cost_items, standard_cost_items
from proposal_app.fixed_scope import (
    FIELD_PROGRAM_INTRO,
    FIELD_PROGRAM_INTRO_MIXED,
    FIELD_PROGRAM_INTRO_TEST_PITS,
    MIXED_SCOPE_CLOSING,
    TEST_PIT_GROUNDWATER_SCOPE,
    TEST_PIT_SCOPE_CLOSING,
)
from proposal_app.models import CostLineItem, InvestigationDepthGroup, ProposalFacts
from test_standard_document import sample_draft

MATERIALS = "Materials Testing - Concrete Testing"
MATERIALS_QUANTITIES = {
    "Technician (III)": 40, "Concrete Cylinder (Breaks)": 20, "Concrete Cylinders (Prep)": 20,
    "Mileage Surcharge": 4000, "Senior Professional": 1,
}

# The user's approved wording, verbatim.
APPROVED_INTRODUCTION = (
    "At the request of Rajdeep Singh Toor of Celestial Living Inc. (Client), Almor Testing Services "
    "Ltd. (Almor) is pleased to provide this proposal for geotechnical engineering services for the "
    "above-noted project. Almor understands that the proposed development consists of a 24-unit "
    "townhouse development at 346 Parkview Estates, Strathmore, Alberta, with three levels of above "
    "grade and a basement level, associated parking. The purpose of the investigation is to "
    "characterize the subsurface soil and groundwater conditions at the site and provide geotechnical "
    "recommendations to support construction of the proposed development."
)
APPROVED_COST_INTRO = (
    "Based on the information provided by the Client, Almor provides the following estimated cost to "
    "complete the proposed geotechnical scope of work."
)


def priced_items(materials=True):
    items = standard_cost_items()
    for item in items:
        if item.section == MATERIALS and materials:
            item.estimate = MATERIALS_QUANTITIES[item.item]
        elif item.item == "Moisture Content Tests":
            item.estimate = 10
        item.total = round(item.estimate * item.rate, 2)
    return items


def facts(**changes):
    return ProposalFacts(
        proposal_number="P026-TEST", proposal_date="2026-11-19",
        client_name="Celestial Living Inc.", contact_name="Rajdeep Singh Toor",
        project_name="346 Parkview Estates",
        borehole_program=[InvestigationDepthGroup(quantity=4, termination_depth_m=6)],
        cost_items=priced_items(),
    ).model_copy(update=changes)


def build(proposal_facts, draft=None):
    data, _ = document_builder.build_standard_docx(proposal_facts, draft or sample_draft(), False)
    return Document(io.BytesIO(data))


def field_program(document):
    return [p.text for p in document_builder.paragraphs_between(
        document, "Geotechnical Field Program", "Cost of Geotechnical Services")]


class MaterialsTestingCostTest(unittest.TestCase):
    def test_catalog_has_materials_section_with_zero_quantities(self):
        items = [item for item in standard_cost_items() if item.section == MATERIALS]
        self.assertEqual([item.item for item in items], list(MATERIALS_QUANTITIES))
        self.assertEqual([item.unit for item in items], ["hr", "Ea", "Ea", "km", "hr"])
        self.assertTrue(all(item.estimate == 0 for item in items))
        self.assertEqual(normalize_cost_items(standard_cost_items()).section_totals[MATERIALS], 0.0)

    def test_materials_section_is_subtotalled_and_added_to_the_estimate(self):
        summary = normalize_cost_items(priced_items())
        self.assertEqual(summary.warnings, [])
        self.assertEqual(summary.section_totals[MATERIALS], 9850.0)
        self.assertEqual(summary.final_total, 9850.0 + 82.5)

    def test_merging_extracted_items_respects_sections(self):
        extracted = [CostLineItem(section="Engineering Analysis & Report Preparation",
                                  item="Senior Professional", unit="hr", estimate=2, rate=250, total=500)]
        merged = merge_standard_cost_items(extracted)
        engineering = [i for i in merged if i.section.startswith("Engineering") and i.item == "Senior Professional"]
        materials = [i for i in merged if i.section == MATERIALS and i.item == "Senior Professional"]
        self.assertEqual([i.estimate for i in engineering], [2])
        self.assertEqual([i.estimate for i in materials], [0])

    def test_word_table_shows_materials_section_with_merged_title_and_total(self):
        table = build(facts()).tables[0]
        rows = [[cell.text for cell in row.cells] for row in table.rows]
        title = next(i for i, row in enumerate(rows) if row[0] == MATERIALS)
        self.assertEqual(rows[title], [MATERIALS] * 6)  # One cell spanning the whole row.
        self.assertEqual(rows[title + 4][:4], ["Mileage Surcharge", "10 trips, 400km/trip", "km", "4000"])
        self.assertEqual(rows[title + 6][4:], ["Subtotal", "$9,850.00"])
        self.assertEqual(rows[-1][3:], ["Estimated Cost", "Estimated Cost", "$9,932.50"])

    def test_zero_materials_rows_are_omitted_from_word(self):
        document = build(facts(cost_items=priced_items(materials=False)))
        text = " ".join(cell.text for row in document.tables[0].rows for cell in row.cells)
        self.assertNotIn(MATERIALS, text)


class ApprovedWordingTest(unittest.TestCase):
    def test_introduction_keeps_template_and_changes_client_and_description_only(self):
        draft = sample_draft().model_copy(update={"introduction": (
            "At the request of Someone Else (Client), Almor is happy to help on the above-noted project. "
            "Almor understands that the proposed development consists of a 24-unit townhouse development "
            "at 346 Parkview Estates, Strathmore, Alberta, with three levels of above grade and a basement "
            "level, associated parking. The purpose of the investigation is something rewritten."
        )})
        paragraphs = [p.text for p in build(facts(), draft).paragraphs]
        self.assertEqual(paragraphs[paragraphs.index("Introduction") + 1], APPROVED_INTRODUCTION)

    def test_introduction_without_contact_names_the_client_only(self):
        proposal_facts = facts(contact_name="")
        text = document_builder.introduction_text(proposal_facts, sample_draft())
        self.assertTrue(text.startswith(
            "At the request of Celestial Living Inc. (Client), Almor Testing Services Ltd. (Almor)"))

    def test_borehole_field_program_and_fixed_sections(self):
        document = build(facts())
        scope = field_program(document)
        self.assertEqual(scope[0], FIELD_PROGRAM_INTRO)
        self.assertIn("Coordinate utility locates and secondary utility clearance before drilling.", scope)
        self.assertIn("including relatively undisturbed Shelby tube soil samples", scope[6])
        paragraphs = [p.text for p in document.paragraphs]
        self.assertEqual(paragraphs[paragraphs.index("Cost of Geotechnical Services") + 1], APPROVED_COST_INTRO)

    def test_test_pit_field_program_has_no_drilling_clauses(self):
        scope = field_program(build(facts(
            borehole_program=[], investigation_methods=["test pits"],
            test_pit_program=[InvestigationDepthGroup(quantity=1, termination_depth_m=3)])))
        self.assertEqual(scope[0], FIELD_PROGRAM_INTRO_TEST_PITS)
        self.assertEqual(scope[3], (
            "Field examination and excavation/sampling of one (1) test pit to a minimum depth of 3.0 m "
            "below existing grade, refusal, or to depths sufficient to establish subsurface conditions, "
            "whichever is the least. Test pit locations will be selected based on site access and "
            "utility considerations."))
        self.assertIn("Coordinate utility locates and secondary utility clearance before test pit excavation.", scope)
        self.assertIn(TEST_PIT_GROUNDWATER_SCOPE, scope)
        self.assertEqual(scope[-1], TEST_PIT_SCOPE_CLOSING)
        text = " ".join(scope).lower()
        for drilling in ("borehole", "drilling", "drill", "spt", "shelby", "piezometer"):
            self.assertNotIn(drilling, text)

    def test_mixed_field_program_describes_both_methods(self):
        scope = field_program(build(facts(
            test_pit_program=[InvestigationDepthGroup(quantity=2, termination_depth_m=3)])))
        self.assertEqual(scope[0], FIELD_PROGRAM_INTRO_MIXED)
        self.assertIn("four (4) boreholes to a minimum depth of 6.0 m and excavation/sampling of two (2) "
                      "test pits to a minimum depth of 3.0 m", scope[3])
        self.assertIn("Borehole and test pit locations", scope[3])
        self.assertIn(TEST_PIT_GROUNDWATER_SCOPE, scope)
        self.assertTrue(any(text.startswith("Installation of 25 mm diameter standpipe") for text in scope))
        self.assertEqual(scope[-1], MIXED_SCOPE_CLOSING)


if __name__ == "__main__":
    unittest.main()
