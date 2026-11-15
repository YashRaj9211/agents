"""
In-process run manager for parallel agent execution.

Why this exists
---------------
Agent execution used to happen *inside* the SSE generator of
``POST /api/chat/stream``, which tied a run's lifetime to the browser
connection. That made three things impossible: running several agents at once,
switching between running sessions without killing them, and stopping a run from
anywhere other than the tab that started it.

Here a run is a background :class:`asyncio.Task` owned by this manager. HTTP
streams only *observe* runs: they replay the run's bounded event buffer and then
live-tail it, so any number of viewers can attach, detach and re-attach.

Concurrency model
-----------------
* One active run per session. ``Repository.create_message`` allocates
  ``seq = max + 1`` and the ADK session context belongs to one conversation, so
  two runs on the same session would interleave replies and duplicate sequence
  numbers.
* A global cap (``MAX_CONCURRENT_RUNS``) bounds the fleet.

Everything in here runs on the single FastAPI event loop, which is why the
orchestration tools (``tools/orchestration_tools``) are ``async def``: ADK awaits
async tools on that same loop, so they need no threads or extra event loops.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger("app.services.run_manager")

#: Run rows in these states are never resumed. A restarted process closes out any
#: leftover ``running``/``cancelling`` row as ``failed`` with an "interrupted"
#: error, because ``schema.sql`` does not allow an ``interrupted`` status.
#: ``interrupted`` is still accepted here so rows written by older builds remain
#: terminal rather than appearing to run forever.
TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled", "interrupted"}

#: SSE frame types that end a stream. ``error`` is informational: a failed turn
#: still emits ``done`` (carrying the error text) so existing clients and
#: ``tests/test_ui_contract.py`` keep seeing ``start`` ... ``done``.
TERMINAL_EVENT_TYPES = {"done", "cancelled"}


class RunBusyError(RuntimeError):
    """Raised when a session already has an active run."""

    def __init__(self, session_id: uuid.UUID, active_run_id: Optional[uuid.UUID] = None):
        self.session_id = session_id
        self.active_run_id = active_run_id
        super().__init__(f"Session '{session_id}' already has an active run")


class RunCapacityError(RuntimeError):
    """Raised when the global concurrency cap is reached."""

    def __init__(self, limit: int):
        self.limit = limit
        super().__init__(f"Concurrent run limit ({limit}) reached")


@dataclass
class RunHandle:
    """Live state for one agent run."""

    run_id: uuid.UUID
    session_id: uuid.UUID
    agent_id: str
    prompt: str = ""
    origin: str = "user"
    parent_run_id: Optional[uuid.UUID] = None
    trigger_message_id: Optional[uuid.UUID] = None
    instance_id: Optional[uuid.UUID] = None
    reply_context: Optional[Dict[str, Any]] = None
    status: str = "running"
    cancel_requested: bool = False
    error: Optional[str] = None
    final_output: str = ""
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    events: List[Dict[str, Any]] = field(default_factory=list)
    first_seq: int = 0
    truncated: bool = False
    version: int = 0
    task: Optional[asyncio.Task] = None
    finalize_task: Optional[asyncio.Task] = None
    persist_task: Optional[asyncio.Task] = None
    terminal_published: bool = False
    _waiter: asyncio.Event = field(default_factory=asyncio.Event)

    # ───────── event buffer ─────────
    def publish(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Appends an event to the buffer and wakes every attached viewer."""
        seq = self.first_seq + len(self.events)
        item = {"seq": seq, **event}
        self.events.append(item)

        cap = settings.RUN_EVENT_BUFFER_SIZE
        if cap > 0 and len(self.events) > cap:
            drop = len(self.events) - cap
            del self.events[:drop]
            self.first_seq += drop
            self.truncated = True

        self.touch()
        return item

    def next_seq(self) -> int:
        return self.first_seq + len(self.events)

    def events_from(self, cursor: int) -> tuple[List[Dict[str, Any]], int, bool]:
        """Returns ``(events, effective_cursor, truncated)`` from ``cursor`` on."""
        truncated = False
        effective = cursor
        if effective < self.first_seq:
            effective = self.first_seq
            truncated = True
        index = max(0, effective - self.first_seq)
        return self.events[index:], effective, truncated

    def touch(self) -> None:
        """Bumps the version and wakes waiters without losing notifications.

        The waiter event is swapped *before* being set so a subscriber that
        captures the new one observes the bumped version instead of sleeping
        through the wakeup. All of this happens synchronously on the event loop,
        so there is no preemption between the version check and the capture.
        """
        self.version += 1
        waiter = self._waiter
        self._waiter = asyncio.Event()
        waiter.set()

    @property
    def elapsed_ms(self) -> int:
        end = self.finished_at if self.finished_at is not None else time.time()
        return int((end - self.started_at) * 1000)

    def summary(self) -> Dict[str, Any]:
        return {
            "run_id": str(self.run_id),
            "session_id": str(self.session_id),
            "agent_id": self.agent_id,
            "status": self.status,
            "origin": self.origin,
            "parent_run_id": str(self.parent_run_id) if self.parent_run_id else None,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_ms": self.elapsed_ms,
            "last_seq": self.next_seq(),
            "error": self.error,
            "live": True,
        }


