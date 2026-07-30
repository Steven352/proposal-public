import unittest

from proposal_app.pdf_builder import find_signature_page


class FakePage:
    def __init__(self, text: str):
        self.text = text

    def extract_text(self):
        return self.text


class FakeReader:
    def __init__(self, *texts: str):
        self.pages = [FakePage(text) for text in texts]


class SignaturePageDetectionTest(unittest.TestCase):
    def test_finds_labels_when_pdf_splits_words_across_lines(self):
        reader = FakeReader("Introduction", "Prepared\nby     Reviewed\nBy")
        self.assertEqual(find_signature_page(reader), 1)

    def test_does_not_require_both_names_on_the_labelled_page(self):
        reader = FakeReader("Steven Lai", "Prepared by ... Reviewed By")
        self.assertEqual(find_signature_page(reader), 1)

    def test_uses_safe_partial_fallback_for_rendering_variations(self):
        reader = FakeReader("Introduction", "Prepared by\nSteven Lai")
        self.assertEqual(find_signature_page(reader), 1)

    def test_rejects_unrelated_person_name_mentions(self):
        with self.assertRaises(RuntimeError):
            find_signature_page(FakeReader("Steven Lai and Abdul Alemi"))


if __name__ == "__main__":
    unittest.main()
