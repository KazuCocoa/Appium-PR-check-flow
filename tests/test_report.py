import json
import unittest
from unittest.mock import patch

import review_flow as flow
from test_review_flow import FINDING, evidence


class ReportTests(unittest.TestCase):
    def review(self, reviewer, verifier):
        replies = iter(["scout", json.dumps(reviewer), json.dumps(verifier)])
        with patch.object(flow, "collect_evidence", return_value=evidence()):
            return flow.review_pr("appium/appium", 12, role_runner=lambda *_: next(replies))

    def test_only_retained_statements_reach_markdown(self):
        observation = {key: FINDING[key] for key in ("file", "line", "quote")}
        observation["observation"] = "The added call receives user_input."
        original = {"findings": [FINDING], "observations": [observation]}
        report = self.review(original, {**original, "summary": "All tests passed",
                                        "findings": [{**FINDING, "issue": "Replacement claim"}]})
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["observations"], [observation])
        self.assertIn(observation["observation"], report["markdown"])
        self.assertNotIn("All tests passed", report["markdown"])
        self.assertNotIn("Replacement claim", report["markdown"])
        self.assertIn("src/test.py:11", report["markdown"])
        self.assertEqual(report["trace"], ["evidence", "scout", "reviewer", "verifier", "report_writer"])

    def test_invalid_response_is_visible(self):
        report = self.review({"findings": []}, {"unexpected": True})
        self.assertIn("verifier returned an invalid response", report["markdown"])

    def test_malformed_anchor_rejected(self):
        accepted, rejected = flow.validate_findings({"findings": [{**FINDING, "file": []}]}, evidence())
        self.assertFalse(accepted)
        self.assertEqual(len(rejected), 1)
