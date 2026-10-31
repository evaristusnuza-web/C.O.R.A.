"""Small MCP client transports used by Friday's optional integrations.

The SSE implementation is a real MCP client. The Stdio implementation below is
intentionally only a demonstration placeholder; use SSE for configured tools.
"""

import asyncio
import logging
from contextlib import AbstractAsyncContextManager, AsyncExitStack
from types import TracebackType
from typing import Any, Self

from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.types import CallToolResult, JSONRPCMessage
from mcp.types import Tool as MCPTool


class MCPServer:
    async def connect(self) -> None:
        raise NotImplementedError

    @property
    def name(self) -> str:
        raise NotImplementedError

    @property
    def connected(self) -> bool:
        raise NotImplementedError

    async def list_tools(self) -> list[MCPTool]:
        raise NotImplementedError

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
        raise NotImplementedError

    async def cleanup(self) -> None:
        raise NotImplementedError


class _MCPServerWithClientSession(MCPServer):
    """Base class for transports that communicate through an MCP ClientSession."""

    def __init__(self, cache_tools_list: bool) -> None:
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()
        self._connect_lock = asyncio.Lock()
        self._cleanup_lock = asyncio.Lock()
        self.cache_tools_list = cache_tools_list
        self._cache_dirty = True
        self._tools_list: list[MCPTool] | None = None
        self.logger = logging.getLogger(__name__)

    @property
    def connected(self) -> bool:
        return self.session is not None

    def create_streams(
        self,
    ) -> AbstractAsyncContextManager[
        tuple[
            MemoryObjectReceiveStream[JSONRPCMessage | Exception],
            MemoryObjectSendStream[JSONRPCMessage],
        ]
    ]:
        raise NotImplementedError

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.cleanup()

    def invalidate_tools_cache(self) -> None:
        self._cache_dirty = True

    async def connect(self) -> None:
        async with self._connect_lock:
            if self.session is not None:
                return
            # AsyncExitStack cannot be reused after aclose; create a fresh one on reconnect.
            self.exit_stack = AsyncExitStack()
            try:
                read, write = await self.exit_stack.enter_async_context(self.create_streams())
                session = await self.exit_stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                self.session = session
                self.logger.info("Connected to MCP server: %s", self.name)
            except Exception:
                self.logger.exception("Could not connect to MCP server %s", self.name)
                try:
                    await self.exit_stack.aclose()
                finally:
                    self.session = None
                    self.exit_stack = AsyncExitStack()
                raise

    async def list_tools(self) -> list[MCPTool]:
        if self.session is None:
            raise RuntimeError("MCP server is not connected; call connect() first.")
        if self.cache_tools_list and not self._cache_dirty and self._tools_list is not None:
            return self._tools_list
        try:
            result = await self.session.list_tools()
            self._tools_list = result.tools
            self._cache_dirty = False
            return self._tools_list
        except Exception:
            self.logger.exception("Could not list tools from MCP server %s", self.name)
            raise

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> CallToolResult:
        if self.session is None:
            raise RuntimeError("MCP server is not connected; call connect() first.")
        try:
            return await self.session.call_tool(tool_name, arguments or {})
        except Exception:
            self.logger.exception("MCP tool call failed: %s", tool_name)
            raise

    async def cleanup(self) -> None:
        async with self._cleanup_lock:
            stack = self.exit_stack
            self.session = None
            self._tools_list = None
            self._cache_dirty = True
            try:
                await stack.aclose()
            except Exception:
                self.logger.exception("Error cleaning up MCP server %s", self.name)
            finally:
                self.exit_stack = AsyncExitStack()


MCPServerSseParams = dict[str, Any]
MCPServerStdioParams = dict[str, Any]


class MCPServerSse(_MCPServerWithClientSession):
    """MCP client using the legacy HTTP/SSE transport."""

    def __init__(
        self,
        params: MCPServerSseParams,
        cache_tools_list: bool = False,
        name: str | None = None,
    ) -> None:
        super().__init__(cache_tools_list)
        self.params = params
        self._name = name or f"SSE MCP server at {self.params.get('url', 'unknown')}"
        if not self.params.get("url"):
            raise ValueError("An MCP SSE server URL is required.")

    def create_streams(
        self,
    ) -> AbstractAsyncContextManager[
        tuple[
            MemoryObjectReceiveStream[JSONRPCMessage | Exception],
            MemoryObjectSendStream[JSONRPCMessage],
        ]
    ]:
        return sse_client(
            url=self.params["url"],
            headers=self.params.get("headers"),
            timeout=self.params.get("timeout", 10),
            sse_read_timeout=self.params.get("sse_read_timeout", 300),
        )

    @property
    def name(self) -> str:
        return self._name


class MCPServerStdio(MCPServer):
    """Placeholder transport retained for compatibility; it does not spawn a process."""

    def __init__(
        self,
        params: MCPServerStdioParams,
        cache_tools_list: bool = False,
        name: str | None = None,
    ) -> None:
        self.params = params
        self.cache_tools_list = cache_tools_list
        self._tools_cache: list[MCPTool] | None = None
        self._name = name or f"Stdio placeholder: {self.params.get('command', 'unknown')}"
        self._connected = False
        self.logger = logging.getLogger(__name__)

    @property
    def name(self) -> str:
        return self._name

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        raise NotImplementedError("MCPServerStdio is a placeholder. Configure an SSE MCP server instead.")

    async def list_tools(self) -> list[MCPTool]:
        if not self.connected:
            raise RuntimeError("The Stdio placeholder is not connected.")
        return self._tools_cache or []

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
        raise NotImplementedError("MCPServerStdio is a placeholder and cannot call tools.")

    async def cleanup(self) -> None:
        self._connected = False
