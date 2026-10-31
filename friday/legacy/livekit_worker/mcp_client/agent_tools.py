"""Register tools discovered from MCP servers on a LiveKit Agent."""

import inspect
import keyword
import logging
import re
import typing
from collections.abc import Callable
from typing import Any

from friday.mcp_client.server import MCPServer
from .util import FunctionTool, MCPUtil

logger = logging.getLogger("mcp-agent-tools")


class MCPToolsIntegration:
    """Convert MCP JSON-schema tools into LiveKit function tools."""

    @staticmethod
    async def prepare_dynamic_tools(
        mcp_servers: list[MCPServer],
        convert_schemas_to_strict: bool = False,
        auto_connect: bool = True,
    ) -> list[Callable[..., Any]]:
        prepared: list[Callable[..., Any]] = []
        for server in mcp_servers:
            if not getattr(server, "connected", False):
                if not auto_connect:
                    logger.warning("MCP server %s is not connected", server.name)
                    continue
                try:
                    await server.connect()
                except Exception:
                    logger.exception("Could not connect to MCP server %s", server.name)
                    continue
            try:
                mcp_tools = await MCPUtil.get_function_tools(
                    server, convert_schemas_to_strict=convert_schemas_to_strict
                )
            except Exception:
                logger.exception("Could not fetch tools from MCP server %s", server.name)
                continue
            for tool in mcp_tools:
                try:
                    prepared.append(MCPToolsIntegration._create_decorated_tool(tool))
                except Exception:
                    logger.exception("Could not register MCP tool %s", tool.name)
        return prepared

    @staticmethod
    def _create_decorated_tool(tool: FunctionTool) -> Callable[..., Any]:
        from livekit.agents.llm import function_tool

        schema = tool.params_json_schema or {}
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        type_map: dict[str, Any] = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        parameters: list[inspect.Parameter] = []
        annotations: dict[str, Any] = {}
        argument_names: dict[str, str] = {}
        used_names: set[str] = set()

        for original_name, details in properties.items():
            details = details if isinstance(details, dict) else {}
            safe_name = re.sub(r"\W", "_", str(original_name))
            if not safe_name or safe_name[0].isdigit():
                safe_name = f"arg_{safe_name}"
            if keyword.iskeyword(safe_name):
                safe_name += "_"
            base_name = safe_name
            suffix = 2
            while safe_name in used_names:
                safe_name = f"{base_name}_{suffix}"
                suffix += 1
            used_names.add(safe_name)
            argument_names[safe_name] = str(original_name)

            json_type = details.get("type", "string")
            if isinstance(json_type, list):
                json_type = next((value for value in json_type if value != "null"), "string")
            python_type = type_map.get(json_type, typing.Any)
            is_required = original_name in required
            default = inspect.Parameter.empty if is_required else details.get("default", None)
            if not is_required and default is None and python_type is not typing.Any:
                python_type = python_type | None
            annotations[safe_name] = python_type
            parameters.append(
                inspect.Parameter(
                    name=safe_name,
                    kind=inspect.Parameter.KEYWORD_ONLY,
                    annotation=python_type,
                    default=default,
                )
            )

        async def tool_impl(**kwargs: Any) -> str:
            original_kwargs = {
                argument_names.get(name, name): value for name, value in kwargs.items()
            }
            import json

            return await tool.on_invoke_tool(None, json.dumps(original_kwargs, ensure_ascii=False))

        signature_name = re.sub(r"\W", "_", tool.name)
        if not signature_name or signature_name[0].isdigit():
            signature_name = f"mcp_{signature_name}"
        if keyword.iskeyword(signature_name):
            signature_name = f"mcp_{signature_name}"
        tool_impl.__signature__ = inspect.Signature(parameters=parameters)
        tool_impl.__name__ = signature_name
        tool_impl.__doc__ = tool.description or f"MCP tool {tool.name}"
        tool_impl.__annotations__ = {"return": str, **annotations}
        decorated = function_tool()(tool_impl)
        # Preserve the remote name for diagnostics without using it as an invalid Python identifier.
        decorated.mcp_tool_name = tool.name
        return decorated

    @staticmethod
    async def register_with_agent(
        agent: Any,
        mcp_servers: list[MCPServer],
        convert_schemas_to_strict: bool = False,
        auto_connect: bool = True,
    ) -> list[Callable[..., Any]]:
        tools = await MCPToolsIntegration.prepare_dynamic_tools(
            mcp_servers,
            convert_schemas_to_strict=convert_schemas_to_strict,
            auto_connect=auto_connect,
        )
        if hasattr(agent, "_tools") and isinstance(agent._tools, list):
            agent._tools.extend(tools)
            logger.info("Registered %d MCP tools with agent", len(tools))
        else:
            logger.warning("Agent has no mutable _tools list; MCP tools were not registered")
        return tools

    @staticmethod
    async def create_agent_with_tools(
        agent_class: Any,
        mcp_servers: list[MCPServer],
        agent_kwargs: dict[str, Any] | None = None,
        convert_schemas_to_strict: bool = False,
    ) -> Any:
        agent = agent_class(**(agent_kwargs or {}))
        await MCPToolsIntegration.register_with_agent(
            agent,
            mcp_servers,
            convert_schemas_to_strict=convert_schemas_to_strict,
            auto_connect=True,
        )
        return agent
