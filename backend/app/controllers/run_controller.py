"""
Run controller: read models over the run manager and the agent-run trace.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import parse_uuid_or_derive
from app.core.config import settings
from app.schemas.run import RunDetail, RunListResponse, RunSummary
from app.services.run_manager import TERMINAL_RUN_STATUSES, get_run_manager
from db.repository import Repository

LIVE_STATUSES = {"running", "cancelling"}


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _origin_of(run) -> str:
    usage = run.usage if isinstance(run.usage, dict) else {}
    return str(usage.get("origin") or "user")


class RunController:
    @staticmethod
    async def list_runs(
        db: AsyncSession,
        status: Optional[str] = "running",
        session_id: Optional[str] = None,
        limit: int = 100,
    ) -> RunListResponse:
        """Merges live in-process runs with the persisted run trace.

        ``status="running"`` (the default) answers "what is happening now?" from
        the live registry, which is authoritative. ``all``/terminal statuses also
        include persisted rows so finished and interrupted runs stay visible.
        """
        manager = get_run_manager()
        session_uuid = parse_uuid_or_derive(session_id) if session_id else None

        live = manager.live_runs()
        if session_uuid is not None:
            live = [h for h in live if h.session_id == session_uuid]

        rows: List[RunSummary] = [
            RunSummary(
                run_id=str(h.run_id),
                session_id=str(h.session_id),
                agent_id=h.agent_id,
                status=h.status,
                origin=h.origin,
                parent_run_id=str(h.parent_run_id) if h.parent_run_id else None,
                started_at=_iso(h.started_at),
                finished_at=_iso(h.finished_at),
                elapsed_ms=h.elapsed_ms,
                live=True,
                error=h.error,
            )
            for h in sorted(live, key=lambda h: h.started_at, reverse=True)
        ]

        include_db = status in (None, "all") or status not in LIVE_STATUSES
        if include_db:
            live_ids = {r.run_id for r in rows}
            db_status = None if status in (None, "all") else status
            db_rows = await Repository.list_agent_runs(
                db, status=db_status, session_id=session_uuid, limit=limit
            )
            for run in db_rows:
                if str(run.id) in live_ids:
                    continue
                started = _iso(run.started_at)
                finished = _iso(run.finished_at)
                elapsed = None
                if run.started_at and run.finished_at:
                    elapsed = int((run.finished_at - run.started_at).total_seconds() * 1000)
                rows.append(
                    RunSummary(
                        run_id=str(run.id),
                        session_id=str(run.session_id) if run.session_id else None,
                        agent_id=run.agent_id,
                        status=run.status,
                        origin=_origin_of(run),
                        parent_run_id=str(run.parent_run_id) if run.parent_run_id else None,
                        started_at=started,
                        finished_at=finished,
                        elapsed_ms=elapsed,
                        live=False,
                        error=(run.error or {}).get("detail") if isinstance(run.error, dict) else None,
                    )
                )

        if limit > 0:
            rows = rows[:limit]
        await RunController._attach_session_titles(db, rows)

        return RunListResponse(
            runs=rows,
            active_count=manager.active_count(),
            limit=settings.MAX_CONCURRENT_RUNS,
        )

    @staticmethod
    async def _attach_session_titles(db: AsyncSession, rows: List[RunSummary]) -> None:
        session_ids = {r.session_id for r in rows if r.session_id}
        titles: Dict[str, str] = {}
        for sid in session_ids:
            try:
                sess = await Repository.get_session(db, uuid.UUID(str(sid)))
            except (ValueError, AttributeError):
                continue
            if sess:
                titles[str(sid)] = sess.title or "Conversation"
        for row in rows:
            if row.session_id:
                row.session_title = titles.get(row.session_id)

    @staticmethod
    async def get_run(db: AsyncSession, run_id: str) -> Optional[RunDetail]:
        manager = get_run_manager()
        handle = manager.get(run_id)
        if handle:
            return RunDetail(
                run_id=str(handle.run_id),
                session_id=str(handle.session_id),
                agent_id=handle.agent_id,
                status=handle.status,
                origin=handle.origin,
                parent_run_id=str(handle.parent_run_id) if handle.parent_run_id else None,
                started_at=_iso(handle.started_at),
                finished_at=_iso(handle.finished_at),
                elapsed_ms=handle.elapsed_ms,
                live=handle.status not in TERMINAL_RUN_STATUSES,
                error=handle.error,
                last_seq=handle.next_seq(),
                truncated=handle.truncated,
                final_output=handle.final_output or None,
                prompt_preview=(handle.prompt or "")[:200] or None,
            )

        run_uuid = parse_uuid_or_derive(run_id)
        run = await Repository.get_agent_run(db, run_uuid)
        if not run:
            return None

        started = _iso(run.started_at)
        finished = _iso(run.finished_at)
        elapsed = None
        if run.started_at and run.finished_at:
            elapsed = int((run.finished_at - run.started_at).total_seconds() * 1000)
        return RunDetail(
            run_id=str(run.id),
            session_id=str(run.session_id) if run.session_id else None,
            agent_id=run.agent_id,
            status=run.status,
            origin=_origin_of(run),
            parent_run_id=str(run.parent_run_id) if run.parent_run_id else None,
            started_at=started,
            finished_at=finished,
            elapsed_ms=elapsed,
            live=False,
            error=(run.error or {}).get("detail") if isinstance(run.error, dict) else None,
            last_seq=0,
            truncated=False,
        )
