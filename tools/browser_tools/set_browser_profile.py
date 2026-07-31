"""
set_browser_profile.py
----------------------
ADK tool that sets the active browser profile for subsequent Playwright
sessions.  Call this BEFORE any navigation when the user specifies a
named profile.

The profile name is stored as a module-level variable in
mcp_servers.plawright so that the next create_playwright_toolset() call
picks it up.
"""

from __future__ import annotations

from pathlib import Path

# ── Resolve project root ──────────────────────────────────────────────────────
_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parents[2]
PROFILES_DIR = _PROJECT_ROOT / "browser_profiles"


def set_browser_profile(profile_name: str) -> str:
    """
    Sets the active browser profile that will be used for the next
    Playwright browser session.

    Call this tool FIRST whenever the user asks to use a named profile
    (e.g. "use my work profile", "use the 'personal' browser profile").
    After calling this tool, proceed with normal browser navigation —
    the browser will start already logged in to sites saved in that profile.

    To revert to a fresh/anonymous session (no logins), call this with
    profile_name="" or "default".

    Args:
        profile_name: Name of the saved profile (e.g. "work", "personal"),
                      or "" / "default" to use an ephemeral session.

    Returns:
        Confirmation string indicating which profile is now active.
    """
    import mcp_servers.plawright as pw_module

    profile_name = profile_name.strip()

    # Reset to ephemeral / default
    if profile_name in ("", "default", "none"):
        pw_module.set_active_profile(None)
        return (
            "Browser profile reset to default (ephemeral session). "
            "No saved logins will be used."
        )

    profile_dir = PROFILES_DIR / profile_name
    if not profile_dir.exists():
        available = [p.name for p in PROFILES_DIR.iterdir() if p.is_dir()] if PROFILES_DIR.exists() else []
        return (
            f"Profile '{profile_name}' not found.\n"
            f"Available profiles: {available or ['(none)']}\n"
            "Use create_browser_profile(profile_name) to create a new profile."
        )

    pw_module.set_active_profile(profile_name)
    return (
        f"Active browser profile set to '{profile_name}'.\n"
        f"Profile path: {profile_dir}\n"
        "The next browser session will use the saved logins from this profile."
    )
