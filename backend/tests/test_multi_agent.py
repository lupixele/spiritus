"""Unit tests for Spiritus Multi-Agent Orchestrator and Safety Critic."""
import asyncio
import unittest
from unittest.mock import MagicMock, patch

from agent.orchestrator import MultiAgentOrchestrator
from core.tools import CalculatorTool, ToolRegistry


class TestMultiAgentOrchestrator(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.register(CalculatorTool())

    def test_critic_auditor_detects_lockdown_violation(self):
        from agent.adversarial import adversarial_manager
        adversarial_manager.reset()
        adversarial_manager.inject("CONSTRAINT_INVERSION")

        orchestrator = MultiAgentOrchestrator(registry=self.registry)
        plan_data = {"columns": ["Task"], "rows": [["Execute automated dispatch"]]}

        audit = asyncio.run(orchestrator.audit_plan_safety(plan_data))
        self.assertFalse(audit["approved"])
        self.assertTrue(any("LOCKDOWN" in v["type"] for v in audit["violations"]))
        adversarial_manager.reset()

    def test_critic_auditor_approves_safe_plan(self):
        from agent.adversarial import adversarial_manager
        adversarial_manager.reset()

        orchestrator = MultiAgentOrchestrator(registry=self.registry)
        plan_data = {"columns": ["Step", "Action"], "rows": [["1", "Analyze inventory"], ["2", "Generate summary"]]}

        audit = asyncio.run(orchestrator.audit_plan_safety(plan_data))
        self.assertTrue(audit["approved"])
        self.assertEqual(len(audit["violations"]), 0)

    @patch("httpx.AsyncClient.post")
    def test_multi_agent_stream_handoffs(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "All sub-goals solved.\n```json\n{\"columns\": [\"Item\", \"Status\"], \"rows\": [[\"Task 1\", \"Done\"]]}\n```",
                        "tool_calls": [],
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        orchestrator = MultiAgentOrchestrator(registry=self.registry)

        async def collect():
            evs = []
            async for ev in orchestrator.run("Process general calculation"):
                evs.append(ev)
            return evs

        events = asyncio.run(collect())
        ev_types = [e["type"] for e in events]
        self.assertIn("agent_handoff", ev_types)
        self.assertIn("critic_evaluation", ev_types)
        self.assertIn("final_answer", ev_types)
        self.assertIn("done", ev_types)


if __name__ == "__main__":
    unittest.main()
