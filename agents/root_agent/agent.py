import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from tools.utility_tools.getCurrTime import getCurrentTime
from mcp_servers.docker_mcp import docker_mcp_toolset
from mcp_servers.groww_mcp import groww_mcp_toolset
from agents.browser_agent.agent import browser_agent
from agents.file_agent.agent import file_agent
from agents.cli_agent.agent import cli_agent
from agents.scheduler_agent.agent import scheduler_agent
from agents.job_assist_agent.agent import job_assist_agent
from agents.firecrawl_agent.agent import firecrawl_agent

load_dotenv()

api_base_url = "https://integrate.api.nvidia.com/v1"
model_name_at_endpoint = "nvidia/nemotron-3-super-120b-a12b"


prompt = """You are the root agent. You coordinate specialized sub-agents to achieve the user's goals.
You have direct access to time and Docker containers.
You have the following sub-agents under your control:
1. `browser_agent`: An autonomous web browsing agent that can navigate websites, search the web, interact with web pages, and manage browser profiles.
2. `file_agent`: A file handling agent that can list directories, read, write, append, edit, and delete files on the local filesystem.
3. `cli_agent`: A CLI agent that can run terminal commands, execute shells, and interact with command line tools.
4. `scheduler_agent`: A scheduler agent that can schedule tasks, cron jobs, background timers, and manage schedules.
5. `job_assist_agent`: A job assist agent that can search for jobs, generate professionally formatted PDF resumes, and save resumes.
6. `firecrawl_agent`: A specialized web scraping, web search, crawling, sitemap mapping, and JSON extraction agent.

Always delegate tasks to the appropriate sub-agent rather than trying to perform them yourself. For example, delegate file operations to `file_agent`, running CLI commands to `cli_agent`, scheduling/timer tasks to `scheduler_agent`, web browsing tasks to `browser_agent`, job/resume tasks to `job_assist_agent`, and web scraping/crawling/extracting to `firecrawl_agent`.

===========================================
GENERAL RULES
===========================================
Memory rules:
- You have a short-term memory to remember the conversation history
- You have a long-term memory to remember the results of previous tasks
- Use short-term memory to remember the current conversation
- Use long-term memory to remember the results of previous tasks

Output format:
- Return the final result in markdown format with tag <DONE>
"""

root_agent = LlmAgent(
    model=LiteLlm(
        model=os.getenv("ROOT_AGENT"),
        api_base=os.getenv("ROOT_AGENT_BASE_URL"),
        api_key=os.getenv("ROOT_AGENT_KEY"),
        custom_llm_provider="openai",
    ),
    name="root_agent",
    instruction=prompt,
    tools=[
        getCurrentTime,
        # docker_mcp_toolset,
        # groww_mcp_toolset,
    ],
    sub_agents=[browser_agent, file_agent, cli_agent, scheduler_agent, job_assist_agent, firecrawl_agent],
)




