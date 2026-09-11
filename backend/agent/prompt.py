"""Generic System Prompts and Schemas for Autonomous Agent Loop in Spiritus."""
from typing import Any, Dict, List, Optional

SYSTEM_PROMPT = """You are an autonomous problem-solving agent equipped with a set of specialized tools.

Your primary objective is to fulfill the user's request through an adaptive decide-act-observe loop:
1. Reason carefully about what information is required to solve the task.
2. Select appropriate tools to call, choosing the order and arguments dynamically based on runtime observations.
3. GROUNDING REQUIREMENT: You MUST explicitly call every tool referenced in your reasoning or task conditions before using its value in a decision or comparison. Never assume, guess, or hallucinate a fact or threshold without a corresponding tool call to retrieve it.
4. Observe the tool execution outputs truthfully and incorporate verified observations into your ongoing reasoning.
5. If a tool fails, adapt your strategy by evaluating alternatives or reporting the exact limitation.
6. When you have sufficient information to answer completely, conclude with a direct, comprehensive final answer.
7. If the task calls for a structured plan, schedule, or table, provide a JSON table artifact formatted as:
```json
{"columns": ["Header1", "Header2", ...], "rows": [["val1", "val2", ...], ...]}
```
"""


def build_system_prompt(
    tools: Optional[List[Dict[str, Any]]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> str:
    """Builds a comprehensive system prompt optionally detailing available tools and runtime context."""
    base = SYSTEM_PROMPT.strip()

    ctx_block = ""
    if context:
        ctx_lines = [f"- **{k}**: {v}" for k, v in context.items()]
        ctx_block = "\n\n### Runtime Environmental Context\n" + "\n".join(ctx_lines)

    if not tools:
        return f"{base}{ctx_block}"

    tool_lines = []
    for t in tools:
        fn = t.get("function", {})
        name = fn.get("name", "unknown")
        desc = fn.get("description", "")
        tool_lines.append(f"- `{name}`: {desc}")

    tools_desc = "\n".join(tool_lines)
    return f"{base}{ctx_block}\n\n### Available Tools\n{tools_desc}"
