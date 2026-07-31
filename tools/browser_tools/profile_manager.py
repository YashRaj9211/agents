"""
Browser Profile Manager
-----------------------
ADK-compatible tools for creating, listing, and deleting named browser
profiles.  Each profile stores a Playwright persistent-context directory
under  <project_root>/browser_profiles/<profile_name>/.

Usage (agent):
    list_browser_profiles()          – list saved profiles
    create_browser_profile(name)     – open headed browser, user logs in
    delete_browser_profile(name)     – remove a profile
    get_profile_info(name)           – metadata for one profile
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ── Resolve project root (two levels up from this file) ──────────────────────
_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parents[2]          # agents/
PROFILES_DIR = _PROJECT_ROOT / "browser_profiles"
PROFILES_DIR.mkdir(exist_ok=True)

_METADATA_FILE = "metadata.json"


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _profile_path(profile_name: str) -> Path:
    return PROFILES_DIR / profile_name.strip()


def _read_metadata(profile_dir: Path) -> dict:
    meta_path = profile_dir / _METADATA_FILE
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"name": profile_dir.name, "created_at": "unknown", "description": ""}


def _write_metadata(profile_dir: Path, name: str, description: str = "") -> None:
    meta = {
        "name": name,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "description": description,
    }
    (profile_dir / _METADATA_FILE).write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public ADK tools
# ─────────────────────────────────────────────────────────────────────────────

def list_browser_profiles() -> str:
    """
    Lists all saved browser profiles in the browser_profiles directory.

    Returns a formatted string with profile names, creation dates, and
    descriptions. If no profiles exist, returns a helpful message.
    """
    profiles = [p for p in PROFILES_DIR.iterdir() if p.is_dir()]

    if not profiles:
        return (
            "No browser profiles found.\n"
            "Use create_browser_profile(profile_name) to create one.\n"
            f"Profiles are stored in: {PROFILES_DIR}"
        )

    lines = [f"Found {len(profiles)} browser profile(s):\n"]
    for p in sorted(profiles):
        meta = _read_metadata(p)
        desc = f"  Description : {meta['description']}" if meta.get("description") else ""
        lines.append(
            f"• {meta['name']}\n"
            f"  Created     : {meta.get('created_at', 'unknown')}\n"
            f"  Path        : {p}{chr(10) + desc if desc else ''}"
        )

    return "\n".join(lines)


def create_browser_profile(profile_name: str, description: str = "") -> str:
    """
    Creates a new browser profile by launching a headed (visible) browser
    session.  The user should log into the desired websites, then close
    the browser.  The session state (cookies, localStorage) is automatically
    saved to browser_profiles/<profile_name>/.

    Args:
        profile_name: A short identifier for this profile (e.g. "work", "personal").
        description:  Optional description of what accounts are saved here.

    Returns:
        Instructions / status message.
    """
    profile_name = profile_name.strip()
    if not profile_name:
        return "Error: profile_name cannot be empty."

    # Validate name (no path-traversal)
    if any(c in profile_name for c in r'/\\:*?"<>|'):
        return f"Error: profile_name '{profile_name}' contains invalid characters."

    profile_dir = _profile_path(profile_name)

    if profile_dir.exists():
        return (
            f"Profile '{profile_name}' already exists at {profile_dir}.\n"
            "To update it, log in again by using the same profile name -- "
            "existing session data will be updated."
        )

    profile_dir.mkdir(parents=True, exist_ok=True)
    _write_metadata(profile_dir, profile_name, description)

    # Launch headed Playwright MCP to let user log in
    user_data_arg = str(profile_dir)
    cmd = [
        "npx", "-y", "@playwright/mcp@latest",
        "--user-data-dir", user_data_arg,
    ]

    # On Windows, shell=True is needed to resolve npx from PATH
    is_windows = sys.platform == "win32"

    msg = (
        f"Launching a browser for profile '{profile_name}'...\n\n"
        f"  1. Log into all the websites you want saved in this profile.\n"
        f"  2. When finished, close the browser window.\n"
        f"  3. Your session will be saved to: {profile_dir}\n\n"
        f"Starting browser now..."
    )
    print(msg)

    try:
        subprocess.run(
            cmd,
            shell=is_windows,
            check=False,   # Don't raise if user Ctrl+C's
            env=os.environ.copy(),
        )
    except FileNotFoundError:
        shutil.rmtree(profile_dir, ignore_errors=True)
        return (
            "Error: 'npx' not found. Please ensure Node.js/npm is installed "
            "and available on PATH."
        )
    except KeyboardInterrupt:
        pass   # User closed the browser

    # Check if any data was actually saved
    saved_files = list(profile_dir.rglob("*"))
    if len(saved_files) <= 1:   # only metadata.json
        return (
            f"Warning: Profile '{profile_name}' was created but may be empty -- "
            "the browser might have closed before any session data was saved. "
            "Try creating the profile again and make sure to log in before closing."
        )

    return (
        f"Profile '{profile_name}' saved successfully!\n"
        f"   Path: {profile_dir}\n"
        f"   Files saved: {len(saved_files)}\n\n"
        f"To use this profile, say: 'Use the {profile_name} profile to ...'"
    )


def delete_browser_profile(profile_name: str) -> str:
    """
    Permanently deletes a saved browser profile and all its session data.

    Args:
        profile_name: The name of the profile to delete.

    Returns:
        Confirmation or error message.
    """
    profile_name = profile_name.strip()
    profile_dir = _profile_path(profile_name)

    if not profile_dir.exists():
        available = [p.name for p in PROFILES_DIR.iterdir() if p.is_dir()]
        return (
            f"Profile '{profile_name}' does not exist.\n"
            f"Available profiles: {available}"
        )

    try:
        shutil.rmtree(profile_dir)
        return f"Profile '{profile_name}' deleted successfully."
    except PermissionError as e:
        return f"Error deleting profile '{profile_name}': {e}"


def get_profile_info(profile_name: str) -> str:
    """
    Returns metadata and details about a specific saved browser profile.

    Args:
        profile_name: The name of the profile to inspect.

    Returns:
        Formatted profile information string.
    """
    profile_name = profile_name.strip()
    profile_dir = _profile_path(profile_name)

    if not profile_dir.exists():
        return f"Profile '{profile_name}' does not exist."

    meta = _read_metadata(profile_dir)
    all_files = list(profile_dir.rglob("*"))
    total_size = sum(f.stat().st_size for f in all_files if f.is_file())

    return (
        f"Profile: {meta.get('name', profile_name)}\n"
        f"Created : {meta.get('created_at', 'unknown')}\n"
        f"Description: {meta.get('description', '(none)')}\n"
        f"Path    : {profile_dir}\n"
        f"Files   : {len(all_files)}\n"
        f"Size    : {total_size / 1024:.1f} KB"
    )
