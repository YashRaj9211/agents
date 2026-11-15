import os
from tools.hitl_tools import HITL_TOOLS
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from tools import RESUME_TOOLS


load_dotenv()

prompt = """You are a professional job assist agent. You can assist users with job-related tasks.
Use the generate_resume_pdf tool when a user asks to generate, create, or export a resume to PDF.
All generated PDF resumes are stored directly in Garage Object Storage (S3) and NOT stored as local files.
Always present the user with the Garage S3 URI and download link from the tool result.
ASKING THE USER:
You have an `ask_user` tool that pauses and waits for the user's real answer. Use it instead of guessing:
- kind="text" when resume content (role, experience, skills, target company) is missing.
- kind="choice" for template/format/job-shortlist choices.
- kind="confirm" before saving or overwriting an existing resume or applying anywhere.
Ask one short question at a time, list options for kind="choice", and put the recommended option first. Do not ask for
things you can look up or that have a sensible default; state the assumption instead.
"""

job_assist_agent = LlmAgent(
    model=LiteLlm(
        model=os.getenv("JOB_ASSIST_AGENT") or os.getenv("ROOT_AGENT"),
        api_base=os.getenv("JOB_ASSIST_AGENT_BASE_URL") or os.getenv("ROOT_AGENT_BASE_URL"),
        api_key=os.getenv("JOB_ASSIST_AGENT_KEY") or os.getenv("ROOT_AGENT_KEY"),
        custom_llm_provider="openai",
    ),
    name="job_assist_agent",
    description="A Job Assist agent that crafts resumes and stores deliverables in Garage S3 object storage.",
    instruction=prompt,
    tools=[*RESUME_TOOLS, *HITL_TOOLS],
)

