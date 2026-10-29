import json
import subprocess
import sys
import unittest
from pathlib import Path


REPLACE_SCRIPT = """
import json
import sys
from lxml import etree
from proposal_app.document_builder import replace_text_across_nodes

case = json.loads(sys.argv[1])
nodes = []
for part in case["parts"]:
    node = etree.Element("text")
    node.text = part
    nodes.append(node)
changed = replace_text_across_nodes(nodes, case["old"], case["new"])
print(json.dumps({"changed": changed, "text": "".join(node.text or "" for node in nodes)}))
"""


class TextReplacementTest(unittest.TestCase):
    def replace_in_bounded_process(self, parts, old, new):
        result = subprocess.run(
            [sys.executable, "-c", REPLACE_SCRIPT,
             json.dumps({"parts": parts, "old": old, "new": new})],
            cwd=Path(__file__).resolve().parents[1],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        return json.loads(result.stdout)

    def test_unchanged_value_finishes_without_modifying_split_runs(self):
        result = self.replace_in_bounded_process(["Current ", "Client"], "Current Client", "Current Client")
        self.assertFalse(result["changed"])
        self.assertEqual(result["text"], "Current Client")

    def test_replacement_containing_original_text_replaces_each_original_match_once(self):
        result = self.replace_in_bounded_process(["Cli", "ent / Cl", "ient"], "Client", "Client Ltd.")
        self.assertTrue(result["changed"])
        self.assertEqual(result["text"], "Client Ltd. / Client Ltd.")


if __name__ == "__main__":
    unittest.main()
