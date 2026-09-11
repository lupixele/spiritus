"""Generic Tool Protocol and Registry for Agentic Execution.

Provides a problem-agnostic tool system with built-in safe execution:
- CalculatorTool: Safe mathematical evaluation
- DatasetLookupTool: Generic structured entity query/filter
- HttpFetchTool: Resilient HTTP requests with timeouts & fallback
- KeyValueStoreTool: Session-scoped persistent key-value memory
"""
import ast
import json
import logging
import operator
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable

logger = logging.getLogger("spiritus.tools")


@dataclass
class ToolResult:
    success: bool
    output: Any = None
    error: Optional[str] = None
    artifact: Optional[Dict[str, Any]] = None

    def to_llm_content(self) -> str:
        if not self.success:
            return f"Error: {self.error or 'Unknown tool execution error'}"
        if isinstance(self.output, (dict, list)):
            return json.dumps(self.output)
        return str(self.output)


@runtime_checkable
class Tool(Protocol):
    name: str
    description: str
    json_schema: Dict[str, Any]

    async def run(self, **kwargs) -> ToolResult:
        ...


class CalculatorTool:
    name: str = "calculator"
    description: str = (
        "Evaluate a safe mathematical expression (supports +, -, *, /, //, %, **, parentheses). "
        "Does not allow variables, system calls, or arbitrary Python execution."
    )
    json_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Mathematical expression to evaluate, e.g. '150 * 42' or '(100 + 50) / 2'",
            }
        },
        "required": ["expression"],
    }

    _OPERATORS: Dict[type, Callable[[Any, Any], Any]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }

    _UNARY_OPERATORS: Dict[type, Callable[[Any], Any]] = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    def _eval_node(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"Unsupported constant type: {type(node.value)}")
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op_type = type(node.op)
            if op_type not in self._OPERATORS:
                raise ValueError(f"Unsupported operator: {op_type}")
            if op_type == ast.Pow and (right > 100 or left > 10000):
                raise ValueError("Exponentiation base or power too large")
            return self._OPERATORS[op_type](left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            op_type = type(node.op)
            if op_type not in self._UNARY_OPERATORS:
                raise ValueError(f"Unsupported unary operator: {op_type}")
            return self._UNARY_OPERATORS[op_type](operand)
        else:
            raise ValueError(f"Unsupported syntax tree node: {type(node)}")

    async def run(self, expression: str = "", **kwargs) -> ToolResult:
        if not expression or not expression.strip():
            return ToolResult(success=False, error="Expression cannot be empty")
        try:
            tree = ast.parse(expression.strip(), mode="eval")
            result = self._eval_node(tree.body)
            return ToolResult(success=True, output=result)
        except Exception as e:
            return ToolResult(success=False, error=f"Math evaluation error: {str(e)}")


class DatasetLookupTool:
    name: str = "dataset_lookup"
    description: str = (
        "Query or filter structured entities from the registered in-memory domain store. "
        "Supports exact key lookup or field filtering."
    )
    json_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "collection": {
                "type": "string",
                "description": "The dataset collection name to query (e.g. 'inventory', 'routes', 'users')",
            },
            "key": {
                "type": "string",
                "description": "Optional specific item ID to retrieve",
            },
            "filter_field": {
                "type": "string",
                "description": "Optional field name to filter by",
            },
            "filter_value": {
                "type": "string",
                "description": "Optional value that filter_field must match",
            },
        },
        "required": ["collection"],
    }

    def __init__(self, initial_data: Optional[Dict[str, List[Dict[str, Any]]]] = None):
        self._data = initial_data or {
            "services": [
                {"id": "srv_01", "name": "Primary Dispatch", "status": "active", "latency_ms": 12},
                {"id": "srv_02", "name": "Analytics Pipeline", "status": "active", "latency_ms": 34},
                {"id": "srv_03", "name": "Backup Gateway", "status": "standby", "latency_ms": 85},
            ]
        }

    def register_collection(self, name: str, items: List[Dict[str, Any]]):
        self._data[name] = items

    async def run(
        self,
        collection: str = "",
        key: Optional[str] = None,
        filter_field: Optional[str] = None,
        filter_value: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        if collection not in self._data:
            return ToolResult(
                success=False,
                error=f"Collection '{collection}' not found. Available: {list(self._data.keys())}",
            )
        items = self._data[collection]
        if key:
            match = next((item for item in items if item.get("id") == key), None)
            if match:
                return ToolResult(success=True, output=match)
            return ToolResult(success=False, error=f"Item '{key}' not found in '{collection}'")

        if filter_field and filter_value is not None:
            filtered = [
                item for item in items
                if str(item.get(filter_field, "")).lower() == str(filter_value).lower()
            ]
            return ToolResult(success=True, output=filtered)

        return ToolResult(success=True, output=items)


class KeyValueStoreTool:
    name: str = "kv_store"
    description: str = "Read, write, or list persistent key-value configuration and notes."
    json_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get", "set", "delete", "list"],
                "description": "Operation to perform",
            },
            "key": {"type": "string", "description": "Key name"},
            "value": {"type": "string", "description": "Value to store (for action='set')"},
        },
        "required": ["action"],
    }

    def __init__(self):
        self._store: Dict[str, str] = {}

    async def run(self, action: str = "list", key: str = "", value: str = "", **kwargs) -> ToolResult:
        if action == "list":
            return ToolResult(success=True, output=dict(self._store))
        elif action == "get":
            if key in self._store:
                return ToolResult(success=True, output=self._store[key])
            return ToolResult(success=False, error=f"Key '{key}' not found in store")
        elif action == "set":
            if not key:
                return ToolResult(success=False, error="Key cannot be empty for set action")
            self._store[key] = value
            return ToolResult(success=True, output={"key": key, "value": value, "status": "saved"})
        elif action == "delete":
            if key in self._store:
                del self._store[key]
                return ToolResult(success=True, output={"key": key, "status": "deleted"})
            return ToolResult(success=False, error=f"Key '{key}' does not exist")
        return ToolResult(success=False, error=f"Unsupported action '{action}'")


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Tool]:
        return list(self._tools.values())

    def get_schemas(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.json_schema,
                },
            }
            for tool in self._tools.values()
        ]

    async def run_tool(self, name: str, **kwargs) -> ToolResult:
        tool = self.get(name)
        if not tool:
            return ToolResult(success=False, error=f"Tool '{name}' is not registered.")
        try:
            return await tool.run(**kwargs)
        except Exception as e:
            logger.exception(f"Unhandled exception in tool '{name}'")
            return ToolResult(success=False, error=f"Internal tool error: {str(e)}")
