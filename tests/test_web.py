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
        def fake_run(question, on_tool=None, provider='openai'):
            on_tool("list_pull_requests", {"repo": "appium/appium"}, [])
            return "Found PRs"

        with patch.object(web, "run_agent", fake_run):
            result = self.client.post("/api/ask", json={"question": "list PRs", "provider": "ollama"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["answer"], "Found PRs")
        self.assertEqual(self.client.post("/api/ask", json={"question": "hi", "provider": "bad"}).status_code, 422)
        self.assertEqual(result.json()["tools"][0]["tool"], "list_pull_requests")

    def test_staged_review(self):
        report = {"findings": [], "coverage": {"complete": False}}
        with patch.object(web, "review_pr", return_value=report) as mock:
            response = self.client.post("/api/review", json={
                "repo": "appium/appium", "number": 23131, "provider": "ollama"
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), report)
        mock.assert_called_once_with("appium/appium", 23131, provider="ollama")

    def test_staged_review_bad_number(self):
        response = self.client.post("/api/review", json={
            "repo": "appium/appium", "number": 0
        })
        self.assertEqual(response.status_code, 422)

    def test_index(self):
        self.assertEqual(self.client.get("/").status_code, 200)


if __name__ == "__main__":
    unittest.main()
