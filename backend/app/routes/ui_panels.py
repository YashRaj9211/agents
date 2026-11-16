"""UI panels API: agent-generated HTML views shown beside the chat."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.controllers.agent_controller import parse_uuid_or_derive
from tools.ui_tools import ui_store

router = APIRouter(prefix="/ui-panels", tags=["UI Panels"])

# Even when opened directly in a tab the page is sandboxed (opaque origin).
_RAW_HEADERS = {
    "Content-Security-Policy": "sandbox allow-scripts allow-popups allow-forms allow-modals",
    "X-Content-Type-Options": "nosniff",
}


@router.get("")
async def list_panels(session_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    sid = str(parse_uuid_or_derive(session_id)) if session_id else None
    return {"panels": ui_store.list_panels(sid)}


@router.get("/{panel_id}")
async def get_panel(panel_id: str) -> Dict[str, Any]:
    panel = ui_store.get_panel(panel_id)
    if not panel:
        raise HTTPException(404, "Panel not found")
    return panel


@router.get("/{panel_id}/raw", response_class=HTMLResponse)
async def raw_panel(panel_id: str) -> HTMLResponse:
    panel = ui_store.get_panel(panel_id)
    if not panel:
        raise HTTPException(404, "Panel not found")
    return HTMLResponse(panel["html"], headers=_RAW_HEADERS)


@router.delete("/{panel_id}")
async def delete_panel(panel_id: str) -> Dict[str, Any]:
    if not ui_store.delete_panel(panel_id):
        raise HTTPException(404, "Panel not found")
    return {"status": "success", "deleted_id": panel_id}
