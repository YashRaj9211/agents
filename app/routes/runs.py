"""
Run management routes.

These expose the fleet that ``app.services.run_manager`` maintains:

* list / inspect live and historical runs,
* attach to a run's event stream (replay + live tail),
* cancel a run or a session's active run,
* inspect peer messages queued for a session.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.agent_controller import parse_uuid_or_derive
from app.controllers.run_controller import RunController
from app.core.dependencies import get_db_session
from app.schemas.run import (
    CancelRunResponse,
    PendingMessageItem,
    PendingMessagesResponse,
    RunDetail,
    RunListResponse,
)
from app.services.agent_mailbox_service import AgentMailboxService
from app.services.run_manager import RunManager, get_run_manager
from db.repository import Repository

logger = logging.getLogger("app.routes.runs")

router = APIRouter(tags=["Runs"])


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@router.get("/runs", response_model=RunListResponse)
async def list_runs(
    status_filter: Optional[str] = Query(
        default="running",
        alias="status",
        description="'running' (live only), 'all', or a specific run status",
    ),
    session_id: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db_session),
):
    return await RunController.list_runs(
        db, status=status_filter, session_id=session_id, limit=limit
    )


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(run_id: str, db: AsyncSession = Depends(get_db_session)):
    detail = await RunController.get_run(db, run_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found"
        )
    return detail


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str, cursor: int = Query(default=0, ge=0)):
    """Attaches to a run: replays buffered events from ``cursor`` then live-tails."""
    manager = get_run_manager()
    handle = manager.get(run_id)
    if handle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' is not live in this process; read its messages instead",
        )

    return StreamingResponse(
        _sse_frames(manager, handle.run_id, cursor),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _sse_frames(manager: RunManager, run_id, cursor: int):
    """Adapts the run manager's event generator into SSE frames."""
    async for event in manager.subscribe(run_id, cursor=cursor, emit_attach=True):
        yield _sse(event)


@router.post("/runs/{run_id}/cancel", response_model=CancelRunResponse)
async def cancel_run(
    run_id: str,
    cascade: bool = Query(default=True, description="Also cancel runs this run spawned"),
    reason: Optional[str] = None,
):
    manager = get_run_manager()
    result = await manager.cancel_run(run_id, cascade=cascade, reason=reason)
    if result.get("status") == "not_found" and not result.get("cancelled_children"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found"
        )
    return CancelRunResponse(
        success=bool(result.get("success")),
        run_id=result.get("run_id") or run_id,
        status=result.get("status") or "unknown",
        cancelled=bool(result.get("cancelled")),
        cancelled_children=result.get("cancelled_children") or [],
        message=reason,
    )


@router.post("/sessions/{session_id}/cancel", response_model=CancelRunResponse)
async def cancel_session_run(session_id: str, reason: Optional[str] = None):
    manager = get_run_manager()
    session_uuid = parse_uuid_or_derive(session_id)
    result = await manager.cancel_session(session_uuid, reason=reason)
    return CancelRunResponse(
        success=bool(result.get("success")),
        run_id=result.get("run_id"),
        session_id=str(session_uuid),
        status=result.get("status") or "idle",
        cancelled=bool(result.get("cancelled")),
        message=reason,
    )


@router.get("/sessions/{session_id}/messages/pending", response_model=PendingMessagesResponse)
async def list_pending_peer_messages(
    session_id: str, db: AsyncSession = Depends(get_db_session)
):
    session_uuid = parse_uuid_or_derive(session_id)
    sess = await Repository.get_session(db, session_uuid)
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Session '{session_id}' not found"
        )
    pending = await AgentMailboxService.pending_summaries(session_uuid)
    return PendingMessagesResponse(
        session_id=str(session_uuid),
        total=len(pending),
        messages=[PendingMessageItem(**item) for item in pending],
    )
