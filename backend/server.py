"""
Server entrypoint for Multi-Agent Orchestrator Platform.
Imports the configured modular FastAPI application from app.main.

Host/port and autoreload are overridable so this can run alongside other
services when the defaults (127.0.0.1:8000) are already taken:

    BACKEND_PORT=8021 python backend/server.py
"""
import os
from pathlib import Path

from app.main import app

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        app_dir=str(Path(__file__).resolve().parent),
        host=os.getenv("BACKEND_HOST", "127.0.0.1"),
        port=int(os.getenv("BACKEND_PORT", "8000")),
        reload=os.getenv("BACKEND_RELOAD", "true").lower() not in {"0", "false", "no"},
    )
