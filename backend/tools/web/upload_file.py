"""Tool to handle file uploads via browser MCP."""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from browser_mcp.client import PlaywrightMcpClient

CATEGORY = "web"

SCHEMA = {
    "type": "function",
    "function": {
        "name": "upload_file",
        "description": "Uploads a local file to a file input element.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector of the file input element (type='file')."
                },
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the local file to upload."
                }
            },
            "required": ["selector", "file_path"]
        }
    }
}


async def upload_file(browser: "PlaywrightMcpClient", selector: str, file_path: str) -> str:
    """Uploads a file to the specified input element."""
    path = Path(file_path).resolve()
    if not path.is_file():
        return json.dumps({"error": f"File not found: {file_path}"})
        
    try:
        # Playwright MCP exposes a set_input_files tool or similar. 
        # If not, we might have to use evaluate or assume a custom mcp tool.
        # Assuming the standard mcp server has `browser_set_input_files`.
        # If it doesn't, this will fail gracefully and the agent will know.
        res = await browser.call_tool("browser_set_input_files", {
            "selector": selector,
            "files": [str(path)]
        })
        return res
    except Exception as e:
        return json.dumps({"error": f"Failed to upload {file_path} to {selector}: {e}"})
