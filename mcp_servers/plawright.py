"""
plawright.py
------------
Playwright MCP toolset factory.

Profile support
~~~~~~~~~~~~~~~
A module-level variable ``_active_profile`` stores the currently selected
browser profile name (or None for an ephemeral session).

Call ``set_active_profile(name)`` to switch profiles at runtime — the next
call to ``create_playwright_toolset()`` (or access of the lazy
``playwright_toolset`` property) will use the updated value.

Usage from agent code:
    from mcp_servers.plawright import playwright_toolset   # lazy singleton
    from mcp_servers.plawright import create_playwright_toolset  # explicit
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

# ── Headless mode ─────────────────────────────────────────────────────────────
# Set BROWSER_MODE=headless to run without a visible window.
HEADLESS = False

# ── Project root ──────────────────────────────────────────────────────────────
_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parent.parent      # agents/
_PROFILES_DIR = _PROJECT_ROOT / "browser_profiles"

# ── Active profile state ──────────────────────────────────────────────────────
_active_profile: Optional[str] = None


def set_active_profile(profile_name: Optional[str]) -> None:
    """
    Sets the browser profile that will be used by the next toolset created.

    Args:
        profile_name: Name of the saved profile, or None for ephemeral session.
    """
    global _active_profile
    _active_profile = profile_name or None


def get_active_profile() -> Optional[str]:
    """Returns the currently active profile name, or None if using ephemeral session."""
    return _active_profile


def _build_args(profile_name: Optional[str] = None) -> list[str]:
    """Builds the CLI args list for the Playwright MCP server."""
    args: list[str] = []

    if HEADLESS:
        args.append("--headless")

    # Resolve profile directory
    resolved_profile = profile_name if profile_name is not None else _active_profile
    if resolved_profile:
        profile_dir = _PROFILES_DIR / resolved_profile
        if profile_dir.exists():
            args += ["--user-data-dir", str(profile_dir)]
        else:
            # Profile doesn't exist — log a warning and fall back to ephemeral
            print(
                f"[plawright] Warning: profile '{resolved_profile}' not found at "
                f"{profile_dir}. Falling back to ephemeral session."
            )

    return args


def create_playwright_toolset(
    profile_name: Optional[str] = None,
    timeout: float = 60.0,
) -> McpToolset:
    """
    Creates an ADK McpToolset connected to the Playwright MCP server.

    Args:
        profile_name: Override the active profile for this specific toolset.
                      If None, uses whatever ``_active_profile`` is set to.
        timeout:      Connection timeout in seconds.

    Returns:
        A configured McpToolset instance.
    """
    args = _build_args(profile_name)

    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@playwright/mcp@latest"] + args,
        env=os.environ.copy(),
    )
    connection_params = StdioConnectionParams(
        server_params=server_params,
        timeout=timeout,
    )
    return McpToolset(connection_params=connection_params)


# ── Dynamic toolset getter ────────────────────────────────────────────────────
# Always returns a fresh McpToolset reflecting the *current* _active_profile.
# This avoids the stale-singleton problem where a toolset built at import time
# ignores any subsequent set_active_profile() calls.
#
# Usage in agent code:
#   from mcp_servers.plawright import get_playwright_toolset
#   tools = [get_playwright_toolset(), ...]
#
def get_playwright_toolset(timeout: float = 60.0) -> McpToolset:
    """Returns a new McpToolset configured for the currently active profile."""
    return create_playwright_toolset(timeout=timeout)


# Back-compat: kept for any code that still imports `playwright_toolset`.
# This is a module-level instance created at import time — it does NOT update
# when set_active_profile() is called later.  Prefer get_playwright_toolset().
playwright_toolset = create_playwright_toolset()