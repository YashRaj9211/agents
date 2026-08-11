import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from tools import RESUME_TOOLS

load_dotenv()

prompt = """You are a professional resume agent. You can generate professionally formatted PDF resumes based on structured user data.
Use the generate_resume_pdf tool when a user asks to generate, create, or export a resume to PDF.
"""

resume_agent = LlmAgent(
    model=LiteLlm(
        model=os.getenv("RESUME_AGENT") or os.getenv("ROOT_AGENT"),
        api_base=os.getenv("RESUME_AGENT_BASE_URL") or os.getenv("ROOT_AGENT_BASE_URL"),
        api_key=os.getenv("RESUME_AGENT_KEY") or os.getenv("ROOT_AGENT_KEY"),
        custom_llm_provider="openai",
    ),
    name="resume_agent",
    description="A resume agent that can generate professionally formatted PDF resumes based on structured user data.",
    instruction=prompt,
    tools=RESUME_TOOLS,
)
