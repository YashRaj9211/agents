"""
Run manager suite: parallel runs, per-session exclusivity, capacity, cancellation,
event replay and startup reconciliation.
"""
from __future__ import annotations

import asyncio
import uuid

from orchestration_helpers import (
    ScriptedRunner,
    StallingRunner,
    done_event,
    install_runner_factory,
    shutdown_runs,
    uninstall_runner_factory,
    wait_for,
)

from app.core.config import settings
from app.services.run_manager import (
    RunBusyError,
    RunCapacityError,
    get_run_manager,
)
from db.connection import async_session_scope, init_db
from db.repository import Repository


async def _make_session(title: str) -> uuid.UUID:
    async with async_session_scope() as db:
        user, workspace = await Repository.get_or_create_default_identity(db)
        sess = await Repository.create_session(
            db,
            workspace_id=workspace.id,
            user_id=user.id,
            title=title,
            primary_agent_id="root_agent",
        )
        return sess.id


async def _cleanup(*session_ids: uuid.UUID) -> None:
    async with async_session_scope() as db:
        for sid in session_ids:
            await Repository.delete_session(db, sid)


async def test_parallel_runs_replay_and_persistence() -> None:
    manager = get_run_manager()
    manager.bind_loop()
    runner = ScriptedRunner(lambda sid, msg: [done_event(f"ok-{str(sid)[:4]}")], delay=0.15)
    install_runner_factory(runner)

    s1 = await _make_session("run-mgr parallel 1")
    s2 = await _make_session("run-mgr parallel 2")
    try:
        h1 = await manager.start_run(session_uuid=s1, agent_id="root_agent", prompt="one")
        h2 = await manager.start_run(session_uuid=s2, agent_id="root_agent", prompt="two")

        assert manager.active_count() == 2, "both runs should execute at the same time"
        assert h1.status == "running" and h2.status == "running"
        assert manager.is_session_busy(s1) and manager.is_session_busy(s2)

        await asyncio.gather(h1.task, h2.task)
        assert h1.status == "completed", h1.status
        assert h2.status == "completed", h2.status
        assert manager.active_count() == 0
        assert not manager.is_session_busy(s1)

        async with async_session_scope() as db:
            messages = await Repository.list_session_messages(db, s1)
            run = await Repository.get_agent_run(db, h1.run_id)
        assert [m.role for m in messages] == ["assistant"], [m.role for m in messages]
        assert "ok-" in messages[0].content
        assert run is not None and run.status == "completed", run.status

        # Replay after completion must still deliver the whole story.
        events = [
            e async for e in manager.subscribe(h1.run_id, cursor=0, emit_attach=False)
        ]
        types = [e["type"] for e in events]
        assert types[0] == "start", types
        assert types[-1] == "done", types
        assert events[-1]["final_output"].startswith("ok-")

        # Attaching mid-flight (or after) announces itself first.
        attached = [
            e async for e in manager.subscribe(h1.run_id, cursor=0, emit_attach=True)
        ]
        assert attached[0]["type"] == "attach", attached[0]
        assert attached[0]["status"] == "completed"

        # Two viewers on the same run both get the replay.
        viewers = await asyncio.gather(
            _collect(manager, h2.run_id),
            _collect(manager, h2.run_id),
        )
        assert all(types[-1] == "done" for types in viewers), viewers
    finally:
        uninstall_runner_factory()
        await _cleanup(s1, s2)


async def _collect(manager, run_id) -> list:
    return [e["type"] async for e in manager.subscribe(run_id, cursor=0, emit_attach=False)]


