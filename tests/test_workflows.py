import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import workflows
import web
from test_review_flow import evidence, FINDING


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(web.app)
        self.request = dict(name="Example", steps=["tests", "compatibility"], repo="owner/repo", number=1)

    def test_invalid_plan_rejected_before_evidence(self):
        with patch.object(workflows, "collect_evidence") as fetch:
            for steps in ([], ["new role"], ["tests", "tests"]):
                self.assertEqual(self.client.post("/api/workflows/run",
                                 json={**self.request, "steps": steps}).status_code, 422)
            fetch.assert_not_called()

    def run_plan(self, replies):
        snapshot = {**evidence(), "pr_metadata": {"title": "Example"}}
        with patch.object(workflows, "collect_evidence", return_value=snapshot) as fetch, patch.object(
                workflows, "ask_role", side_effect=replies) as model:
            response = self.client.post("/api/workflows/run", json=self.request)
        fetch.assert_called_once()
        events = [json.loads(line) for line in response.iter_lines()]
        return events, model

    def test_selected_order_and_validated_handoff(self):
        events, model = self.run_plan([json.dumps({"findings": [FINDING, {**FINDING, "line": -1}]}),
                                       '{"findings":[]}'])
        self.assertEqual([e["stage"] for e in events[:-1]], ["evidence", *self.request["steps"], "report_writer"])
        result = events[-1]["result"]
        self.assertEqual(result["status"], "completed")
        self.assertEqual(model.call_args_list[1].args[-1]["previous"]["findings"], [FINDING])
        self.assertEqual(result["rejected_count"], 1)
        self.assertEqual(result["workflow"]["steps"], self.request["steps"])

    def test_invalid_output_stops_dependents_and_keeps_inspection(self):
        events, model = self.run_plan(["invalid"])
        result = events[-1]["result"]
        self.assertEqual(model.call_count, 1)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["stages"][0]["response"], "invalid")
