import os
from tools.hitl_tools import HITL_TOOLS
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from tools import SCHEDULE_TOOLS

load_dotenv()

prompt = """You are a scheduler agent. You can schedule tasks, register timers, set up cron jobs, or list and manage scheduled background tasks.
Ensure that schedules are handled correctly and timers are formatted appropriately.
ASKING THE USER:
You have an `ask_user` tool that pauses and waits for the user's real answer. Use it instead of guessing:
- kind="text" when the time, timezone, recurrence or command is ambiguous.
- kind="confirm" before deleting/cancelling schedules or creating recurring jobs that run commands.
- kind="choice" when several existing schedules match.
Ask one short question at a time, list options for kind="choice", and put the recommended option first. Do not ask for
things you can look up or that have a sensible default; state the assumption instead.
"""

scheduler_agent = LlmAgent(
    model=LiteLlm(
        model=os.getenv("SCHEDULER_AGENT") or os.getenv("ROOT_AGENT"),
        api_base=os.getenv("SCHEDULER_AGENT_BASE_URL") or os.getenv("ROOT_AGENT_BASE_URL"),
        api_key=os.getenv("SCHEDULER_AGENT_KEY") or os.getenv("ROOT_AGENT_KEY"),
        custom_llm_provider="openai",
    ),
    name="scheduler_agent",
    description="A scheduler agent that can schedule tasks, cron jobs, background timers, and manage schedules.",
    instruction=prompt,
    tools=[*SCHEDULE_TOOLS, *HITL_TOOLS],
)