async def test_one_active_run_per_session() -> None:
    manager = get_run_manager()
    manager.bind_loop()
    install_runner_factory(StallingRunner())

    s1 = await _make_session("run-mgr busy")
    try:
        handle = await manager.start_run(session_uuid=s1, agent_id="root_agent", prompt="hold")
        await asyncio.sleep(0.05)

        try:
            await manager.start_run(session_uuid=s1, agent_id="root_agent", prompt="second")
            raise AssertionError("a second run on the same session must be refused")
        except RunBusyError as exc:
            assert exc.session_id == s1
            assert str(exc.active_run_id) == str(handle.run_id)

        # A different session is fine while the first is busy.
        s2 = await _make_session("run-mgr busy other")
        try:
            other = await manager.start_run(session_uuid=s2, agent_id="root_agent", prompt="ok")
            assert other.status == "running"
            await manager.cancel_run(other.run_id)
        finally:
            await _cleanup(s2)
    finally:
        await manager.cancel_run(handle.run_id)
        uninstall_runner_factory()
        await _cleanup(s1)


async def test_global_capacity_cap() -> None:
    manager = get_run_manager()
    manager.bind_loop()
    install_runner_factory(StallingRunner())

    original_limit = settings.MAX_CONCURRENT_RUNS
    settings.MAX_CONCURRENT_RUNS = 1
    s1 = await _make_session("run-mgr cap 1")
    s2 = await _make_session("run-mgr cap 2")
    try:
        handle = await manager.start_run(session_uuid=s1, agent_id="root_agent", prompt="first")
        await asyncio.sleep(0.05)
        try:
            await manager.start_run(session_uuid=s2, agent_id="root_agent", prompt="second")
            raise AssertionError("capacity limit must reject the second run")
        except RunCapacityError as exc:
            assert exc.limit == 1
    finally:
        settings.MAX_CONCURRENT_RUNS = original_limit
        await manager.cancel_run(handle.run_id)
        uninstall_runner_factory()
        await _cleanup(s1, s2)


async def test_cancellation_finalizes_run_and_message() -> None:
    manager = get_run_manager()
    manager.bind_loop()
    install_runner_factory(StallingRunner())

    session = await _make_session("run-mgr cancel")
    try:
        handle = await manager.start_run(session_uuid=session, agent_id="root_agent", prompt="long")

        seen: list = []

        async def consume():
            async for event in manager.subscribe(handle.run_id, cursor=0, emit_attach=False):
                seen.append(event["type"])

        viewer = asyncio.create_task(consume())
        await asyncio.sleep(0.1)

        result = await manager.cancel_run(handle.run_id, reason="test stop")
        assert result["success"] is True, result
        assert handle.status == "cancelled", handle.status

        await asyncio.wait_for(viewer, timeout=5)
        assert "cancelled" in seen, seen
        assert not manager.is_session_busy(session)

        async with async_session_scope() as db:
            run = await Repository.get_agent_run(db, handle.run_id)
            messages = await Repository.list_session_messages(db, session)
        assert run.status == "cancelled", run.status
        assert run.finished_at is not None
        assert messages and messages[-1].metadata_.get("cancelled") is True, messages
    finally:
        uninstall_runner_factory()
        await _cleanup(session)


async def test_cascade_cancel_stops_spawned_runs() -> None:
    manager = get_run_manager()
    manager.bind_loop()
    install_runner_factory(StallingRunner())

    parent_session = await _make_session("run-mgr cascade parent")
    child_session = await _make_session("run-mgr cascade child")
    try:
        parent = await manager.start_run(
            session_uuid=parent_session, agent_id="root_agent", prompt="parent"
        )
        child = await manager.start_run(
            session_uuid=child_session,
            agent_id="root_agent",
            prompt="child",
            parent_run_id=parent.run_id,
            origin="spawn",
        )
        await asyncio.sleep(0.05)

        result = await manager.cancel_run(parent.run_id, cascade=True)
        assert result["success"] is True
        assert str(child.run_id) in result["cancelled_children"], result
        assert child.status == "cancelled", child.status
    finally:
        uninstall_runner_factory()
        await _cleanup(parent_session, child_session)


