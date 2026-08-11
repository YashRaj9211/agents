import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from tools import CLI_TOOLS

load_dotenv()

prompt = """You are a CLI handling agent. You can execute shell and system commands to perform actions on the local environment using your CLI tools.
Perform operations carefully, noting any command outputs or errors.
"""

cli_agent = LlmAgent(
    model=LiteLlm(
        model=os.getenv("CLI_AGENT") or os.getenv("ROOT_AGENT"),
        api_base=os.getenv("CLI_AGENT_BASE_URL") or os.getenv("ROOT_AGENT_BASE_URL"),
        api_key=os.getenv("CLI_AGENT_KEY") or os.getenv("ROOT_AGENT_KEY"),
        custom_llm_provider="openai",
    ),
    name="cli_agent",
    description="A CLI agent that can run terminal commands, execute shells, and interact with command line tools.",
    instruction=prompt,
    tools=CLI_TOOLS,
)
