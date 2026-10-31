"""Adapters between MCP tool definitions and Friday's agent interfaces."""

import json
import logging
from typing import Any

from .server import MCPServer

logger = logging.getLogger(__name__)


class FunctionTool:
    def __init__(
        self,
        name: str,
        description: str,
        params_json_schema: dict[str, Any],
        on_invoke_tool: Any,
        strict_json_schema: bool = False,
    ) -> None:
        self.name = name
        self.description = description
        self.params_json_schema = params_json_schema
        self.on_invoke_tool = on_invoke_tool
        self.strict_json_schema = strict_json_schema

    def __repr__(self) -> str:
        return f"FunctionTool(name={self.name!r})"


class MCPUtil:
    @classmethod
    async def get_function_tools(
        cls,
        server: MCPServer,
        convert_schemas_to_strict: bool = False,
    ) -> list[FunctionTool]:
        tools = await server.list_tools()
        return [
            cls.to_function_tool(tool, server, convert_schemas_to_strict)
            for tool in tools
        ]

    @classmethod
    def to_function_tool(
        cls,
        tool: Any,
        server: MCPServer,
        convert_schemas_to_strict: bool = False,
    ) -> FunctionTool:
        schema = getattr(tool, "inputSchema", None) or {"type": "object", "properties": {}}
        if hasattr(schema, "model_dump"):
            schema = schema.model_dump(exclude_none=True)

        async def invoke_tool(context: Any, input_json: str) -> str:
            try:
                arguments = json.loads(input_json) if input_json else {}
                if not isinstance(arguments, dict):
                    raise TypeError("Tool arguments must be a JSON object.")
            except (json.JSONDecodeError, TypeError) as exc:
                return f"Error parsing input JSON for tool {tool.name!r}: {exc}"
            try:
                result = await server.call_tool(tool.name, arguments)
                content = result.get("content") if isinstance(result, dict) else getattr(result, "content", None)
                pieces: list[str] = []
                for item in content or []:
                    if isinstance(item, str):
                        pieces.append(item)
                    elif isinstance(item, (int, float, bool)):
                        pieces.append(str(item))
                    elif hasattr(item, "text"):
                        pieces.append(str(item.text))
                    elif hasattr(item, "model_dump"):
                        pieces.append(json.dumps(item.model_dump(exclude_none=True), ensure_ascii=False))
                    else:
                        pieces.append(str(item))
                text = "\n".join(piece for piece in pieces if piece)
                is_error = result.get("isError", False) if isinstance(result, dict) else getattr(result, "isError", False)
                if is_error:
                    return f"MCP tool {tool.name!r} returned an error: {text or 'no details'}"
                if text:
                    return text
                if isinstance(result, dict):
                    return json.dumps(result, ensure_ascii=False, default=str)
                if hasattr(result, "model_dump"):
                    return json.dumps(result.model_dump(exclude_none=True), ensure_ascii=False, default=str)
                return str(result)
            except Exception as exc:
                logger.exception("MCP tool call %s failed", tool.name)
                return f"Error calling tool {tool.name!r}: {exc}"

        return FunctionTool(
            name=tool.name,
            description=getattr(tool, "description", None) or "",
            params_json_schema=schema,
            on_invoke_tool=invoke_tool,
            strict_json_schema=convert_schemas_to_strict,
        )
