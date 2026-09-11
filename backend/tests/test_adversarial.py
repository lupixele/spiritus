"""Unit tests for Spiritus Adversarial Chaos Engine."""
import unittest
from fastapi.testclient import TestClient

from app import app
from agent.adversarial import adversarial_manager


class TestSpiritusAdversarial(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        adversarial_manager.reset()

    def tearDown(self):
        adversarial_manager.reset()

    def test_presets_catalog(self):
        resp = self.client.get("/api/adversarial/presets")
        self.assertEqual(resp.status_code, 200)
        presets = resp.json()
        self.assertGreaterEqual(len(presets), 3)

    def test_inject_and_reset(self):
        resp = self.client.post("/api/adversarial/inject", json={"scenario_id": "SERVICE_OUTAGE_HTTP503"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(adversarial_manager.is_outage_active("external_service"))

        st = self.client.get("/api/adversarial/status").json()
        self.assertTrue(st["chaos_active"])

        # Reset
        res_reset = self.client.post("/api/adversarial/reset")
        self.assertEqual(res_reset.status_code, 200)
        self.assertFalse(adversarial_manager.get_status()["chaos_active"])


if __name__ == "__main__":
    unittest.main()
