"""
Store for agent-generated UI panels (self-contained HTML documents).

One JSON file per panel under ``data/ui_panels/`` (override with ``UI_PANELS_DIR``).
Both the ``render_ui`` tool and the HTTP API go through this module.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_LOCK = threading.RLock()
MAX_HTML_BYTES = 500_000


def _root() -> Path:
    env = os.getenv("UI_PANELS_DIR")
    base = Path(env) if env else Path(__file__).resolve().parents[3] / "data" / "ui_panels"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _path(panel_id: str) -> Path:
    safe = "".join(c for c in panel_id if c.isalnum() or c in "-_")
    return _root() / f"{safe}.json"


def save_panel(
    *,
    title: str,
    html: str,
    session_id: Optional[str] = None,
    kind: str = "general",
    panel_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Creates a panel, or replaces ``panel_id`` in place (keeps created_at, bumps version)."""
    if len(html.encode("utf-8")) > MAX_HTML_BYTES:
        raise ValueError(f"html is too large (max {MAX_HTML_BYTES // 1000} KB)")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _LOCK:
        existing = get_panel(panel_id) if panel_id else None
        record = {
            "id": existing["id"] if existing else uuid.uuid4().hex[:12],
            "session_id": session_id or (existing or {}).get("session_id"),
            "title": title.strip() or "Untitled",
            "kind": kind,
            "html": html,
            "version": (existing["version"] + 1) if existing else 1,
            "created_at": existing["created_at"] if existing else now,
            "updated_at": now,
        }
        path = _path(record["id"])
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    return record


def get_panel(panel_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not panel_id:
        return None
    path = _path(panel_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def list_panels(session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Newest first, without the html body."""
    items: List[Dict[str, Any]] = []
    for p in _root().glob("*.json"):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if session_id and rec.get("session_id") != session_id:
            continue
        rec.pop("html", None)
        items.append(rec)
    items.sort(key=lambda r: r.get("updated_at", ""), reverse=True)
    return items


def delete_panel(panel_id: str) -> bool:
    path = _path(panel_id)
    if path.exists():
        path.unlink()
        return True
    return False
