import os
import platform
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

def create_groww_mcp_toolset(timeout: float = 60.0) -> McpToolset:
    """
    Creates an ADK McpToolset connected to the Groww MCP server.
    """
    # Use npx.cmd on Windows to correctly resolve execution, otherwise npx
    command = "npx.cmd" if platform.system() == "Windows" else "npx"
    
    server_params = StdioServerParameters(
        command=command,
        args=[
            "mcp-remote@0.1.18",
            "https://mcp.groww.in/mcp",
            "52155"
        ],
        env=os.environ.copy()
    )
    
    connection_params = StdioConnectionParams(
        server_params=server_params,
        timeout=timeout
    )
    
    return McpToolset(
        connection_params=connection_params
    )

groww_mcp_toolset = create_groww_mcp_toolset()
