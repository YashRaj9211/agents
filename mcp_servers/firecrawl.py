"""
firecrawl.py
------------
Firecrawl MCP toolset factory — self-hosted mode.

By default this module connects to a **locally running** Firecrawl instance
(Docker Compose at http://localhost:3002).  When FIRECRAWL_API_URL is set to a
local address the firecrawl-mcp npm package skips cloud authentication
entirely, so no FIRECRAWL_API_KEY is required.

To switch to the cloud API, set FIRECRAWL_API_KEY in your environment (or
.env) and leave FIRECRAWL_API_URL unset (or set it to
https://api.firecrawl.dev).

Usage from agent code:
    from mcp_servers.firecrawl import firecrawl_toolset        # lazy singleton
    from mcp_servers.firecrawl import create_firecrawl_toolset  # explicit factory
"""

from __future__ import annotations

import os
from dotenv import load_dotenv

from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

load_dotenv()


# ── Defaults ──────────────────────────────────────────────────────────────────
# Point at the locally running Firecrawl Docker Compose stack.
# Override with the FIRECRAWL_API_URL env-var to use a different host or the
# cloud API.
_DEFAULT_LOCAL_URL = "http://localhost:3002"
_DEFAULT_CLOUD_URL = "https://api.firecrawl.dev"

FIRECRAWL_API_KEY: str = os.getenv("FIRECRAWL_API_KEY", "")
FIRECRAWL_API_URL: str = os.getenv(
    "FIRECRAWL_API_URL", 
    _DEFAULT_CLOUD_URL if FIRECRAWL_API_KEY else _DEFAULT_LOCAL_URL
)


def create_firecrawl_toolset(
    api_url: str = FIRECRAWL_API_URL,
    api_key: str = FIRECRAWL_API_KEY,
    timeout: float = 60.0,
) -> McpToolset:
    """
    Creates an ADK McpToolset connected to the Firecrawl MCP server.

    The MCP server is launched locally via ``npx firecrawl-mcp`` over stdio.
    It reads FIRECRAWL_API_URL and FIRECRAWL_API_KEY from the env it receives.

    Self-hosted (no API key needed):
        FIRECRAWL_API_URL=http://localhost:3002  → npx firecrawl-mcp

    Cloud (API key required):
        FIRECRAWL_API_KEY=fc-xxx                 → npx firecrawl-mcp

    Args:
        api_url:  Firecrawl API base URL. Defaults to https://api.firecrawl.dev (if key present) or http://localhost:3002.
        api_key:  Firecrawl API key. Leave empty for local/self-hosted.
        timeout:  MCP session connection timeout in seconds.

    Returns:
        A configured McpToolset instance that exposes the Firecrawl tools:
            - firecrawl_scrape
            - firecrawl_search
            - firecrawl_crawl
            - firecrawl_map
            - firecrawl_check_crawl_status
            - firecrawl_extract
    """
    env = os.environ.copy()
    env["FIRECRAWL_API_URL"] = api_url
    if api_key:
        env["FIRECRAWL_API_KEY"] = api_key

    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "firecrawl-mcp"],
        env=env,
    )
    connection_params = StdioConnectionParams(
        server_params=server_params,
        timeout=timeout,
    )
    
    print(f"Created Firecrawl toolset (URL: {api_url})")
    return McpToolset(connection_params=connection_params)


# ── Lazy singleton ─────────────────────────────────────────────────────────────
# Created once at import time using the current env values.
# Call create_firecrawl_toolset() directly if you need custom settings.
firecrawl_toolset = create_firecrawl_toolset()
