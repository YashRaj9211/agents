"""Tool to fill application form fields, handling credential injection securely."""
from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING
import os

if TYPE_CHECKING:
    from browser_mcp.client import PlaywrightMcpClient

CATEGORY = "web"

SCHEMA = {
    "type": "function",
    "function": {
        "name": "fill_application",
        "description": "Fills form fields on the current page using Playwright MCP.",
        "parameters": {
            "type": "object",
            "properties": {
                "fields": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "selector": {"type": "string", "description": "CSS selector for the input"},
                            "value": {"type": "string", "description": "Value to type or select"},
                            "type": {"type": "string", "enum": ["text", "select", "checkbox"], "description": "Type of interaction"}
                        },
                        "required": ["selector", "value", "type"]
                    },
                    "description": "List of fields to fill."
                }
            },
            "required": ["fields"]
        }
    }
}


def _resolve_credentials(value: str | dict[str, Any]) -> str:
    """If the value is a credential placeholder, resolve it from the environment."""
    if isinstance(value, dict) and "__credential__" in value:
        ref = value["__credential__"]
        site = ref.get("site")
        field = ref.get("field")
        # In a real system, you'd look this up in a DB or secure vault
        # For this prototype, we'll check env vars like GREENHOUSE_PASSWORD
        env_var = f"{site}_{field}".upper()
        secret = os.getenv(env_var)
        if not secret:
            raise ValueError(f"Credential {env_var} not found in environment.")
        return secret
    
    # If it's just a normal string
    if isinstance(value, str):
        return value
        
    return str(value)


async def fill_application(browser: "PlaywrightMcpClient", fields: list[dict[str, Any]]) -> str:
    """Iterate through fields and fill them using Playwright MCP tools."""
    results = []
    
    for field in fields:
        selector = field["selector"]
        field_type = field["type"]
        raw_value = field["value"]
        
        try:
            value = _resolve_credentials(raw_value)
            
            if field_type == "text":
                res = await browser.call_tool("browser_fill", {"selector": selector, "value": value})
                results.append(f"Filled {selector}: {'[SECRET]' if isinstance(raw_value, dict) else 'success'}")
            
            elif field_type == "select":
                # Assuming browser_evaluate to set select value since MCP might lack a native select tool
                script = f"""
                const el = document.querySelector("{selector}");
                if (el) {{ el.value = "{value}"; el.dispatchEvent(new Event('change')); }}
                """
                res = await browser.call_tool("browser_evaluate", {"script": script})
                results.append(f"Selected {selector}: success")
                
            elif field_type == "checkbox":
                action = "check" if value.lower() in ("true", "1", "yes") else "uncheck"
                # Evaluate script to click if needed
                script = f"""
                const el = document.querySelector("{selector}");
                if (el && el.checked !== {str(action == 'check').lower()}) {{ el.click(); }}
                """
                res = await browser.call_tool("browser_evaluate", {"script": script})
                results.append(f"Toggled {selector} to {action}")
                
        except Exception as e:
            results.append(f"Error on {selector}: {e}")
            
    return json.dumps({"results": results})
