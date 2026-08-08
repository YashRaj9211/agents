import os
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

# Name of the Docker MCP profile to run (defaults to 'my_agent')
DOCKER_MCP_PROFILE_NAME = os.getenv("DOCKER_MCP_PROFILE", "my_agent")

def create_docker_mcp_toolset(profile: str = DOCKER_MCP_PROFILE_NAME, timeout: float = 60.0) -> McpToolset:
    """
    Creates an ADK McpToolset connected to Docker MCP Gateway using a specified profile.
    
    Command executed: docker mcp gateway run --profile <profile>
    """
    server_params = StdioServerParameters(
        command="docker",
        args=["mcp", "gateway", "run", "--profile", profile],
        env=os.environ.copy()
    )
    
    connection_params = StdioConnectionParams(
        server_params=server_params,
        timeout=timeout
    )
    
    return McpToolset(
        connection_params=connection_params
    )

docker_mcp_toolset = create_docker_mcp_toolset(DOCKER_MCP_PROFILE_NAME)
