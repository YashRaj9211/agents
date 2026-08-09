"""
Browser Profile Manager
-----------------------
ADK-compatible tools for creating, listing, and deleting named browser
profiles.  Each profile stores a full Chromium user-data directory under
<project_root>/browser_profiles/<profile_name>/.

Unlike a simple JSON cookie export, a Chromium user-data directory contains
EVERYTHING Chrome / Chromium stores locally:
  - Cookies (Cookies SQLite database)
  - LocalStorage / IndexedDB / SessionStorage
  - Disk cache
  - Browsing history
  - Preferences and extension state

When the Playwright MCP server is launched with
  --user-data-dir <profile_dir>
it picks up the entire saved state — the browser is already logged in to
whatever sites the user visited during profile creation.

Usage (agent):
    list_browser_profiles()            – list saved profiles
    create_browser_profile(name)       – open headed Chromium, user logs in,
                                         close browser → full profile saved
    update_browser_profile(name)       – re-open an existing profile to add /
                                         refresh logins
    delete_browser_profile(name)       – remove a profile
    get_profile_info(name)             – stats for one profile
"""

from __future__ import annotations

import json
import os
import shutil
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


def _write_metadata(profile_dir: Path, name: str, description: str = "",
                    existing_meta: dict | None = None) -> None:
    now = datetime.utcnow().isoformat() + "Z"
    meta = existing_meta.copy() if existing_meta else {}
    meta.update({
        "name": name,
        "description": description or meta.get("description", ""),
    })
    if "created_at" not in meta:
        meta["created_at"] = now
    meta["last_updated"] = now
    (profile_dir / _METADATA_FILE).write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )


def _validate_name(profile_name: str) -> str | None:
    """Returns an error string if invalid, else None."""
    if not profile_name:
        return "Error: profile_name cannot be empty."
    if any(c in profile_name for c in r'/\\:*?"<>|'):
        return f"Error: profile_name '{profile_name}' contains invalid characters."
    return None


def _count_profile_files(profile_dir: Path) -> tuple[int, float]:
    """Returns (file_count, total_size_kb) for a profile directory."""
    all_files = [f for f in profile_dir.rglob("*") if f.is_file()]
    total_size = sum(f.stat().st_size for f in all_files)
    return len(all_files), total_size / 1024


def _launch_persistent_browser(profile_dir: Path, page_title: str, instructions: str) -> str:
    """
    Launches a headed Chromium browser using playwright's async API inside a
    dedicated background thread (with its own event loop).

    ADK tool functions are called from within an already-running asyncio event
    loop, so using playwright.sync_api here would raise:
        "Please use the Async API instead."
    Running the async playwright code in a fresh thread+loop sidesteps this.

    The browser stays open until the user closes it.  All browser state
    (cookies, localStorage, cache, history, …) is written to ``profile_dir``
    by Chromium automatically.

    Returns a status message string.
    """
    try:
        from playwright.async_api import async_playwright  # noqa: F401
    except ImportError:
        return (
            "Error: The 'playwright' Python package is not installed.\n"
            "Run: pip install playwright && playwright install chromium"
        )

    print(instructions)

    PAGE_HTML = f"""
<!DOCTYPE html>
<html>
<head>
  <title>{page_title}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      max-width: 700px; margin: 60px auto; padding: 0 20px;
      background: #f8f9fa; color: #333;
    }}
    h1 {{ color: #1a73e8; }}
    .step {{ background: white; border-radius: 8px; padding: 16px 20px;
             margin: 12px 0; box-shadow: 0 1px 3px rgba(0,0,0,.12); }}
    .step b {{ color: #1a73e8; }}
    .note {{ background: #fff3cd; border-left: 4px solid #ffc107;
             padding: 10px 16px; border-radius: 4px; margin-top: 20px; }}
  </style>
</head>
<body>
  <h1>🔐 Browser Profile Setup</h1>
  <div class="step"><b>Step 1:</b> Open any website in this browser (use the address bar above)</div>
  <div class="step"><b>Step 2:</b> Log in to all the accounts you want saved in this profile</div>
  <div class="step"><b>Step 3:</b> When you're done, <b>close this browser window</b></div>
  <div class="note">
    ℹ️ Everything you do here is automatically saved — cookies, history,
    localStorage, and cache — just like a real Chrome user profile.
  </div>
</body>
</html>
"""

    result_holder: list[str] = []

    async def _run() -> None:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,
                args=[
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-blink-features=AutomationControlled",
                ],
                ignore_default_args=["--enable-automation"],
                viewport={"width": 1280, "height": 800},
            )

            page = context.pages[0] if context.pages else await context.new_page()
            await page.set_content(PAGE_HTML)

            # Block until the user closes all browser windows
            await context.wait_for_event("close", timeout=0)

        result_holder.append("ok")

    import asyncio
    import threading

    error_holder: list[str] = []

    def _thread_target() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run())
        except KeyboardInterrupt:
            result_holder.append("ok")
        except Exception as exc:
            error_holder.append(f"Error launching browser: {exc}")
        finally:
            loop.close()

    t = threading.Thread(target=_thread_target, daemon=True)
    t.start()
    t.join()  # wait for the user to close the browser

    if error_holder:
        return error_holder[0]

    return "ok"


