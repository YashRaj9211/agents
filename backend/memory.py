"""Conversation history plus a JSONL trace for debugging an agent run."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from config import BASE_DIR


class Memory:
    def __init__(self, run_id: str) -> None:
        self.messages: list[dict[str, Any]] = []
        self.trace_path = BASE_DIR / "storage" / "logs" / f"{run_id}.jsonl"
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, message: dict[str, Any]) -> None:
        self.messages.append(message)
        with self.trace_path.open("a", encoding="utf-8") as trace:
            trace.write(json.dumps({"timestamp": time.time(), **message}, default=str) + "\n")
