"""
Application Configuration settings loaded from environment.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _resolve_sqlite_url(url: str) -> str:
    """Makes relative sqlite file paths absolute (against the repo root) and
    ensures the parent directory exists. Non-sqlite / in-memory URLs pass through."""
    prefix, sep, path = url.partition(":///")
    if not sep or not prefix.startswith("sqlite") or not path or path.startswith(":memory:"):
        return url
    p = Path(path)
    if not p.is_absolute():
        p = _REPO_ROOT / p
    p.parent.mkdir(parents=True, exist_ok=True)
    return f"{prefix}:///{p.as_posix()}"


class Settings:
    PROJECT_NAME: str = "Agents Backend API"
    DESCRIPTION: str = "Multi-Agent Orchestrator API with Modular Routing and Persistent Storage"
    VERSION: str = "1.2.0"
    API_PREFIX: str = "/api"

    # Database (connects to PostgreSQL in Docker mapped to localhost:5432)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/agents"
    )

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    # S3 / Garage (connects to Garage S3 in Docker mapped to localhost:3900)
    S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL", "http://localhost:3900")
    S3_REGION: str = os.getenv("S3_REGION", "garage")
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "GK0123456789abcdef01234567")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef")
    S3_BUCKET: str = os.getenv("S3_BUCKET", "agents-artifacts")

    # Local Chroma Vector DB (connects to Chroma in Docker mapped to localhost:8001)
    CHROMA_SERVER_HOST: str = os.getenv("CHROMA_SERVER_HOST", "localhost")
    CHROMA_SERVER_HTTP_PORT: int = int(os.getenv("CHROMA_SERVER_HTTP_PORT", "8001"))

    # ───────── Run management (parallel agents) ─────────
    # Agents execute in background tasks owned by app.services.run_manager, so a
    # run outlives the HTTP stream that started it. These knobs bound that fleet.
    MAX_CONCURRENT_RUNS: int = int(os.getenv("MAX_CONCURRENT_RUNS", "8"))
    RUN_EVENT_BUFFER_SIZE: int = int(os.getenv("RUN_EVENT_BUFFER_SIZE", "2000"))
    RUN_CANCEL_TIMEOUT_SECONDS: float = float(os.getenv("RUN_CANCEL_TIMEOUT_SECONDS", "10"))
    RUN_HEARTBEAT_SECONDS: float = float(os.getenv("RUN_HEARTBEAT_SECONDS", "15"))

    # Agent-to-agent messaging: how many hops a single peer conversation may take
    # before the chain is expired instead of answered.
    AGENT_REPLY_HOP_LIMIT: int = int(os.getenv("AGENT_REPLY_HOP_LIMIT", "6"))

    # ───────── Human-in-the-loop ─────────
    # How long an `ask_user` tool call blocks before it gives up and lets the
    # agent continue. The run is not cancelled, just unblocked, so the UI can
    # show "no answer received" instead of waiting forever.
    HITL_TIMEOUT_SECONDS: float = float(os.getenv("HITL_TIMEOUT_SECONDS", "600"))
    # How much of a tool call's arguments/outputs is echoed into the SSE stream
    # for the steps panel. Bounded so a huge file write cannot bloat the buffer.
    TOOL_STREAM_DETAIL_CHARS: int = int(os.getenv("TOOL_STREAM_DETAIL_CHARS", "600"))

    # ADK's own session/event store. This MUST NOT be the application database:
    # ADK's v1 schema declares a `sessions` table (plus `events`, `app_states`,
    # `user_states`, `adk_internal_metadata`) that collides with this app's
    # `sessions` table, and create_all(checkfirst=True) would silently skip it.
    # The default is anchored to the repo root (not the process CWD) so starting
    # the server from backend/ doesn't hit "unable to open database file".
    ADK_SESSION_DB_URL: str = _resolve_sqlite_url(
        os.getenv("ADK_SESSION_DB_URL", "sqlite+aiosqlite:///./data/agents_adk_sessions.db")
    )

    # Default catalog seeds
    DEFAULT_AGENTS: List[Dict[str, Any]] = [
        {"id": "root_agent", "name": "Root Orchestrator", "description": "Central orchestrator coordinating specialized sub-agents", "kind": "root"},
        {"id": "browser_agent", "name": "Browser Agent", "description": "Playwright browser automation and web navigation", "kind": "worker"},
        {"id": "cli_agent", "name": "CLI Agent", "description": "Terminal command and shell execution", "kind": "worker"},
        {"id": "scheduler_agent", "name": "Scheduler Agent", "description": "Task scheduling, cron jobs, and background timers", "kind": "scheduler"},
        {"id": "job_assist_agent", "name": "Job Assist Agent", "description": "Job hunting and professional PDF resume generation", "kind": "worker"},
        {"id": "firecrawl_agent", "name": "Firecrawl Agent", "description": "Web scraping, crawling, and structured JSON extraction", "kind": "worker"},
        {"id": "job_scout_agent", "name": "Job Scout", "description": "Browses job sites with a saved profile and collects ~100 real postings", "kind": "worker"},
        {"id": "job_matcher_agent", "name": "Job Matcher", "description": "Scores and explains how well each job fits your profile", "kind": "worker"},
        {"id": "resume_tailor_agent", "name": "Resume Tailor", "description": "Writes a job-specific single-file HTML/CSS resume", "kind": "worker"},
    ]

    DEFAULT_QUICK_ACTIONS: List[Dict[str, Any]] = [
        {
            "id": "firecrawl_laya",
            "emoji": "🔍",
            "title": "Crawl GitHub repository",
            "description": "Scrape repo & extract description using firecrawl_agent",
            "prompt": "crawl https://github.com/NandhaKishorM/laya this link and provide me one description about this repository",
            "colorScheme": "orange",
            "target_agent_id": "firecrawl_agent",
        },
        {
            "id": "browser_action",
            "emoji": "🌐",
            "title": "Run browser task",
            "description": "Automate forms, research, or scrape data with Playwright",
            "prompt": "Browse to news.ycombinator.com and summarize the top 5 articles with browser_agent",
            "colorScheme": "purple",
            "target_agent_id": "browser_agent",
        },
        {
            "id": "job_assist",
            "emoji": "📄",
            "title": "Generate resume",
            "description": "Craft tailored PDF resume using job_assist_agent",
            "prompt": "Generate an updated resume PDF tailored for an AI Research Engineer position",
            "colorScheme": "green",
            "target_agent_id": "job_assist_agent",
        },
        {
            "id": "job_hunt",
            "emoji": "🎯",
            "title": "Find me jobs",
            "description": "Scout ~100 jobs, rank them, tailor resumes",
            "prompt": "Run the full job hunt: scout about 100 jobs for me, match them to my profile, then tailor resumes for the top 5.",
            "colorScheme": "purple",
            "target_agent_id": "root_agent",
        },
        {
            "id": "cli_diagnostics",
            "emoji": "💻",
            "title": "System diagnostics",
            "description": "Run shell inspection and resource report with cli_agent",
            "prompt": "Show system status and disk space using cli_agent",
            "colorScheme": "blue",
            "target_agent_id": "cli_agent",
        },
    ]


settings = Settings()
