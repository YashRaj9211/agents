"""Per-site rate limiter to avoid automated detection."""
from __future__ import annotations

import asyncio
import json
import random

CATEGORY = "storage"

SCHEMA = {
    "type": "function",
    "function": {
        "name": "throttle",
        "description": "Applies a sleep with jitter to rate-limit actions on a specific site.",
        "parameters": {
            "type": "object",
            "properties": {
                "site": {
                    "type": "string",
                    "description": "The site identifier (e.g. 'greenhouse')."
                }
            },
            "required": ["site"]
        }
    }
}


# Simple global tracker for last action time per site.
# In a distributed system this would be in Redis.
_last_action_time: dict[str, float] = {}


async def throttle(site: str) -> str:
    """
    Sleeps for a random duration between 2 and 5 seconds.
    In a real system, you'd pull base intervals from config.yaml.
    """
    try:
        delay = random.uniform(2.0, 5.0)
        await asyncio.sleep(delay)
        return json.dumps({"status": f"Throttled {site} for {delay:.2f}s"})
    except Exception as e:
        return json.dumps({"error": f"Throttle failed: {e}"})
