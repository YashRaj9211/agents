import os
from google.adk.tools.mcp_tool import McpToolset
from mcp import StdioServerParameters

# Name of the Docker MCP profile to run (defaults to 'my_agent')
PROFILE_NAME = os.getenv("DOCKER_MCP_PROFILE", "my_agent")

def create_docker_mcp_toolset(profile: str = PROFILE_NAME) -> McpToolset:
    """
    Creates an ADK McpToolset connected to Docker MCP Gateway using a specified profile.
    
    Command executed: docker mcp gateway run --profile <profile>
    """
    connection_params = StdioServerParameters(
        command="docker",
        args=["mcp", "gateway", "run", "--profile", profile],
        env=os.environ.copy()
    )
    
    return McpToolset(
        connection_params=connection_params
    )

docker_mcp_toolset = create_docker_mcp_toolset(PROFILE_NAME)