async def test_mailbox_drain_and_orphan_reconciliation() -> None:
    manager = get_run_manager()
    manager.bind_loop()
    # A per-run delay keeps the session busy long enough to queue a peer message.
    runner = ScriptedRunner(lambda sid, msg: [done_event("peer answered")], delay=0.4)
    install_runner_factory(runner)

    session = await _make_session("run-mgr mailbox")
    try:
        from app.services.agent_mailbox_service import AgentMailboxService

        await manager.start_run(session_uuid=session, agent_id="root_agent", prompt="first")
        await asyncio.sleep(0.05)
        assert manager.is_session_busy(session), "first run should still be executing"

        # Queued while busy: nothing may start until the first run releases the session.
        message_id = await AgentMailboxService.create_message(
            recipient_session_id=session, content="queued peer ping", expect_reply=False
        )
        assert await AgentMailboxService.has_pending(session) is True

        async def delivered() -> bool:
            async with async_session_scope() as db:
                stored = await Repository.get_agent_message(db, message_id)
            return stored is not None and stored.status != "queued"

        assert await wait_for(delivered, timeout=15), (
            "queued peer message should be drained once the session frees up"
        )
        assert await wait_for(
            lambda: not manager.is_session_busy(session), timeout=15
        ), "follow-up run should finish"

        async with async_session_scope() as db:
            runs = await Repository.list_agent_runs(db, session_id=session, limit=20)
            messages = await Repository.list_session_messages(db, session)
        assert len(runs) >= 2, [r.agent_id for r in runs]
        assert any("peer answered" in m.content for m in messages), [m.content for m in messages]

        # Orphaned running rows from a dead process are closed out at startup.
        # (schema.sql has no "interrupted" status, so this is recorded as a
        # failure carrying the reason.)
        async with async_session_scope() as db:
            user, workspace = await Repository.get_or_create_default_identity(db)
            orphan = await Repository.create_agent_run(
                db, agent_id="root_agent", session_id=session, status="running"
            )
            orphan_id = orphan.id
            count = await Repository.reconcile_interrupted_runs(db)
            refreshed = await Repository.get_agent_run(db, orphan_id)
        assert count >= 1
        assert refreshed.status == "failed", refreshed.status
        assert "interrupted" in (refreshed.error or {}).get("detail", ""), refreshed.error
    finally:
        uninstall_runner_factory()
        await _cleanup(session)


async def test_event_buffer_trims_and_flags_truncation() -> None:
    manager = get_run_manager()
    manager.bind_loop()
    install_runner_factory(ScriptedRunner(lambda sid, msg: [done_event("tiny")]))

    original = settings.RUN_EVENT_BUFFER_SIZE
    settings.RUN_EVENT_BUFFER_SIZE = 2
    session = await _make_session("run-mgr buffer")
    try:
        handle = await manager.start_run(session_uuid=session, agent_id="root_agent", prompt="p")
        await asyncio.wait_for(handle.task, timeout=10)

        # A late viewer is told the front of the buffer is gone.
        attached = [
            e async for e in manager.subscribe(handle.run_id, cursor=0, emit_attach=True)
        ]
        assert attached[0]["type"] == "attach", attached[0]
        assert attached[0]["truncated"] is True, attached[0]
        assert attached[0]["cursor"] == handle.first_seq, attached[0]
        assert handle.truncated is True
        assert attached[-1]["type"] == "done", attached[-1]
        # Bounded memory: never more events retained than the configured cap.
        assert len(handle.events) <= 2, len(handle.events)
    finally:
        settings.RUN_EVENT_BUFFER_SIZE = original
        uninstall_runner_factory()
        await _cleanup(session)


async def main() -> None:
    await init_db()
    tests = [
        test_parallel_runs_replay_and_persistence,
        test_one_active_run_per_session,
        test_global_capacity_cap,
        test_cancellation_finalizes_run_and_message,
        test_cascade_cancel_stops_spawned_runs,
        test_mailbox_drain_and_orphan_reconciliation,
        test_event_buffer_trims_and_flags_truncation,
    ]
    for test in tests:
        await test()
        print(f"PASS {test.__name__}")
    await shutdown_runs()
    print("\nRun manager suite passed.")


if __name__ == "__main__":
    asyncio.run(main())
