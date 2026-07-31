import os
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

# Set BROWSER_MODE=headless to run without a visible window.
# By default (or any other value), the browser window is shown.
HEADLESS = os.getenv("BROWSER_MODE", "").lower() == "headless"

args = []
if HEADLESS:
    args.append("--headless")

def create_playwright_toolset(timeout: float = 60.0) -> McpToolset:
    """
    Creates an ADK McpToolset connected to Playwright MCP server using npx.
    """
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@playwright/mcp@latest"] + args,
        env=os.environ.copy()
    )
    connection_params = StdioConnectionParams(
        server_params=server_params,
        timeout=timeout
    )
    return McpToolset(
        connection_params=connection_params
    )

playwright_toolset = create_playwright_toolset()