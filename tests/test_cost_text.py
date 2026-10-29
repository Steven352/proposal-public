import unittest

from proposal_app.costs import normalize_cost_items
from proposal_app.models import CostLineItem


class CostTextTest(unittest.TestCase):
    def normalize_repeatedly(self, label, description, expected_label, expected_description):
        items = [CostLineItem(
            section="Laboratory Testing Program", item=label, description=description,
            unit="Ea", estimate=2, rate=100, total=200,
        )]
        for iteration in range(3):
            with self.subTest(iteration=iteration):
                summary = normalize_cost_items(items)
                self.assertEqual(len(summary.items), 1)
                self.assertEqual(summary.items[0].item, expected_label)
                self.assertEqual(summary.items[0].description, expected_description)
                self.assertEqual(summary.final_total, 200)
                self.assertFalse(summary.warnings)
                items = summary.items

    def test_canonical_laboratory_names_do_not_grow_when_normalized_again(self):
        for canonical in ("Hydrometer Analysis", "Organic Content Tests"):
            with self.subTest(label=canonical):
                self.normalize_repeatedly(canonical, f"Selected {canonical} samples", canonical,
                                          f"Selected {canonical} samples")

    def test_abbreviated_laboratory_aliases_expand_once(self):
        for alias, canonical in (
            ("Hydrometer", "Hydrometer Analysis"),
            ("Organic Content", "Organic Content Tests"),
        ):
            with self.subTest(label=alias):
                self.normalize_repeatedly(alias, f"Selected {alias} samples", canonical,
                                          f"Selected {canonical} samples")

    def test_existing_corrupted_catalog_labels_are_repaired_without_rewriting_prose(self):
        for corrupted, canonical in (
            ("Hydrometer Analysis Analysis", "Hydrometer Analysis"),
            ("Organic Content Tests Tests Tests", "Organic Content Tests"),
        ):
            with self.subTest(label=corrupted):
                prose = f"Client wording containing {corrupted} must remain intact."
                self.normalize_repeatedly(corrupted, prose, canonical, prose)

    def test_aliases_are_not_replaced_inside_other_words(self):
        self.normalize_repeatedly("Hydrometers", "Organic Contents", "Hydrometers", "Organic Contents")


if __name__ == "__main__":
    unittest.main()
