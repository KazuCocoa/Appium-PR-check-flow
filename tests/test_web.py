import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from fastapi.testclient import TestClient
    import web
except ImportError:
    TestClient = None


@unittest.skipIf(TestClient is None, "Install requirements.txt to run web tests")
class WebTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(web.app)

    def test_health(self):
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})

    def test_invalid_question(self):
        self.assertEqual(self.client.post("/api/ask", json={"question": ""}).status_code, 422)

    def test_ask(self):
        def fake_run(question, on_tool=None):
            on_tool("list_pull_requests", {"repo": "appium/appium"}, [])
            return "Found PRs"

        with patch.object(web, "run_agent", fake_run):
            result = self.client.post("/api/ask", json={"question": "list PRs"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["answer"], "Found PRs")
        self.assertEqual(result.json()["tools"][0]["tool"], "list_pull_requests")

    def test_index(self):
        self.assertEqual(self.client.get("/").status_code, 200)


if __name__ == "__main__":
    unittest.main()
