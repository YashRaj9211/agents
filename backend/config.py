"""Application settings read from ``backend/.env``.

Keeping settings here means the rest of the project never needs to read
environment variables directly.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# pyrefly: ignore [missing-import]
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    # NVIDIA NIM is OpenAI-compatible. Any compatible provider can be used by
    # changing these three values in .env.
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")
    llm_model: str = os.getenv("LLM_MODEL", "")

    mcp_command: str = os.getenv("MCP_COMMAND", "npx.cmd")
    browser_profile_dir: Path = Path(
        os.getenv("BROWSER_PROFILE_DIR", str(BASE_DIR / "storage" / "browser-profile"))
    )
    max_steps: int = int(os.getenv("MAX_STEPS", "40"))

    @property
    def files_dir(self) -> Path:
        """The only directory local file tools may access."""
        return BASE_DIR / "storage" / "files"

    @property
    def db_path(self) -> Path:
        """The path to the SQLite tracking database."""
        path = Path(os.getenv("DB_PATH", str(BASE_DIR / "storage" / "db" / "tracker.sqlite3")))
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def mcp_args(self) -> list[str]:
        """Use one persistent browser profile so a user logs in only once."""
        return [
            "-y",
            "@playwright/mcp@latest",
            "--user-data-dir",
            str(self.browser_profile_dir),
            "--caps=pdf",
            "--output-dir",
            str(self.files_dir / "output"),
        ]


settings = Settings()
