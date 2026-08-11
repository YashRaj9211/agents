import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from tools import RESUME_TOOLS


load_dotenv()

prompt = """You are a professional job assist agent. You can assist users with job-related tasks.
Use the generate_resume_pdf tool when a user asks to generate, create, or export a resume to PDF.
"""

job_assist_agent = LlmAgent(
    model=LiteLlm(
        model=os.getenv("JOB_ASSIST_AGENT") or os.getenv("ROOT_AGENT"),
        api_base=os.getenv("JOB_ASSIST_AGENT_BASE_URL") or os.getenv("ROOT_AGENT_BASE_URL"),
        api_key=os.getenv("JOB_ASSIST_AGENT_KEY") or os.getenv("ROOT_AGENT_KEY"),
        custom_llm_provider="openai",
    ),
    name="job_assist_agent",
    description="A Job Assist agent that can assist users with job-related tasks.",
    instruction=prompt,
    tools=RESUME_TOOLS,
)
