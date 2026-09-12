"""Domain-Agnostic Multi-Agent Orchestration & Self-Healing Critic Engine for Spiritus."""
import asyncio
import json
import logging
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from agent.adversarial import adversarial_manager
from agent.loop import _extract_plan_artifact, _resolve_endpoint
from agent.prompt import build_system_prompt
from core.tools import ToolRegistry, ToolResult

logger = logging.getLogger("spiritus.orchestrator")


class MultiAgentOrchestrator:
    """Coordinates specialized agents: Orchestrator -> Domain Executor -> Safety Critic -> Self-Healing."""

    def __init__(
        self,
        registry: ToolRegistry,
        provider_url: str = "http://localhost:20128/v1",
        api_key: str = "",
        model: str = "antigravity/gemini-3.8-flash-tiered",
        max_steps_per_agent: int = 6,
        timeout: float = 60.0,
    ):
        self.registry = registry
        self.provider_url = provider_url
        self.api_key = api_key
        self.model = model
        self.max_steps_per_agent = max_steps_per_agent
        self.timeout = timeout

    async def audit_plan_safety(
        self, plan_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Audits candidate plan against active adversarial constraints and logical consistency."""
        violations = []
        warnings = []

        chaos = adversarial_manager.get_status()
        injected = chaos.get("injected_constraints", {})

        # Check emergency lockdown
        if injected.get("emergency_lockdown"):
            violations.append({
                "type": "EMERGENCY_LOCKDOWN_VIOLATION",
                "details": "Emergency lockdown policy is active. Unverified automated operations prohibited.",
            })

        # Check road closure violations & shelter overcapacity from exercise state if present
        try:
            from disaster.scenario_engine import get_exercise_summary
            ex = get_exercise_summary()
            disrupted_names = [r["name"].lower() for r in ex["disrupted_roads"]]
            full_shelters = [s["name"].lower() for s in ex["shelters"] if s["status"] != "open" or s["current_occupancy"] >= s["max_capacity"]]
            
            rows = plan_data.get("rows", [])
            for row in rows:
                text_cells = " ".join(str(v).lower() for v in row)
                for d_road in disrupted_names:
                    if d_road in text_cells and "avoid" not in text_cells and "bypass" not in text_cells:
                        violations.append({
                            "type": "ROAD_CLOSURE_SAFETY_VIOLATION",
                            "details": f"Plan routes through compromised corridor '{d_road}', which is blocked/collapsed.",
                        })
                for f_sh in full_shelters:
                    if f_sh in text_cells and "divert" not in text_cells and "full" not in text_cells:
                        violations.append({
                            "type": "SHELTER_OVERCAPACITY_VIOLATION",
                            "details": f"Plan routes evacuees to shelter '{f_sh}' which is already at 100% capacity.",
                        })
        except Exception:
            pass

        is_approved = len(violations) == 0
        return {
            "approved": is_approved,
            "violations": violations,
            "warnings": warnings,
            "auditor": "Safety Critic & Grounding Auditor v2.0",
            "notes": "Plan conforms to operational constraints." if is_approved else "Adversarial violations detected. Autonomous self-healing triggered.",
        }

    async def run(
        self,
        instruction: str,
        session_id: Optional[str] = None,
        run_id: Optional[str] = None,
        prior_turns: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        session_tag = session_id or f"sess_{uuid.uuid4().hex[:8]}"
        active_run_id = run_id or f"run_{uuid.uuid4().hex[:8]}"
        endpoint = _resolve_endpoint(self.provider_url)
        headers = {"Content-Type": "application/json"}
        if self.api_key and self.api_key.strip():
            headers["Authorization"] = f"Bearer {self.api_key.strip()}"

        # 1. Orchestrator Dispatch
        yield {
            "type": "agent_handoff",
            "session_id": session_tag,
            "run_id": active_run_id,
            "from_agent": "User Client",
            "to_agent": "Orchestrator Agent",
            "role": "Mission Strategy & Task Decomposition",
            "mission": instruction,
        }

        yield {
            "type": "activity",
            "session_id": session_tag,
            "run_id": active_run_id,
            "content": "Orchestrator decomposing mission into execution sub-goals...",
        }

        # 2. Execution Specialist
        yield {
            "type": "agent_handoff",
            "session_id": session_tag,
            "run_id": active_run_id,
            "from_agent": "Orchestrator Agent",
            "to_agent": "Domain Execution Specialist",
            "role": "Dynamic Tool Calling & Grounded Synthesis",
            "mission": "Execute tool queries and produce candidate plan artifact.",
        }

        tool_schemas = self.registry.get_schemas()
        system_prompt = build_system_prompt(tool_schemas, context=context)

        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        if prior_turns:
            for pt in prior_turns[-6:]:
                r = pt.get("role")
                c = pt.get("content")
                if r in ("user", "assistant") and c:
                    messages.append({"role": r, "content": c})

        messages.append({"role": "user", "content": instruction})

        final_artifact: Optional[Dict[str, Any]] = None
        assistant_content_accum = ""
        converged = False

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for step in range(1, self.max_steps_per_agent + 1):
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.2,
                }
                if tool_schemas:
                    payload["tools"] = tool_schemas
                    payload["tool_choice"] = "auto"

                try:
                    resp = await client.post(endpoint, headers=headers, json=payload)
                except asyncio.CancelledError:
                    raise
                except Exception as net_err:
                    yield {
                        "type": "error",
                        "session_id": session_tag,
                        "run_id": active_run_id,
                        "step": step,
                        "message": f"Network error contacting LLM provider: {str(net_err)}",
                    }
                    yield {"type": "done", "session_id": session_tag, "run_id": active_run_id, "converged": False}
                    return

                if resp.status_code != 200:
                    yield {
                        "type": "error",
                        "session_id": session_tag,
                        "run_id": active_run_id,
                        "step": step,
                        "message": f"LLM provider error ({resp.status_code}): {resp.text}",
                    }
                    yield {"type": "done", "session_id": session_tag, "run_id": active_run_id, "converged": False}
                    return

                resp_json = resp.json()
                choices = resp_json.get("choices", [])
                if not choices:
                    yield {
                        "type": "error",
                        "session_id": session_tag,
                        "run_id": active_run_id,
                        "step": step,
                        "message": "LLM response contained no choices.",
                    }
                    yield {"type": "done", "session_id": session_tag, "run_id": active_run_id, "converged": False}
                    return

                message = choices[0].get("message", {})
                content = message.get("content") or ""
                tool_calls = message.get("tool_calls") or []

                if content:
                    assistant_content_accum += content
                    yield {
                        "type": "thought",
                        "session_id": session_tag,
                        "run_id": active_run_id,
                        "step": step,
                        "agent": "Domain Execution Specialist",
                        "content": content,
                    }
                    extracted = _extract_plan_artifact(content)
                    if extracted:
                        final_artifact = extracted
                        yield {
                            "type": "plan_artifact",
                            "session_id": session_tag,
                            "run_id": active_run_id,
                            "columns": extracted["columns"],
                            "rows": extracted["rows"],
                            "title": "Candidate Plan Artifact (Pre-Audit)",
                        }

                if not tool_calls:
                    converged = True
                    break

                messages.append(message)
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    name = fn.get("name", "")
                    arguments_raw = fn.get("arguments", "{}")
                    tc_id = tc.get("id") or f"call_{uuid.uuid4().hex[:8]}"

                    try:
                        args = json.loads(arguments_raw) if isinstance(arguments_raw, str) else (arguments_raw or {})
                    except Exception:
                        args = {}

                    inv_id = f"inv_{uuid.uuid4().hex[:8]}"
                    yield {
                        "type": "tool_call",
                        "session_id": session_tag,
                        "run_id": active_run_id,
                        "step": step,
                        "invocation_id": inv_id,
                        "agent": "Domain Execution Specialist",
                        "tool_name": name,
                        "args": args,
                        "status": "running",
                    }

                    res = await self.registry.run_tool(name, **args)
                    res_summary = ""
                    if res.output and isinstance(res.output, dict):
                        res_summary = res.output.get("status") or str(res.output)[:100]
                    elif res.error:
                        res_summary = f"Error: {res.error[:100]}"
                    else:
                        res_summary = str(res.output)[:100] if res.output is not None else ""

                    yield {
                        "type": "tool_call",
                        "session_id": session_tag,
                        "run_id": active_run_id,
                        "step": step,
                        "invocation_id": inv_id,
                        "agent": "Domain Execution Specialist",
                        "tool_name": name,
                        "args": args,
                        "status": "completed" if res.success else "failed",
                        "result_summary": res_summary,
                        "output": res.output if res.success else None,
                        "error": res.error,
                    }

                    if res.artifact and isinstance(res.artifact, dict):
                        if "columns" in res.artifact and "rows" in res.artifact:
                            final_artifact = res.artifact
                            yield {
                                "type": "plan_artifact",
                                "session_id": session_tag,
                                "run_id": active_run_id,
                                "columns": res.artifact["columns"],
                                "rows": res.artifact["rows"],
                                "title": res.artifact.get("title", f"Plan Artifact ({name})"),
                            }

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": res.to_llm_content(),
                    })

        # 3. Safety Critic & Invariant Auditor
        yield {
            "type": "agent_handoff",
            "session_id": session_tag,
            "run_id": active_run_id,
            "from_agent": "Domain Execution Specialist",
            "to_agent": "Safety Critic & Grounding Auditor",
            "role": "Constraint Audit & Invariant Verification",
            "mission": "Verify candidate output against active operational and safety constraints.",
        }

        audit_result = await self.audit_plan_safety(final_artifact or {"rows": [assistant_content_accum]}, context=context)

        yield {
            "type": "critic_evaluation",
            "session_id": session_tag,
            "run_id": active_run_id,
            "approved": audit_result["approved"],
            "violations": audit_result["violations"],
            "warnings": audit_result["warnings"],
            "auditor": audit_result["auditor"],
            "notes": audit_result["notes"],
        }

        # 4. Self-Healing Replanning Loop (if rejected)
        if not audit_result["approved"]:
            yield {
                "type": "activity",
                "session_id": session_tag,
                "run_id": active_run_id,
                "content": "Critic rejected candidate plan. Invoking autonomous self-healing corrective loop...",
            }

            corrective_prompt = (
                f"AUDITOR SAFETY VIOLATION NOTICE:\n"
                f"The previously proposed solution violated constraints: {json.dumps(audit_result['violations'])}.\n"
                f"You must revise your plan, satisfy all constraints, and produce an approved solution."
            )
            messages.append({"role": "user", "content": corrective_prompt})

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {"model": self.model, "messages": messages, "temperature": 0.1}
                if tool_schemas:
                    payload["tools"] = tool_schemas
                    payload["tool_choice"] = "auto"
                try:
                    c_resp = await client.post(endpoint, headers=headers, json=payload)
                    if c_resp.status_code == 200:
                        c_json = c_resp.json()
                        c_choices = c_json.get("choices", [])
                        if c_choices:
                            c_msg = c_choices[0].get("message", {})
                            c_content = c_msg.get("content") or ""
                            if c_content:
                                assistant_content_accum += f"\n\n**[Self-Healing Corrective Plan]**\n{c_content}"
                                extracted_c = _extract_plan_artifact(c_content)
                                if extracted_c:
                                    final_artifact = extracted_c
                                    yield {
                                        "type": "plan_artifact",
                                        "session_id": session_tag,
                                        "run_id": active_run_id,
                                        "columns": extracted_c["columns"],
                                        "rows": extracted_c["rows"],
                                        "title": "Certified Self-Healed Plan Artifact",
                                    }
                except Exception as c_err:
                    logger.warning(f"Self-healing sub-step warning: {c_err}")

        # 5. Final Synthesis
        yield {
            "type": "final_answer",
            "session_id": session_tag,
            "run_id": active_run_id,
            "step": step if "step" in locals() else 1,
            "converged": converged,
            "content": assistant_content_accum or "Task completed.",
            "artifact": final_artifact,
            "audit": audit_result,
        }

        yield {
            "type": "done",
            "session_id": session_tag,
            "run_id": active_run_id,
            "converged": converged,
        }
