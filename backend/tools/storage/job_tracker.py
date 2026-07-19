"""SQLite-backed job application tracker."""
from __future__ import annotations

import sqlite3
import json
from pathlib import Path
from typing import Any

from config import settings

CATEGORY = "storage"

SCHEMA = {
    "type": "function",
    "function": {
        "name": "job_tracker",
        "description": "Tracks job application status.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["save_job", "update_status", "get_job", "list_jobs"]
                },
                "job_id": {"type": "string"},
                "company": {"type": "string"},
                "url": {"type": "string"},
                "status": {"type": "string"},
                "match_score": {"type": "integer"}
            },
            "required": ["action"]
        }
    }
}


class JobTracker:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.files_dir / ".." / "db" / "tracker.sqlite3"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    company TEXT,
                    url TEXT,
                    status TEXT,
                    match_score INTEGER,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def save_job(self, job_id: str, company: str, url: str, status: str, match_score: int) -> str:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO jobs (job_id, company, url, status, match_score)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    status=excluded.status,
                    match_score=excluded.match_score
            """, (job_id, company, url, status, match_score))
            conn.commit()
        return f"Saved job {job_id} ({status})"

    def update_status(self, job_id: str, status: str) -> str:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE jobs SET status=? WHERE job_id=?", (status, job_id))
            conn.commit()
        return f"Updated job {job_id} to {status}"

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row:
                return dict(row)
        return None


# Global instance
_tracker = None

def _get_tracker() -> JobTracker:
    global _tracker
    if not _tracker:
        _tracker = JobTracker()
    return _tracker


def job_tracker(action: str, **kwargs: Any) -> str:
    """Tool entry point for tracking jobs."""
    tracker = _get_tracker()
    
    try:
        if action == "save_job":
            return tracker.save_job(
                job_id=kwargs["job_id"],
                company=kwargs["company"],
                url=kwargs["url"],
                status=kwargs["status"],
                match_score=kwargs.get("match_score", 0)
            )
        elif action == "update_status":
            return tracker.update_status(kwargs["job_id"], kwargs["status"])
        elif action == "get_job":
            job = tracker.get_job(kwargs["job_id"])
            return json.dumps(job) if job else json.dumps({"error": "Not found"})
        elif action == "list_jobs":
            # For simplicity, returning a stub here. In reality you'd select *.
            return json.dumps({"error": "list_jobs not yet implemented"})
        else:
            return json.dumps({"error": f"Unknown action: {action}"})
    except Exception as e:
        return json.dumps({"error": f"Tracker error: {e}"})
