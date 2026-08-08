"""
browser_tools package
---------------------
Exports all browser-related ADK tools.
"""

from tools.browser_tools.profile_manager import (
    list_browser_profiles,
    create_browser_profile,
    delete_browser_profile,
    get_profile_info,
)
from tools.browser_tools.set_browser_profile import set_browser_profile

BROWSER_PROFILE_TOOLS = [
    list_browser_profiles,
    create_browser_profile,
    delete_browser_profile,
    get_profile_info,
    set_browser_profile,
]

__all__ = [
    "list_browser_profiles",
    "create_browser_profile",
    "delete_browser_profile",
    "get_profile_info",
    "set_browser_profile",
    "BROWSER_PROFILE_TOOLS",
]
