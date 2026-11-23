import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent


class ToolTests(unittest.TestCase):
    def test_rejects_invalid_repository_without_network(self):
        with patch.object(agent, "urlopen") as open_mock:
            result = agent.list_pull_requests("https://example.com/a/b")
        self.assertIn("error", result)
        open_mock.assert_not_called()

    def test_tool_schema_is_strict(self):
        self.assertTrue(agent.TOOLS[0]["strict"])
        self.assertFalse(agent.TOOLS[0]["parameters"]["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
