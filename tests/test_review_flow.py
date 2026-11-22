"""No-network tests for evidence collection, validation, and role orchestration."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import review_flow as flow

PATCH = "@@ -10,2 +10,3 @@\n before\n+unsafe_call(user_input)\n existing\n"


def evidence():
    return {
        "repo": "appium/appium", "number": 12, "head_sha": "abc",
        "files": [{
            "file": "src/test.py", "patch": PATCH,
            "patch_available": True, "patch_truncated": False,
        }],
        "coverage": {"complete": True, "ci_checked": False, "tests_executed": False},
    }


FINDING = {
    "file": "src/test.py", "line": 11, "quote": "unsafe_call(user_input)",
    "severity": "high", "issue": "Untrusted input reaches the unsafe call.",
}


class ReviewTests(unittest.TestCase):
    def test_diff_anchor_parser(self):
        self.assertEqual(flow.added_lines(PATCH)[11], "unsafe_call(user_input)")
        self.assertNotIn(10, flow.added_lines(PATCH))

    def test_accepts_exact_anchor(self):
        accepted, rejected = flow.validate_findings({"findings": [FINDING]}, evidence())
        self.assertEqual(accepted, [FINDING])
        self.assertEqual(rejected, [])

    def test_rejects_fabricated_line_or_quote(self):
        bad = [{**FINDING, "line": 999}, {**FINDING, "quote": "something else"}]
        accepted, rejected = flow.validate_findings({"findings": bad}, evidence())
        self.assertEqual(accepted, [])
        self.assertEqual(len(rejected), 2)

    def test_coverage_flags_author_claims_not_ci(self):
        pr = {"title": "Test", "body": "All 43 tests passed", "head": "abc", "changed_files": 1}
        files = [{"filename": "src/test.py", "status": "modified", "patch": PATCH}]
        with patch.object(flow, "get_pull_request", return_value=pr), patch.object(
            flow, "get_changed_files", return_value={"files": files, "complete": True}
        ):
            result = flow.collect_evidence("appium/appium", 12)
        self.assertTrue(result["coverage"]["complete"])
        self.assertFalse(result["coverage"]["ci_checked"])
        self.assertFalse(result["coverage"]["tests_executed"])
        self.assertEqual(result["pr_metadata"]["description_author_claim"], "All 43 tests passed")

    def test_incomplete_patch_flagged(self):
        pr = {"title": "Test", "body": "", "head": "abc", "changed_files": 1}
        files = [{"filename": "src/test.py", "patch": "X" * (flow.MAX_PATCH_PER_FILE + 10)}]
        with patch.object(flow, "get_pull_request", return_value=pr), patch.object(
            flow, "get_changed_files", return_value={"files": files, "complete": True}
        ):
            result = flow.collect_evidence("appium/appium", 12)
        self.assertFalse(result["coverage"]["complete"])
        self.assertEqual(result["coverage"]["patches_truncated"], ["src/test.py"])

    def test_skill_is_shared_file(self):
        text = flow.load_skill()
        self.assertIn("name: appium-pr-review", text)
        self.assertIn("Evidence protocol", text)

    def test_scout_reviewer_verifier_and_subset_gate(self):
        calls = []
        def role_runner(provider, role, skill, payload):
            calls.append(role)
            if "SCOUT" in role:
                return "Check input handling."
            return json.dumps({"findings": [FINDING], "summary": "One candidate"})

        with patch.object(flow, "collect_evidence", return_value=evidence()):
            result = flow.review_pr("appium/appium", 12, role_runner=role_runner)
        self.assertEqual(result["roles"], ["scout", "reviewer", "verifier"])
        self.assertEqual(len(calls), 3)
        self.assertEqual(result["findings"], [FINDING])
        self.assertFalse(result["verification"]["semantic_correctness_verified"])

    def test_verifier_cannot_invent_new_finding(self):
        sequence = iter([
            "Check line", json.dumps({"findings": [], "summary": "None"}),
            json.dumps({"findings": [FINDING], "summary": "Invented"}),
        ])
        with patch.object(flow, "collect_evidence", return_value=evidence()):
            result = flow.review_pr(
                "appium/appium", 12, role_runner=lambda *_: next(sequence)
            )
        self.assertEqual(result["findings"], [])

    def test_invalid_model_json_fails_closed(self):
        self.assertEqual(flow.parse_model_json("oops")["findings"], [])

    def test_role_ollama_disables_tools(self):
        with patch.object(flow, "ollama_chat", return_value={"content": "{}"}) as fake:
            result = flow.ask_role("ollama", "role", "skill", {"a": 1})
        self.assertEqual(result, "{}")
        self.assertFalse(fake.call_args.kwargs["tools_enabled"])


if __name__ == "__main__":
    unittest.main()
