"""Tool to extract full job details from a specific URL."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from browser_mcp.client import PlaywrightMcpClient

CATEGORY = "web"

SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_job_details",
        "description": "Navigates to a job URL and extracts the full job description text.",
        "parameters": {
            "type": "object",
            "properties": {
                "job_url": {
                    "type": "string",
                    "description": "URL of the job posting."
                }
            },
            "required": ["job_url"]
        }
    }
}


async def get_job_details(browser: "PlaywrightMcpClient", job_url: str) -> str:
    """Navigates to a URL and tries to extract the main body text."""
    try:
        nav_res = await browser.call_tool("browser_navigate", {"url": job_url})
        if "error" in nav_res.lower() and not nav_res.startswith("{"): 
            # some error strings might not be json
            return json.dumps({"error": f"Failed to navigate: {nav_res}"})
            
        # In a real implementation, we would extract the text of the body or main content div.
        # Playwright MCP doesn't have a direct "get full page text" tool that is clean,
        # but you can evaluate JS.
        eval_res = await browser.call_tool("browser_evaluate", {
            "script": "document.body.innerText"
        })
        
        return eval_res
    except Exception as e:
        return json.dumps({"error": f"Failed to get details for {job_url}: {e}"})
