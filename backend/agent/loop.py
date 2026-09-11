"""Autonomous Decide-Act-Observe Agent Loop for Spiritus."""
import asyncio
import json
import re
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx

from agent.prompt import build_system_prompt
from core.tools import ToolRegistry, ToolResult


def _extract_plan_artifact(text: str) -> Optional[Dict[str, Any]]:
    """Inspects text for an embedded generalized plan_artifact table."""
    if not text:
        return None

    # Search for markdown json fences
    matches = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    for block in matches:
        try:
            data = json.loads(block.strip())
            if isinstance(data, dict) and "columns" in data and "rows" in data:
                if isinstance(data["columns"], list) and isinstance(data["rows"], list):
                    return {"columns": data["columns"], "rows": data["rows"]}
        except Exception:
            continue

    # Fallback search for bare json with columns and rows
    try:
        first = text.find("{")
        last = text.rfind("}")
        if first != -1 and last != -1 and last > first:
            data = json.loads(text[first : last + 1])
            if isinstance(data, dict) and "columns" in data and "rows" in data:
                if isinstance(data["columns"], list) and isinstance(data["rows"], list):
                    return {"columns": data["columns"], "rows": data["rows"]}
    except Exception:
        pass

    return None


def _resolve_endpoint(base_url: str) -> str:
    url = base_url.rstrip("/")
    if url.endswith("/chat/completions"):
        return url
    if url.endswith("/v1"):
        return f"{url}/chat/completions"
    return f"{url}/v1/chat/completions"


async def run_agent_loop(
    instruction: str,
    registry: ToolRegistry,
    provider_url: str,
    api_key: str,
    model: str,
    session_id: Optional[str] = None,
    run_id: Optional[str] = None,
    prior_turns: Optional[List[Dict[str, Any]]] = None,
    max_steps: int = 8,
    timeout: float = 60.0,
    context: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Executes the autonomous decide-act-observe loop.
    Emits structured event dicts: tool_call, plan_artifact, final_answer, done, error.
    """
    endpoint = _resolve_endpoint(provider_url)
    headers = {"Content-Type": "application/json"}
    if api_key and api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    tool_schemas = registry.get_schemas()
    system_prompt = build_system_prompt(tool_schemas, context=context)

    session_tag = session_id or f"sess_{uuid.uuid4().hex[:8]}"
    active_run_id = run_id or f"run_{uuid.uuid4().hex[:8]}"

    messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]

    if prior_turns:
        for pt in prior_turns[-6:]:
            role = pt.get("role")
            content = pt.get("content")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": instruction})
    converged = False

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            for step in range(1, max_steps + 1):
                payload: Dict[str, Any] = {
                    "model": model,
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
                    yield {
                        "type": "done",
                        "session_id": session_tag,
                        "run_id": active_run_id,
                        "converged": False,
                    }
                    return

                if resp.status_code != 200:
                    yield {
                        "type": "error",
                        "session_id": session_tag,
                        "run_id": active_run_id,
                        "step": step,
                        "message": f"LLM provider error (status {resp.status_code}): {resp.text}",
                    }
                    yield {
                        "type": "done",
                        "session_id": session_tag,
                        "run_id": active_run_id,
                        "converged": False,
                    }
                    return

                try:
                    resp_json = resp.json()
                except Exception as parse_err:
                    yield {
                        "type": "error",
                        "session_id": session_tag,
                        "run_id": active_run_id,
                        "step": step,
                        "message": f"Invalid JSON response from LLM provider: {str(parse_err)}",
                    }
                    yield {
                        "type": "done",
                        "session_id": session_tag,
                        "run_id": active_run_id,
                        "converged": False,
                    }
                    return

                choices = resp_json.get("choices", [])
                if not choices:
                    yield {
                        "type": "error",
                        "session_id": session_tag,
                        "run_id": active_run_id,
                        "step": step,
                        "message": "LLM response contained no choices.",
                    }
                    yield {
                        "type": "done",
                        "session_id": session_tag,
                        "run_id": active_run_id,
                        "converged": False,
                    }
                    return

                choice = choices[0]
                message = choice.get("message", {})
                content = message.get("content") or ""
                tool_calls = message.get("tool_calls") or []

                if content:
                    yield {
                        "type": "thought",
                        "session_id": session_tag,
                        "run_id": active_run_id,
                        "step": step,
                        "content": content,
                    }
                    extracted = _extract_plan_artifact(content)
                    if extracted:
                        yield {
                            "type": "plan_artifact",
                            "session_id": session_tag,
                            "run_id": active_run_id,
                            "columns": extracted["columns"],
                            "rows": extracted["rows"],
                        }

                if not tool_calls:
                    converged = True
                    yield {
                        "type": "final_answer",
                        "session_id": session_tag,
                        "run_id": active_run_id,
                        "step": step,
                        "converged": True,
                        "content": content,
                    }
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
                        "tool_name": name,
                        "args": args,
                        "status": "running",
                    }

                    res = await registry.run_tool(name, **args)
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
                        "tool_name": name,
                        "args": args,
                        "status": "success" if res.success else "error",
                        "result_summary": res_summary,
                        "output": res.output if res.success else None,
                        "error": res.error,
                    }

                    if res.artifact and isinstance(res.artifact, dict):
                        if "columns" in res.artifact and "rows" in res.artifact:
                            yield {
                                "type": "plan_artifact",
                                "session_id": session_tag,
                                "run_id": active_run_id,
                                "columns": res.artifact["columns"],
                                "rows": res.artifact["rows"],
                            }

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": res.to_llm_content(),
                    })

            if not converged:
                yield {
                    "type": "final_answer",
                    "session_id": session_tag,
                    "run_id": active_run_id,
                    "step": max_steps,
                    "converged": False,
                    "content": content or "Max execution steps reached without convergence.",
                }

    except asyncio.CancelledError:
        yield {
            "type": "done",
            "session_id": session_tag,
            "run_id": active_run_id,
            "converged": False,
            "cancelled": True,
        }
        return
    except Exception as fatal_err:
        yield {
            "type": "error",
            "session_id": session_tag,
            "run_id": active_run_id,
            "step": step if "step" in locals() else 1,
            "message": f"Agent loop fatal error: {str(fatal_err)}",
        }

    yield {
        "type": "done",
        "session_id": session_tag,
        "run_id": active_run_id,
        "converged": converged,
    }
