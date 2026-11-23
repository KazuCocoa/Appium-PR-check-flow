import io
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent


class ToolTests(unittest.TestCase):
    def test_rejects_invalid_repository_without_network(self):
        with patch.object(agent, "urlopen") as request:
            self.assertIn("error", agent.list_pull_requests("https://example.com/a/b"))
            self.assertIn("error", agent.get_pull_request_diff("bad/repo/extra", 1))
            request.assert_not_called()

    def test_rejects_invalid_pr_number(self):
        with patch.object(agent, "urlopen") as request:
            self.assertIn("error", agent.get_pull_request("appium/appium", -1))
            self.assertIn("error", agent.get_pull_request_diff("appium/appium", True))
            request.assert_not_called()

    def test_strict_tool_schemas(self):
        for tool in agent.TOOLS:
            self.assertTrue(tool["strict"])
            self.assertFalse(tool["parameters"]["additionalProperties"])
            self.assertEqual(set(tool["parameters"]["required"]), set(tool["parameters"]["properties"]))

    def test_diff_is_bounded(self):
        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                return False
            def read(self, _limit):
                return b"x" * (agent.MAX_DIFF_CHARS + 5)

        with patch.object(agent, "urlopen", return_value=FakeResponse()):
            result = agent.get_pull_request_diff("appium/appium", 10)
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["diff"]), agent.MAX_DIFF_CHARS)

    def test_multiple_tool_roundtrips(self):
        class FakeResponses:
            def __init__(self):
                self.requests = []
            def create(self, **kwargs):
                self.requests.append(kwargs)
                if len(self.requests) == 1:
                    return SimpleNamespace(
                        id="one",
                        output=[SimpleNamespace(type="function_call", name="get_pull_request",
                                                arguments='{"repo":"appium/appium","number":10}', call_id="c1")],
                    )
                return SimpleNamespace(id="two", output=[], output_text="PR details returned")

        fake = SimpleNamespace(responses=FakeResponses())
        events = []
        with patch.dict(agent.HANDLERS, {"get_pull_request": lambda **kwargs: {"number": kwargs["number"]}}):
            answer = agent.run_agent("Check #10", client=fake, on_tool=lambda *e: events.append(e))
        self.assertEqual(answer, "PR details returned")
        self.assertEqual(len(events), 1)
        second = fake.responses.requests[1]
        self.assertEqual(second["previous_response_id"], "one")
        self.assertEqual(json.loads(second["input"][0]["output"])["number"], 10)

    def test_invalid_json_reports_the_failed_call(self):
        call = SimpleNamespace(type="function_call", name="get_pull_request",
                               arguments="{", call_id="c1")
        responses = [SimpleNamespace(id="one", output=[call]),
                     SimpleNamespace(id="two", output=[], output_text="Done")]
        create = Mock(side_effect=responses)
        client = SimpleNamespace(responses=SimpleNamespace(create=create))
        events = []
        with patch.object(agent, "execute_tool") as dispatch:
            agent.run_agent("Check PR", client=client, on_tool=lambda *event: events.append(event))
            dispatch.assert_not_called()
        output = create.call_args.kwargs["input"][0]
        self.assertEqual(output["call_id"], call.call_id)
        error = json.loads(output["output"])
        self.assertIn("error", error)
        self.assertEqual(events, [(call.name, call.arguments, error)])

    def test_no_tool_needed(self):
        response = SimpleNamespace(id="one", output=[], output_text="Hello")
        fake = SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: response))
        self.assertEqual(agent.run_agent("hello", client=fake), "Hello")


if __name__ == "__main__":
    unittest.main()