class RunManager:
    """Owns every in-flight agent run in this process."""

    def __init__(self) -> None:
        self._runs: Dict[str, RunHandle] = {}
        self._session_active: Dict[str, str] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._shutting_down = False

    # ───────── lifecycle ─────────
    def bind_loop(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        self._loop = loop or asyncio.get_running_loop()
        self._shutting_down = False
        # Startup only runs before any run exists in this process, so anything
        # still registered belongs to a previous (dead) loop and is unusable.
        self._runs.clear()
        self._session_active.clear()
        logger.info("RunManager bound to event loop for run management")

    @property
    def loop(self) -> Optional[asyncio.AbstractEventLoop]:
        return self._loop

    @property
    def shutting_down(self) -> bool:
        return self._shutting_down

    # ───────── registry ─────────
    def get(self, run_id: uuid.UUID | str) -> Optional[RunHandle]:
        return self._runs.get(str(run_id))

    def active_run_id_for_session(self, session_id: uuid.UUID | str) -> Optional[str]:
        return self._session_active.get(str(session_id))

    def is_session_busy(self, session_id: uuid.UUID | str) -> bool:
        return str(session_id) in self._session_active

    def live_runs(self) -> List[RunHandle]:
        return [h for h in self._runs.values() if h.status not in TERMINAL_RUN_STATUSES]

    def active_count(self) -> int:
        return len(self.live_runs())

    def publish(self, run_id: uuid.UUID | str, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Appends an event to a run's stream, if that run is still registered."""
        handle = self.get(run_id)
        if handle is None:
            return None
        if handle.status in TERMINAL_RUN_STATUSES and event.get("type") not in TERMINAL_EVENT_TYPES:
            return None
        return handle.publish(event)

    def _publish_terminal(self, handle: RunHandle, event: Dict[str, Any]) -> None:
        """Publishes a closing frame exactly once per run."""
        if handle.terminal_published:
            return
        handle.terminal_published = True
        handle.publish(event)

    # ───────── starting runs ─────────
    async def start_run(
        self,
        *,
        session_uuid: uuid.UUID,
        agent_id: str,
        prompt: str = "",
        trigger_message_id: Optional[uuid.UUID] = None,
        parent_run_id: Optional[uuid.UUID] = None,
        origin: str = "user",
        workspace_id: Optional[uuid.UUID] = None,
        fold_pending_peers: bool = True,
        require_capacity: bool = True,
    ) -> RunHandle:
        """Registers a run, persists its trace rows and starts its task.

        Raises :class:`RunBusyError` / :class:`RunCapacityError` before touching
        the database so callers can surface a clean 409/429.
        """
        session_key = str(session_uuid)
        active = self._session_active.get(session_key)
        if active:
            raise RunBusyError(session_uuid, uuid.UUID(active) if active else None)

        limit = settings.MAX_CONCURRENT_RUNS
        if require_capacity and limit > 0 and self.active_count() >= limit:
            raise RunCapacityError(limit)

        final_prompt = prompt
        reply_context: Optional[Dict[str, Any]] = None
        consumed: List[Dict[str, Any]] = []

        if fold_pending_peers:
            from app.services.agent_mailbox_service import AgentMailboxService

            final_prompt, consumed = await AgentMailboxService.consume_pending(
                session_uuid, prompt
            )
            reply_context = _reply_context_from(consumed)

        handle = RunHandle(
            run_id=uuid.uuid4(),
            session_id=session_uuid,
            agent_id=agent_id,
            prompt=final_prompt,
            origin=origin,
            parent_run_id=parent_run_id,
            trigger_message_id=trigger_message_id,
            reply_context=reply_context,
        )

        await self._persist_run_start(handle, workspace_id)

        self._runs[str(handle.run_id)] = handle
        self._session_active[session_key] = str(handle.run_id)

        handle.publish(
            {
                "type": "start",
                "agent_id": agent_id,
                "session_id": session_key,
                "run_id": str(handle.run_id),
                "origin": origin,
            }
        )
        if consumed:
            handle.publish(
                {
                    "type": "peer_message",
                    "run_id": str(handle.run_id),
                    "from_agent": reply_context.get("sender_agent_id") if reply_context else None,
                    "message_count": len(consumed),
                }
            )

        handle.task = asyncio.create_task(self._execute(handle), name=f"agent-run-{handle.run_id}")
        logger.info(
            "Started run %s (agent=%s session=%s origin=%s parent=%s)",
            handle.run_id,
            agent_id,
            session_uuid,
            origin,
            parent_run_id,
        )
        return handle

    async def start_run_soon(self, **kwargs: Any) -> Optional[RunHandle]:
        """Best-effort run start used by background auto-dispatch."""
        try:
            return await self.start_run(**kwargs)
        except RunBusyError:
            logger.debug("Auto-dispatch skipped: session %s is busy", kwargs.get("session_uuid"))
        except RunCapacityError as exc:
            logger.warning("Auto-dispatch skipped: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Auto-dispatch failed: %s", exc, exc_info=True)
        return None

    async def _persist_run_start(
        self, handle: RunHandle, workspace_id: Optional[uuid.UUID]
    ) -> None:
        from db.connection import async_session_scope
        from db.repository import Repository

        async with async_session_scope() as db:
            instance = await Repository.create_agent_instance(
                db,
                agent_id=handle.agent_id,
                workspace_id=workspace_id,
                # schema.sql constrains agent_instances.status to
                # ('starting','idle','busy','draining','offline','error').
                status="busy",
                config_override={"run_id": str(handle.run_id), "origin": handle.origin},
            )
            handle.instance_id = instance.id
            await Repository.create_agent_run(
                db,
                agent_id=handle.agent_id,
                session_id=handle.session_id,
                trigger_message_id=handle.trigger_message_id,
                parent_run_id=handle.parent_run_id,
                status="running",
                instance_id=instance.id,
                origin=handle.origin,
                run_id=handle.run_id,
            )

    # ───────── execution ─────────
    async def _execute(self, handle: RunHandle) -> None:
        from app.services.chat_service import ChatService

        try:
            await ChatService.run_turn(handle, self)
            if handle.status == "running":
                handle.status = "completed"
        except asyncio.CancelledError:
            handle.status = "cancelled"
            handle.error = handle.error or "cancelled"
            self._publish_terminal(
                handle,
                {"type": "cancelled", "run_id": str(handle.run_id), "reason": handle.error},
            )
            # Persist from a detached task: the current task is being cancelled,
            # so awaiting here could be interrupted before the DB is updated.
            # ``cancel_run`` awaits this handle so callers observe the final state.
            handle.finalize_task = asyncio.ensure_future(self._finalize(handle, "cancelled"))
            return
        except Exception as exc:  # run_turn handles most errors itself
            logger.error("Run %s failed: %s", handle.run_id, exc, exc_info=True)
            handle.status = "failed"
            handle.error = str(exc)
            self.publish(
                handle.run_id,
                {"type": "error", "run_id": str(handle.run_id), "error": str(exc)},
            )
        finally:
            handle.finished_at = handle.finished_at or time.time()
            self._session_active.pop(str(handle.session_id), None)

        await self._finalize(handle, handle.status)

    async def _finalize(self, handle: RunHandle, status: str) -> None:
        """Writes the terminal DB state, delivers replies and drains the mailbox."""
        if handle.finished_at is None:
            handle.finished_at = time.time()
        # A cancelled run may still be finalized by a detached task; make the
        # registry state terminal either way so viewers never hang.
        if handle.status not in TERMINAL_RUN_STATUSES:
            handle.status = status
        self._session_active.pop(str(handle.session_id), None)
        self.publish(
            handle.run_id,
            {
                "type": "run_status",
                "run_id": str(handle.run_id),
                "status": handle.status,
            },
        )

        try:
            await self._persist_run_finish(handle)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to finalize run %s: %s", handle.run_id, exc, exc_info=True)

        if handle.status != "cancelled":
            await self._deliver_reply(handle)

        await self._drain_mailbox(handle.session_id)

    async def _persist_run_finish(self, handle: RunHandle) -> None:
        from db.connection import async_session_scope
        from db.repository import Repository

        async with async_session_scope() as db:
            await Repository.update_agent_run(
                db,
                handle.run_id,
                status=handle.status,
                error={"detail": handle.error} if handle.error else None,
                finished_at=handle.finished_at and _ts_to_datetime(handle.finished_at),
            )
            if handle.instance_id:
                await Repository.update_agent_instance(
                    db,
                    handle.instance_id,
                    # agent_instances.status has no "stopped": idle after a clean
                    # finish, error when the run failed or was cancelled.
                    status="idle" if handle.status == "completed" else "error",
                )

    # ───────── peer messaging ─────────
    async def send_peer_message(
        self,
        *,
        sender: Optional[RunHandle],
        to_session_id: uuid.UUID,
        content: str,
        expect_reply: bool = True,
        sender_agent_id: Optional[str] = None,
        sender_session_id: Optional[uuid.UUID] = None,
        reply_to_message_id: Optional[uuid.UUID] = None,
        root_message_id: Optional[uuid.UUID] = None,
        hop_count: Optional[int] = None,
        kind: str = "message",
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Queues (and, when the target is idle, immediately delivers) a peer message."""
        from app.services.agent_mailbox_service import AgentMailboxService

        effective_sender_session = sender_session_id or (sender.session_id if sender else None)
        effective_sender_run = sender.run_id if sender else None
        effective_sender_agent = sender_agent_id or (sender.agent_id if sender else None)

        if effective_sender_session and str(effective_sender_session) == str(to_session_id):
            return {"success": False, "error": "refused: cannot message the calling session"}

        hop = hop_count if hop_count is not None else 0
        if hop >= settings.AGENT_REPLY_HOP_LIMIT:
            await AgentMailboxService.record_system_note(
                to_session_id,
                f"Peer conversation reached the hop limit ({settings.AGENT_REPLY_HOP_LIMIT}); "
                f"message from {effective_sender_agent or 'an agent'} was dropped.",
                {"peer_expired": True},
            )
            return {
                "success": False,
                "error": f"hop_limit_reached ({settings.AGENT_REPLY_HOP_LIMIT})",
            }

        message_id = await AgentMailboxService.create_message(
            recipient_session_id=to_session_id,
            content=content,
            sender_run_id=effective_sender_run,
            sender_session_id=effective_sender_session,
            sender_agent_id=effective_sender_agent,
            reply_to_message_id=reply_to_message_id,
            root_message_id=root_message_id,
            hop_count=hop,
            kind=kind,
            expect_reply=expect_reply,
            payload=payload,
        )

        dispatched = None
        if not self.is_session_busy(to_session_id):
            dispatched = await self._dispatch_peer_run(to_session_id)
        else:
            logger.info(
                "Peer message %s queued: session %s is busy", message_id, to_session_id
            )

        return {
            "success": True,
            "message_id": str(message_id),
            "status": "delivered" if dispatched else "queued",
            "dispatched_run_id": str(dispatched.run_id) if dispatched else None,
        }

    async def _deliver_reply(self, handle: RunHandle) -> None:
        """Sends a peer run's final answer back to the session that asked."""
        ctx = handle.reply_context
        if not ctx or not ctx.get("expect_reply"):
            return
        if not handle.final_output:
            return

        hop = int(ctx.get("hop_count") or 0) + 1
        if hop >= settings.AGENT_REPLY_HOP_LIMIT:
            from app.services.agent_mailbox_service import AgentMailboxService

            await AgentMailboxService.expire(
                ctx.get("message_id"),
                f"hop limit ({settings.AGENT_REPLY_HOP_LIMIT}) reached",
            )
            return

        sender_session = ctx.get("sender_session_id")
        if not sender_session:
            return

        await self.send_peer_message(
            sender=handle,
            to_session_id=uuid.UUID(str(sender_session)),
            content=handle.final_output,
            expect_reply=False,
            sender_agent_id=handle.agent_id,
            sender_session_id=handle.session_id,
            reply_to_message_id=uuid.UUID(str(ctx["message_id"])),
            root_message_id=uuid.UUID(str(ctx["root_message_id"])) if ctx.get("root_message_id") else None,
            hop_count=hop,
            kind="reply",
        )

        from app.services.agent_mailbox_service import AgentMailboxService

        await AgentMailboxService.mark_replied(ctx.get("message_id"))

    async def _drain_mailbox(self, session_id: uuid.UUID) -> None:
        """Starts a follow-up run for messages that queued while this session ran."""
        if self._shutting_down:
            return
        if self.is_session_busy(session_id):
            return

        from app.services.agent_mailbox_service import AgentMailboxService

        if not await AgentMailboxService.has_pending(session_id):
            return

        logger.info("Draining peer mailbox for session %s", session_id)
        await self._dispatch_peer_run(session_id)

    async def _dispatch_peer_run(self, session_id: uuid.UUID) -> Optional[RunHandle]:
        from app.services.agent_mailbox_service import AgentMailboxService
        from db.connection import async_session_scope
        from db.repository import Repository

        agent_id = "root_agent"
        async with async_session_scope() as db:
            sess = await Repository.get_session(db, session_id)
            if sess and sess.primary_agent_id:
                agent_id = sess.primary_agent_id

        # A peer conversation continues the chain, so the run links back to the
        # session's most recent run rather than to the message sender's run.
        async with async_session_scope() as db:
            recent = await Repository.list_agent_runs(db, session_id=session_id, limit=1)
        parent_run_id = recent[0].id if recent else None

        return await self.start_run_soon(
            session_uuid=session_id,
            agent_id=agent_id,
            prompt="",
            parent_run_id=parent_run_id,
            origin="peer",
        )

    # ───────── streaming ─────────
    async def subscribe(
        self,
        run_id: uuid.UUID | str,
        cursor: int = 0,
        emit_attach: bool = True,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Replays buffered events from ``cursor`` and then live-tails the run."""
        handle = self.get(run_id)
        if handle is None:
            return

        _, effective, truncated = handle.events_from(cursor)
        if emit_attach:
            yield {
                "type": "attach",
                "run_id": str(handle.run_id),
                "status": handle.status,
                "cursor": effective,
                "truncated": truncated,
            }

        index = max(0, effective - handle.first_seq)
        heartbeat = settings.RUN_HEARTBEAT_SECONDS

        while True:
            while index < len(handle.events):
                event = handle.events[index]
                index += 1
                yield event
                if event.get("type") in TERMINAL_EVENT_TYPES:
                    return

            if handle.status in TERMINAL_RUN_STATUSES:
                # Reached the end of the buffer with a terminal status: the
                # terminal frame was trimmed or already consumed by another
                # viewer, so close the stream rather than hang.
                return

            seen = handle.version
            waiter = handle._waiter  # noqa: SLF001 - same module owns the field
            if handle.version != seen:  # pragma: no cover - loop re-check
                continue
            try:
                await asyncio.wait_for(waiter.wait(), timeout=heartbeat if heartbeat > 0 else None)
            except asyncio.TimeoutError:
                yield {"type": "heartbeat", "run_id": str(handle.run_id), "status": handle.status}

    # ───────── cancellation ─────────
    async def cancel_run(
        self,
        run_id: uuid.UUID | str,
        *,
        cascade: bool = True,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cancels a run and (by default) everything it spawned."""
        handle = self.get(run_id)
        cancelled: List[str] = []

        if cascade:
            for child in await self._unfinished_descendants(uuid.UUID(str(run_id))):
                child_handle = self.get(child)
                if child_handle and await self._cancel_handle(child_handle, reason):
                    cancelled.append(str(child))

        if handle is None:
            # Not live in this process: make sure the row is not left running.
            await self._mark_db_cancelled(uuid.UUID(str(run_id)), reason)
            return {
                "success": False,
                "run_id": str(run_id),
                "status": "not_found",
                "cancelled_children": cancelled,
            }

        if await self._cancel_handle(handle, reason):
            cancelled.insert(0, str(handle.run_id))
        return {
            # "success" answers "is nothing still running?" so an already-finished
            # run reports success (stop was a no-op) instead of a confusing
            # failure, while "cancelled" says whether this call stopped it.
            "success": handle.status in TERMINAL_RUN_STATUSES,
            "cancelled": handle.status == "cancelled",
            "run_id": str(handle.run_id),
            "status": handle.status,
            "cancelled_children": cancelled[1:],
        }

    async def _cancel_handle(self, handle: RunHandle, reason: Optional[str]) -> bool:
        if handle.status in TERMINAL_RUN_STATUSES and handle.task is None:
            return False

        if handle.cancel_requested:
            return False
        handle.cancel_requested = True
        handle.error = reason or "cancelled by user"

        # Cancelling the task propagates into ``runner.run_async`` at its next
        # await point. Some tools (subprocess, Playwright) may swallow it, so a
        # timeout still marks the run cancelled rather than hanging forever.
        if handle.task and not handle.task.done():
            handle.task.cancel()
            timeout = settings.RUN_CANCEL_TIMEOUT_SECONDS
            try:
                await asyncio.wait_for(asyncio.shield(handle.task), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(
                    "Run %s did not stop within %.1fs; marking cancelled anyway",
                    handle.run_id,
                    timeout,
                )
            except BaseException:  # noqa: B014 - the task's own outcome is irrelevant here
                pass

            # The run task finalizes itself from detached tasks (it cannot await
            # mid-cancellation); wait for those writes so callers observe a
            # settled row and a persisted partial message.
            await self._await_detached(handle)

        if handle.status not in TERMINAL_RUN_STATUSES:
            handle.status = "cancelled"
        handle.finished_at = handle.finished_at or time.time()
        self._session_active.pop(str(handle.session_id), None)

        # Release any `ask_user` question this run is blocked on. Without this the
        # registry entry would outlive its run and the UI would keep showing a
        # question card for a run the user just stopped.
        try:
            from app.services.hitl_service import get_hitl_service

            get_hitl_service().fail_all(str(handle.session_id), reason="cancelled")
        except Exception:  # pragma: no cover - cancellation must never fail here
            logger.debug("Could not close HITL questions for run %s", handle.run_id)

        self._publish_terminal(
            handle,
            {"type": "cancelled", "run_id": str(handle.run_id), "reason": handle.error},
        )
        await self._persist_run_finish(handle)
        logger.info("Cancelled run %s (%s)", handle.run_id, handle.error)
        return True

    async def _await_detached(self, handle: RunHandle) -> None:
        """Waits for the persistence tasks a cancelled run scheduled for itself."""
        tasks = [t for t in (handle.persist_task, handle.finalize_task) if t is not None]
        if not tasks:
            return
        gathered = asyncio.gather(*tasks, return_exceptions=True)
        try:
            await asyncio.wait_for(
                asyncio.shield(gathered), timeout=settings.RUN_CANCEL_TIMEOUT_SECONDS
            )
        except BaseException:  # noqa: B014 - best effort; the row is written below anyway
            logger.debug("Detached finalizers for run %s did not finish in time", handle.run_id)

    async def cancel_session(
        self, session_id: uuid.UUID | str, reason: Optional[str] = None
    ) -> Dict[str, Any]:
        active = self._session_active.get(str(session_id))
        if not active:
            return {"success": False, "session_id": str(session_id), "status": "idle"}
        return await self.cancel_run(active, reason=reason)

    async def _unfinished_descendants(self, root_run_id: uuid.UUID) -> List[str]:
        from db.connection import async_session_scope
        from db.repository import Repository

        async with async_session_scope() as db:
            rows = await Repository.list_unfinished_descendant_runs(db, root_run_id)
        return [str(r.id) for r in rows]

    async def _mark_db_cancelled(self, run_id: uuid.UUID, reason: Optional[str]) -> None:
        from db.connection import async_session_scope
        from db.repository import Repository

        async with async_session_scope() as db:
            run = await Repository.get_agent_run(db, run_id)
            if run and run.status not in TERMINAL_RUN_STATUSES:
                await Repository.update_agent_run(
                    db,
                    run_id,
                    status="cancelled",
                    error={"detail": reason or "cancelled"},
                )

    # ───────── shutdown ─────────
    async def shutdown(self) -> None:
        """Cancels every live run; called from the app lifespan on exit."""
        self._shutting_down = True
        handles = self.live_runs()
        for handle in handles:
            handle.cancel_requested = True
            handle.error = "server shutdown"
            if handle.task and not handle.task.done():
                handle.task.cancel()
        if handles:
            pending = [h.task for h in handles if h.task]
            if pending:
                # Bounded: a tool that swallows cancellation must not hang exit.
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*pending, return_exceptions=True),
                        timeout=settings.RUN_CANCEL_TIMEOUT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "%d run task(s) did not stop within %.1fs during shutdown",
                        len(pending),
                        settings.RUN_CANCEL_TIMEOUT_SECONDS,
                    )
        for handle in handles:
            if handle.status not in TERMINAL_RUN_STATUSES:
                # "failed" (not "interrupted") keeps the row inside the status
                # vocabulary enforced by schema.sql's CHECK constraint.
                handle.status = "failed"
            self._session_active.pop(str(handle.session_id), None)
            try:
                await self._persist_run_finish(handle)
            except Exception:  # pragma: no cover - best effort on shutdown
                logger.warning("Could not persist shutdown state for run %s", handle.run_id)


def _reply_context_from(consumed: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Picks the message a peer run should answer, if any asked for a reply."""
    for item in consumed:
        if item.get("expect_reply"):
            return {
                "message_id": item.get("id"),
                "sender_session_id": item.get("sender_session_id"),
                "sender_run_id": item.get("sender_run_id"),
                "sender_agent_id": item.get("sender_agent_id"),
                "root_message_id": item.get("root_message_id") or item.get("id"),
                "hop_count": item.get("hop_count") or 0,
                "expect_reply": True,
            }
    return None


def _ts_to_datetime(ts: float):
    from datetime import datetime, timezone

    return datetime.fromtimestamp(ts, tz=timezone.utc)


_run_manager: Optional[RunManager] = None


def get_run_manager() -> RunManager:
    global _run_manager
    if _run_manager is None:
        _run_manager = RunManager()
    return _run_manager
