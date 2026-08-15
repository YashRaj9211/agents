import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from tools import FILE_TOOLS

load_dotenv()

prompt = """You are a file handling agent. You can create, read, update, delete, list directories, and manage files on the system using your file tools.
Ensure you always perform operations accurately and safely.
"""

file_agent = LlmAgent(
    model=LiteLlm(
        model=os.getenv("FILE_AGENT") or os.getenv("ROOT_AGENT"),
        api_base=os.getenv("FILE_AGENT_BASE_URL") or os.getenv("ROOT_AGENT_BASE_URL"),
        api_key=os.getenv("FILE_AGENT_KEY") or os.getenv("ROOT_AGENT_KEY"),
        custom_llm_provider="openai",
    ),
    name="file_agent",
    description="A file handling agent that can list directories, read, write, append, edit, and delete files on the local filesystem.",
    instruction=prompt,
    tools=FILE_TOOLS,
)
