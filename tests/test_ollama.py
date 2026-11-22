"""Offline tests for native Ollama tool calling."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent


class OllamaTests(unittest.TestCase):
    def test_default_model(self):
        self.assertEqual(agent.OLLAMA_MODEL, "qwen3.5:9b")

    def test_tool_schema_conversion(self):
        converted = agent.ollama_tools()
        self.assertEqual(len(converted), len(agent.TOOLS))
        self.assertEqual(converted[0]["function"]["name"], "list_pull_requests")
        self.assertIn("parameters", converted[0]["function"])

    def test_simple_answer(self):
        messages_seen = []
        def chat(messages):
            messages_seen.extend(messages)
            return {"role": "assistant", "content": "Hello"}
        self.assertEqual(agent.run_ollama_agent("Hi", chat=chat), "Hello")
        self.assertEqual(messages_seen[0]["role"], "system")

    def test_tool_round_trip(self):
        seen = []
        traces = []
        def chat(messages):
            seen.append([dict(m) for m in messages])
            if len(seen) == 1:
                return {
                    "role": "assistant", "content": "",
                    "tool_calls": [
                        {"function": {"name": "get_pull_request",
                                      "arguments": {"repo": "appium/appium", "number": 10}}}
                    ],
                }
            return {"role": "assistant", "content": "PR 10 examined"}

        with patch.dict(agent.HANDLERS, {"get_pull_request": lambda **kwargs: {"number": kwargs["number"]}}):
            result = agent.run_ollama_agent(
                "Inspect PR 10", chat=chat, on_tool=lambda *item: traces.append(item)
            )
        self.assertEqual(result, "PR 10 examined")
        self.assertEqual(len(traces), 1)
        self.assertEqual(seen[1][-1]["role"], "tool")
        self.assertEqual(json.loads(seen[1][-1]["content"]), {"number": 10})

    def test_invalid_tool_name_returns_error(self):
        seen = []
        def chat(messages):
            seen.append([dict(m) for m in messages])
            if len(seen) == 1:
                return {"content": "", "tool_calls": [
                    {"function": {"name": "nonexistent", "arguments": {}}}
                ]}
            return {"content": "Done"}
        agent.run_ollama_agent("Hi", chat=chat)
        self.assertIn("Unknown tool", seen[1][-1]["content"])

    def test_ollama_endpoint_is_loopback(self):
        self.assertEqual(agent.OLLAMA_ENDPOINT, "http://127.0.0.1:11434/api/chat")

    def test_provider_routing_without_openai_client(self):
        with patch.object(agent, "run_ollama_agent", return_value="local") as mocked:
            self.assertEqual(agent.run_agent("test", provider="ollama"), "local")
            mocked.assert_called_once()

    def test_unknown_provider_rejected(self):
        with self.assertRaises(ValueError):
            agent.run_agent("test", provider="unknown", client=object())


if __name__ == "__main__":
    unittest.main()
