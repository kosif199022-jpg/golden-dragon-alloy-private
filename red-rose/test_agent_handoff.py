"""Guard the agent handoff against fabricated historical question coverage."""
import json
import re
import unittest
from pathlib import Path

DIR = Path(__file__).resolve().parent


class AgentHandoffContractTests(unittest.TestCase):
    def test_agent_entrypoint_files_present(self):
        for name in ("AGENTS.md", "NEXT_AGENT_HANDOFF.md",
                     "QUESTIONS_AND_ANSWERS.md", "QUESTION_COVERAGE.json"):
            with self.subTest(name=name):
                self.assertTrue((DIR / name).is_file(), name)
        root = DIR.parent / "AGENTS.md"
        self.assertTrue(root.is_file(), "Repository agents need a routing entrypoint")
        self.assertIn("red-rose/AGENTS.md", root.read_text(encoding="utf-8"))

    def test_historical_ranges_contiguous_without_fake_answers(self):
        data = json.loads((DIR / "QUESTION_COVERAGE.json").read_text(encoding="utf-8"))
        self.assertEqual(data["historical_design_target"], 1400)
        previous = 0
        for record in data["historical_question_status"]:
            self.assertEqual(record["start"], previous + 1)
            self.assertGreaterEqual(record["end"], record["start"])
            self.assertIn("not recovered", record["verbatim_questions_in_this_repo"])
            previous = record["end"]
        self.assertEqual(previous, 1400)
        self.assertFalse(data["original_1400_question_archive_complete"])
        self.assertFalse(data["measured_implementation_at_v17"]["all_1400_implemented"])

    def test_grounded_qa_summary_count(self):
        markdown = (DIR / "QUESTIONS_AND_ANSWERS.md").read_text(encoding="utf-8")
        data = json.loads((DIR / "QUESTION_COVERAGE.json").read_text(encoding="utf-8"))
        ids = re.findall(r"^### (A\d{2}) — ", markdown, flags=re.MULTILINE)
        self.assertEqual(len(ids), data["confirmed_answer_paraphrases"])
        self.assertEqual(len(ids), len(set(ids)), "Duplicate question IDs")
        self.assertEqual(ids, [f"A{i:02d}" for i in range(1, len(ids)+1)])
        self.assertIn("ليست", markdown)
        for source in ("**U:**", "**R:**", "**O:**", "**G:**"):
            self.assertIn(source, markdown)

    def test_handoff_explicitly_requires_evidence(self):
        handoff = (DIR / "NEXT_AGENT_HANDOFF.md").read_text(encoding="utf-8")
        agents = (DIR / "AGENTS.md").read_text(encoding="utf-8")
        for item in ("capability_runtime.REGISTRY", "QUESTION_COVERAGE.json",
                     "unittest discover", "PR"):
            with self.subTest(item=item):
                self.assertIn(item, handoff + agents)
        self.assertIn("25,675", handoff)
        self.assertIn("154", handoff)


if __name__ == "__main__":
    unittest.main()