# ─────────────────────────────────────────────────────────────────────────────
# Public ADK tools
# ─────────────────────────────────────────────────────────────────────────────

def list_browser_profiles() -> str:
    """
    Lists all saved browser profiles in the browser_profiles directory.

    Returns a formatted string with profile names, creation dates, descriptions,
    and storage size. If no profiles exist, returns a helpful message.
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
        file_count, size_kb = _count_profile_files(p)
        desc = f"  Description : {meta['description']}" if meta.get("description") else ""
        lines.append(
            f"• {meta['name']}\n"
            f"  Created     : {meta.get('created_at', 'unknown')}\n"
            f"  Last update : {meta.get('last_updated', 'unknown')}\n"
            f"  Storage     : {file_count} files, {size_kb:.1f} KB\n"
            f"  Path        : {p}"
            + (f"\n{desc}" if desc else "")
        )

    return "\n".join(lines)


def create_browser_profile(profile_name: str, description: str = "") -> str:
    """
    Creates a new browser profile by launching a headed (visible) Chromium
    browser session.

    A full Chromium user-data directory is saved — including cookies,
    LocalStorage, IndexedDB, disk cache, history, and preferences — exactly
    like a Chrome user profile on disk.  The user should:
      1. Log into the desired websites in the opened browser.
      2. Close the browser window when finished.

    The entire session state is automatically persisted to
    browser_profiles/<profile_name>/.  Subsequent browsing via Playwright MCP
    with this profile will start already logged in.

    Args:
        profile_name: A short identifier for this profile (e.g. "work", "personal").
        description:  Optional note describing what accounts are saved here.

    Returns:
        Instructions / status message.
    """
    profile_name = profile_name.strip()
    err = _validate_name(profile_name)
    if err:
        return err

    profile_dir = _profile_path(profile_name)

    if profile_dir.exists():
        return (
            f"Profile '{profile_name}' already exists at {profile_dir}.\n"
            "To add/refresh logins, use update_browser_profile(profile_name) instead."
        )

    profile_dir.mkdir(parents=True, exist_ok=True)
    _write_metadata(profile_dir, profile_name, description)

    instructions = (
        f"\n{'='*60}\n"
        f"  Creating profile: '{profile_name}'\n"
        f"  Path: {profile_dir}\n"
        f"{'='*60}\n"
        "  1. Log into all the websites you want saved in this profile.\n"
        "  2. When finished, CLOSE the browser window.\n"
        "  Your full session (cookies, cache, history) will be auto-saved.\n"
        f"{'='*60}\n"
    )

    result = _launch_persistent_browser(
        profile_dir=profile_dir,
        page_title=f"Profile Setup — {profile_name}",
        instructions=instructions,
    )

    if result != "ok":
        shutil.rmtree(profile_dir, ignore_errors=True)
        return result

    file_count, size_kb = _count_profile_files(profile_dir)

    # Only metadata — browser wrote nothing
    if file_count <= 1:
        return (
            f"⚠️  Warning: Profile '{profile_name}' appears empty.\n"
            "The browser may have been closed before any data was saved.\n"
            "Try create_browser_profile again and make sure to log in before closing."
        )

    _write_metadata(profile_dir, profile_name, description)  # update last_updated

    return (
        f"✅ Profile '{profile_name}' saved successfully!\n"
        f"   Path        : {profile_dir}\n"
        f"   Files saved : {file_count}\n"
        f"   Size        : {size_kb:.1f} KB\n\n"
        f"To use this profile: 'Use the {profile_name} profile to ...'"
    )


def update_browser_profile(profile_name: str) -> str:
    """
    Re-opens an existing browser profile so you can log into additional sites
    or refresh existing login sessions.

    The browser opens with all previously saved state loaded (you will already
    be logged in to sites from the last session).  Log into any additional
    sites, then close the browser — the updated state is saved automatically.

    Args:
        profile_name: The name of the existing profile to update.

    Returns:
        Status message.
    """
    profile_name = profile_name.strip()
    profile_dir = _profile_path(profile_name)

    if not profile_dir.exists():
        available = [p.name for p in PROFILES_DIR.iterdir() if p.is_dir()]
        return (
            f"Profile '{profile_name}' does not exist.\n"
            f"Available profiles: {available}\n"
            "Use create_browser_profile(profile_name) to create a new one."
        )

    meta = _read_metadata(profile_dir)

    instructions = (
        f"\n{'='*60}\n"
        f"  Updating profile: '{profile_name}'\n"
        f"  Path: {profile_dir}\n"
        f"{'='*60}\n"
        "  You are already logged in to previously saved sites.\n"
        "  Log into any additional sites or refresh sessions as needed.\n"
        "  When finished, CLOSE the browser window.\n"
        f"{'='*60}\n"
    )

    result = _launch_persistent_browser(
        profile_dir=profile_dir,
        page_title=f"Update Profile — {profile_name}",
        instructions=instructions,
    )

    if result != "ok":
        return result

    file_count, size_kb = _count_profile_files(profile_dir)
    _write_metadata(profile_dir, profile_name, meta.get("description", ""), existing_meta=meta)

    return (
        f"✅ Profile '{profile_name}' updated successfully!\n"
        f"   Files : {file_count}\n"
        f"   Size  : {size_kb:.1f} KB"
    )


def delete_browser_profile(profile_name: str) -> str:
    """
    Permanently deletes a saved browser profile and all its session data
    (cookies, cache, history, localStorage, etc.).

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
        return f"✅ Profile '{profile_name}' deleted successfully."
    except PermissionError as e:
        return f"Error deleting profile '{profile_name}': {e}"


def get_profile_info(profile_name: str) -> str:
    """
    Returns metadata and storage statistics about a specific saved browser profile.

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
    file_count, size_kb = _count_profile_files(profile_dir)

    # Try to find the Cookies file to confirm real browser data exists
    cookies_file = profile_dir / "Default" / "Cookies"
    has_real_data = cookies_file.exists()
    data_status = "✅ Full Chromium profile (cookies, cache, history saved)" \
        if has_real_data else "⚠️  No browser data found — profile may be empty"

    return (
        f"Profile : {meta.get('name', profile_name)}\n"
        f"Created : {meta.get('created_at', 'unknown')}\n"
        f"Updated : {meta.get('last_updated', 'unknown')}\n"
        f"Description: {meta.get('description', '(none)')}\n"
        f"Path    : {profile_dir}\n"
        f"Files   : {file_count}\n"
        f"Size    : {size_kb:.1f} KB\n"
        f"Status  : {data_status}"
    )
