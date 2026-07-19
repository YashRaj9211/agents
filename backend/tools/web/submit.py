"""Safety-gated submit tool to finalize applications."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from browser_mcp.client import PlaywrightMcpClient

CATEGORY = "web"

SCHEMA = {
    "type": "function",
    "function": {
        "name": "submit_application",
        "description": "Clicks the final submit button. MUST be confirmed by a human.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector for the submit button."
                },
                "confirm": {
                    "type": "boolean",
                    "description": "Safety gate. Must be explicitly True."
                }
            },
            "required": ["selector", "confirm"]
        }
    }
}


async def submit_application(browser: "PlaywrightMcpClient", selector: str, confirm: bool = False) -> str:
    """Clicks submit ONLY if confirm is True."""
    if not confirm:
        return json.dumps({
            "error": "Safety violation: submit_application called without confirm=True. "
                     "In dry-run mode, you must stop before this step."
        })
        
    try:
        res = await browser.call_tool("browser_click", {"selector": selector})
        return res
    except Exception as e:
        return json.dumps({"error": f"Failed to submit: {e}"})
