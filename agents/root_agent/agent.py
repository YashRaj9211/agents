import os
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from mcp_servers.plawright import playwright_toolset

api_base_url = "https://integrate.api.nvidia.com/v1"
model_name_at_endpoint = "nvidia/nemotron-3-super-120b-a12b"


prompt = """Your are the main head agent you use other sub-agents to achieve the goal that is asked by user and then combine their results to produce the final result

Rules:
1. First understand the user's request and break it down into smaller tasks
2. Assign each task to the appropriate sub-agent
3. Collect the results from all sub-agents
4. Combine the results to produce the final result
5. Return the final result in markdown format with tag <DONE>

Example:
User: "Find the weather in New York and the current time in New York"

Sub-agents:
1. Weather agent: Finds the weather in New York
2. Time agent: Finds the current time in New York

Final result: Combines the results from both sub-agents

Memory rules:
- You have a short-term memory to remember the conversation history
- You have a long-term memory to remember the results of previous tasks
- Use short-term memory to remember the current conversation
- Use long-term memory to remember the results of previous tasks

Output format:
- Return the final result in markdown format with tag <DONE>
"""
browser_agent = LlmAgent(
    model=LiteLlm(
        model="nvidia/nemotron-3-super-120b-a12b",
        api_base=api_base_url,
        api_key=os.getenv("BROWSER_MODEL_KEY"),
        custom_llm_provider="openai",
    ),
    name="browser_agent",
    instruction=prompt,
    tools=[playwright_toolset],
)

root_agent = browser_agent
print(browser_agent)