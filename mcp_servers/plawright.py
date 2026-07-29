import os
from google.adk.tools.mcp_tool import McpToolset
from mcp import StdioServerParameters

# Initialize the Playwright MCP Toolset using npx

# Set BROWSER_MODE=headless to run without a visible window.
# By default (or any other value), the browser window is shown.
HEADLESS = os.getenv("BROWSER_MODE", "").lower() == "headless"
print("Headless mode:", HEADLESS)

args = []
if HEADLESS:
    args.append("--headless")

connection_params = StdioServerParameters(
    command="npx",
    args=["-y", "@playwright/mcp@latest"]+args,
    env=os.environ.copy()
)


print(connection_params)

playwright_toolset = McpToolset(
    connection_params=connection_params,
)

print(playwright_toolset)