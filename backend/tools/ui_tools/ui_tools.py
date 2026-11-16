"""``render_ui``: lets an agent show a rich HTML view in the app's side panel."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from tools.orchestration_tools.orchestration_tools import _caller_identity
from tools.ui_tools import ui_store

try:  # ADK is an optional import at tool-definition time in tests.
    from google.adk.tools.tool_context import ToolContext
except Exception:  # pragma: no cover
    ToolContext = Any  # type: ignore[assignment]

logger = logging.getLogger("tools.ui")


def render_ui(
    title: str,
    html: str,
    kind: str = "general",
    panel_id: Optional[str] = None,
    tool_context: ToolContext = None,  # type: ignore[assignment]
) -> Dict[str, Any]:
    """Display a rich, interactive HTML view in the user's side panel next to the chat.

    Pass ONE complete, self-contained HTML document (inline <style> and <script>; no
    build step). It renders in a sandboxed iframe: scripts run, but it has no access
    to the app, cookies or storage, and cannot call back to the backend. External
    libraries may be loaded from a CDN (cdnjs.cloudflare.com, cdn.jsdelivr.net).

    Args:
        title: Short tab title, e.g. "Cart total" or "Top tech news".
        html: The full HTML document, starting with <!doctype html>.
        kind: Free-form label such as "dashboard", "table", "cards", "calculator", "chart".
        panel_id: Pass the id returned earlier to UPDATE that panel in place instead of
            opening a new one.

    Returns:
        {"success": True, "panel_id": ...}. Mention in your reply that the view is open
        in the side panel; do not paste the HTML into your answer.
    """
    if not html or "<" not in html:
        return {"success": False, "error": "html must be a complete HTML document"}

    caller = _caller_identity(tool_context)
    session_uuid = caller["session_uuid"] if caller else None
    if session_uuid is None:
        # Inside an AgentTool sub-agent the ADK session is not ours; fall back to the run's.
        from app.services.run_context import current_session_id

        session_uuid = current_session_id.get()
    session_id = str(session_uuid) if session_uuid else None
    try:
        record = ui_store.save_panel(
            title=title, html=html, session_id=session_id, kind=kind, panel_id=panel_id
        )
    except ValueError as exc:
        return {"success": False, "error": str(exc)}

    if session_uuid:
        try:
            from app.services.run_manager import get_run_manager

            manager = get_run_manager()
            run_id = manager.active_run_id_for_session(session_uuid)
            if run_id:
                manager.publish(
                    run_id,
                    {
                        "type": "ui_panel",
                        "panel_id": record["id"],
                        "title": record["title"],
                        "kind": record["kind"],
                        "version": record["version"],
                        "run_id": str(run_id),
                    },
                )
        except Exception as exc:  # the panel is saved; the UI can still list it
            logger.warning("could not publish ui_panel event: %s", exc)

    return {
        "success": True,
        "panel_id": record["id"],
        "version": record["version"],
        "message": f"'{record['title']}' is now open in the side panel.",
    }
