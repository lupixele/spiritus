"""Unit tests for Spiritus FastAPI Endpoints."""
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app import app


class TestSpiritusAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_get_config(self):
        resp = self.client.get("/api/config")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("provider_url", data)
        self.assertIn("active_model", data)

    def test_sessions_crud(self):
        # Create
        create_resp = self.client.post("/api/sessions", json={"title": "Test Session"})
        self.assertEqual(create_resp.status_code, 200)
        sess_id = create_resp.json()["id"]

        # Get
        get_resp = self.client.get(f"/api/sessions/{sess_id}")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["title"], "Test Session")

        # Delete
        del_resp = self.client.delete(f"/api/sessions/{sess_id}")
        self.assertEqual(del_resp.status_code, 200)

    @patch("app.run_agent_loop")
    def test_stream_agent_sse(self, mock_loop):
        async def mock_event_gen(*args, **kwargs):
            yield {
                "type": "tool_call",
                "step": 1,
                "tool_name": "calculator",
                "status": "success",
                "args": {"expression": "2+2"},
                "result_summary": "4",
            }
            yield {
                "type": "final_answer",
                "step": 2,
                "content": "Result is 4",
                "converged": True,
            }
            yield {
                "type": "done",
                "session_id": "test_sess",
                "converged": True,
            }

        mock_loop.side_effect = mock_event_gen

        resp = self.client.post(
            "/api/agent/stream",
            json={
                "instruction": "Calculate 2+2",
                "session_id": "test_sess",
                "model": "test-model",
                "multi_agent": False,
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/event-stream", resp.headers["content-type"])
        body = resp.text
        self.assertIn("data: ", body)
        self.assertIn('"type": "tool_call"', body)
        self.assertIn('"type": "final_answer"', body)


if __name__ == "__main__":
    unittest.main()
