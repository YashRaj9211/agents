"""Small client for the Playwright MCP server.

It only starts the server, lists its tools, and forwards tool calls. Browser
behaviour stays in Playwright MCP; this project does not duplicate its API.
"""
from __future__ import annotations

import json
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config import settings


class PlaywrightMcpClient:
    def __init__(self) -> None:
        self._stack = AsyncExitStack()
        self._session: ClientSession | None = None

    async def start(self) -> None:
        settings.browser_profile_dir.mkdir(parents=True, exist_ok=True)
        params = StdioServerParameters(
            command=settings.mcp_command,
            args=settings.mcp_args,
        )
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()

    async def stop(self) -> None:
        await self._stack.aclose()
        self._session = None

    async def openai_tools(self) -> list[dict[str, Any]]:
        """Convert MCP tool definitions into the format expected by OpenAI SDKs."""
        session = self._require_session()
        response = await session.list_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema or {"type": "object", "properties": {}},
                },
            }
            for tool in response.tools
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Run one Playwright MCP tool and turn its result into text for the model."""
        try:
            result = await self._require_session().call_tool(name, arguments=arguments)
        except Exception as error:  # The model needs the error to choose its next action.
            return json.dumps({"error": str(error)})

        parts = [
            block.text if getattr(block, "type", None) == "text" else "[non-text browser result]"
            for block in result.content
        ]
        output = "\n".join(parts) or "(empty browser result)"
        return json.dumps({"error": output}) if getattr(result, "isError", False) else output

    def _require_session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError("Browser is not running. Call start() first.")
        return self._session
