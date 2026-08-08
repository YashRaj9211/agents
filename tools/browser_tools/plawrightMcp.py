import os
from google.adk.tools.mcp_tool import McpToolset
from mcp import StdioServerParameters

# Initialize the Playwright MCP Toolset using npx
connection_params = StdioServerParameters(
    command="npx",
    args=["-y", "@playwright/mcp@latest", "--headless"],
    env=os.environ.copy()
)

playwright_toolset = McpToolset(
    connection_params=connection_params,
)
