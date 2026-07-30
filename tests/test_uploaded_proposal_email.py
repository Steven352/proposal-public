import unittest

from proposal_app.models import ProposalFacts
from proposal_app.uploaded_proposal import client_email_from_proposal


class ClientEmailTest(unittest.TestCase):
    def test_builds_email_from_reviewed_proposal_facts(self):
        facts = ProposalFacts(
            proposal_number="P026-140",
            project_name="Roxboro Road Geotechnical Assessment",
            contact_name="Peter Condic",
            contact_email="peter@example.com",
        )

        subject, body = client_email_from_proposal(facts)

        self.assertIn("P026-140", subject)
        self.assertIn("Roxboro Road Geotechnical Assessment", subject)
        self.assertIn("To: peter@example.com", body)
        self.assertIn("Hi Peter,", body)
        self.assertIn("sign and return the Work Authorization", body)


if __name__ == "__main__":
    unittest.main()
