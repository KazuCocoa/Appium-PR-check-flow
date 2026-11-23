import io
import json
import os
from contextlib import redirect_stderr
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

    def test_diagnostics_capture_decisions_without_model_text(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"REVIEW_DEBUG": "1"}), redirect_stderr(output):
            self.review({"findings": [FINDING]}, {"unexpected": True})
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(len({row["run_id"] for row in rows}), 1)
        calls = [row["stage"] for row in rows if row["event"] == "llm.request"]
        self.assertEqual(calls, ["scout", "reviewer", "verifier"])
        parsed = [row["valid"] for row in rows if row["event"] == "json.parsed"]
        self.assertEqual(parsed, [True, False])
        self.assertEqual(rows[-1]["invalid_stages"], ["verifier"])
        self.assertNotIn(FINDING["quote"], output.getvalue())

    def test_full_log_matches_provider_messages_and_raw_responses(self):
        output = io.StringIO()
        responses = ["調査\n結果", " invalid JSON\n", '{"findings":[]}']
        with (patch.dict(os.environ, {"REVIEW_DEBUG": "full"}), redirect_stderr(output),
              patch.object(flow, "collect_evidence", return_value=evidence()),
              patch.object(flow, "ollama_chat", side_effect=[{"content": r} for r in responses]) as chat):
            flow.review_pr("appium/appium", 12)
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        requests = [row for row in rows if row["event"] == "llm.request"]
        self.assertEqual(len(requests), 3)
        for logged, call in zip(requests, chat.call_args_list):
            system, user = call.args[0]
            self.assertEqual(logged["instructions"], system["content"])
            self.assertEqual(logged["input"], user["content"])
        self.assertEqual([row["response"] for row in rows if row["event"] == "llm.response"], responses)

    def test_invalid_response_is_visible(self):
        report = self.review({"findings": []}, {"unexpected": True})
        self.assertIn("verifier returned an invalid response", report["markdown"])

    def test_malformed_anchor_rejected(self):
        accepted, rejected = flow.validate_findings({"findings": [{**FINDING, "file": []}]}, evidence())
        self.assertFalse(accepted)
        self.assertEqual(len(rejected), 1)
