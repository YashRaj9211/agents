"""Tool to search job boards using the browser."""
from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING
import urllib.parse

from tools.schemas import JobPosting

if TYPE_CHECKING:
    from browser_mcp.client import PlaywrightMcpClient

CATEGORY = "web"

SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_jobs",
        "description": "Searches a specific job board for matching roles.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The job title or keywords to search for."
                },
                "location": {
                    "type": "string",
                    "description": "Location (e.g. 'Remote', 'Mumbai')."
                },
                "site": {
                    "type": "string",
                    "description": "The site identifier (e.g. 'greenhouse', 'linkedin')."
                }
            },
            "required": ["query", "location", "site"]
        }
    }
}


async def _search_greenhouse(browser: "PlaywrightMcpClient", query: str, location: str) -> list[JobPosting]:
    """
    Reference implementation for Greenhouse-style job boards.
    In reality, greenhouse doesn't have a central search, so this is a placeholder
    demonstrating how a site handler works. Let's mock a standard search URL structure.
    """
    # Navigate
    url = f"https://boards.greenhouse.io/embed/job_board?q={urllib.parse.quote(query)}"
    nav_res = await browser.call_tool("browser_navigate", {"url": url})
    if "error" in nav_res.lower():
        raise RuntimeError(f"Navigation failed: {nav_res}")
        
    # Wait for page to load (in a real scenario, use Playwright wait tools or sleep)
    # Get HTML/text content
    # For now, we return a mock because full DOM scraping via MCP requires 
    # chaining multiple calls (get elements, parse text) which is complex for this stub.
    # The actual implementation would use `browser_get_dom_elements` or similar MCP tools.
    
    # Mocking for the sake of the structural increment
    return [
        JobPosting(
            title=f"Senior {query} Engineer",
            company="Example Corp",
            url="https://boards.greenhouse.io/examplecorp/jobs/123",
            location=location,
            description="Mock description.",
            posted_date="2026-07-10"
        ),
        JobPosting(
            title=f"Lead {query} Developer",
            company="Example Corp",
            url="https://boards.greenhouse.io/examplecorp/jobs/124",
            location=location,
            description="Mock description 2.",
            posted_date="2026-07-11"
        )
    ]


SITE_HANDLERS = {
    "greenhouse": _search_greenhouse,
}


async def search_jobs(
    browser: "PlaywrightMcpClient", 
    query: str, 
    location: str, 
    site: str
) -> str:
    """Entry point for searching jobs across different sites."""
    handler = SITE_HANDLERS.get(site.lower())
    if not handler:
        return json.dumps({"error": f"Unsupported site: {site}. Available: {list(SITE_HANDLERS.keys())}"})
        
    try:
        jobs = await handler(browser, query, location)
        return json.dumps([job.model_dump() for job in jobs])
    except Exception as e:
        return json.dumps({"error": f"Search failed on {site}: {e}"})
