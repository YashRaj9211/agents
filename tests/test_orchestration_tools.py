"""
Orchestration tool suite: one agent fanning work out to several agents at once.

These tests drive the tools directly with a fake ADK tool context, because that
is exactly how ADK invokes them (``async def`` tools run on the server loop).
"""
from __future__ import annotations

import asyncio
import uuid

from orchestration_helpers import (
    ScriptedRunner,
    StallingRunner,
    done_event,
    fake_tool_context,
    install_runner_factory,
    shutdown_runs,
    uninstall_runner_factory,
    wait_for,
)

from app.services.chat_service import get_agents
from app.services.run_manager import get_run_manager
from db.connection import async_session_scope, init_db
from db.repository import Repository
from tools.orchestration_tools import (
    await_agents,
    cancel_agent_run,
    list_active_runs,
    spawn_agents,
)
from tools.orchestration_tools.orchestration_tools import MAX_SPAWN_PER_CALL


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


def _known_agent_id() -> str:
    agents = get_agents()
    return "root_agent" if "root_agent" in agents else next(iter(agents))


async def test_spawn_agents_runs_in_parallel_and_reports_parent() -> None:
    manager = get_run_manager()
    manager.bind_loop()

    parent_session = await _make_session("spawn parent")
    runner = ScriptedRunner(lambda sid, msg: [done_event(f"done-{str(sid)[:4]}")], delay=0.2)
    install_runner_factory(runner)

    try:
        parent = await manager.start_run(
            session_uuid=parent_session, agent_id=_known_agent_id(), prompt="coordinate"
        )
        await asyncio.sleep(0.05)

        result = await spawn_agents(
            tasks=[
                {"agent_id": _known_agent_id(), "prompt": "task one", "session_title": "spawn one"},
                {"agent_id": _known_agent_id(), "prompt": "task two", "session_title": "spawn two"},
            ],
            tool_context=fake_tool_context(parent_session),
        )

        assert result["success"] is True, result
        assert len(result["spawned"]) == 2, result
        assert result["failed"] == [], result["failed"]

        spawned_ids = [item["run_id"] for item in result["spawned"]]
        child_sessions = [item["session_id"] for item in result["spawned"]]
        assert len(set(child_sessions)) == 2, "each task gets its own session"

        # The children are live at the same time (that is the point of fan-out)
        # and each is linked to the parent run.
        assert manager.active_count() >= 2, manager.active_count()
        for item in result["spawned"]:
            assert manager.is_session_busy(item["session_id"]), item

        async with async_session_scope() as db:
            for run_id in spawned_ids:
                run = await Repository.get_agent_run(db, run_id)
                assert run.parent_run_id == parent.run_id, (run.id, run.parent_run_id)
                assert run.usage.get("origin") == "spawn", run.usage
                assert run.status in ("running", "completed"), run.status

        # The user-visible stream was told about the fan-out.
        events = [
            e async for e in manager.subscribe(parent.run_id, cursor=0, emit_attach=False)
        ]
        spawn_events = [e for e in events if e["type"] == "agent_spawned"]
        assert spawn_events, [e["type"] for e in events]
        assert len(spawn_events[0]["spawned"]) == 2

        # Cancelling the parent cascades to the children it spawned. The parent
        # may have finished already, so assert on the children, not on it.
        handled = await cancel_agent_run(parent.run_id, cascade=True)
        assert handled["success"] is True, handled
        assert set(handled["cancelled_children"]) >= set(spawned_ids), handled
        for sid in child_sessions:
            assert not manager.is_session_busy(sid), sid
    finally:
        await manager.cancel_run(manager.active_run_id_for_session(parent_session) or parent_session, cascade=False)
        uninstall_runner_factory()
        await _cleanup(parent_session)


async def test_spawn_agents_validates_tasks() -> None:
    manager = get_run_manager()
    manager.bind_loop()

    session = await _make_session("spawn validation")
    install_runner_factory(ScriptedRunner(lambda sid, msg: [done_event("ok")]))
    try:
        empty_prompt = await spawn_agents(
            tasks=[{"agent_id": _known_agent_id(), "prompt": "   "}],
            tool_context=fake_tool_context(session),
        )
        assert empty_prompt["success"] is False, empty_prompt
        assert empty_prompt["failed"][0]["error"] == "empty prompt", empty_prompt

        unknown_agent = await spawn_agents(
            tasks=[{"agent_id": "not_a_real_agent", "prompt": "hello"}],
            tool_context=fake_tool_context(session),
        )
        assert unknown_agent["success"] is False, unknown_agent
        assert unknown_agent["failed"][0]["error"] == "unknown agent id", unknown_agent

        too_many = await spawn_agents(
            tasks=[{"agent_id": _known_agent_id(), "prompt": f"t{i}"} for i in range(MAX_SPAWN_PER_CALL + 1)],
            tool_context=fake_tool_context(session),
        )
        assert too_many["success"] is False, too_many
        assert "too many tasks" in too_many["error"], too_many

        not_a_list = await spawn_agents(tasks="nope", tool_context=fake_tool_context(session))
        assert not_a_list["success"] is False, not_a_list
    finally:
        uninstall_runner_factory()
        await _cleanup(session)


async def test_await_agents_collects_outputs_and_times_out() -> None:
    manager = get_run_manager()
    manager.bind_loop()

    session = await _make_session("await agents")
    install_runner_factory(ScriptedRunner(lambda sid, msg: [done_event("collected answer")], delay=0.1))
    spawned_sessions = []
    try:
        result = await spawn_agents(
            tasks=[
                {"agent_id": _known_agent_id(), "prompt": "one"},
                {"agent_id": _known_agent_id(), "prompt": "two"},
            ],
            tool_context=fake_tool_context(session),
        )
        run_ids = [item["run_id"] for item in result["spawned"]]
        spawned_sessions = [item["session_id"] for item in result["spawned"]]

        collected = await await_agents(run_ids=run_ids, timeout_seconds=30)
        assert collected["status"] == "completed", collected
        assert collected["pending"] == [], collected
        for item in collected["results"]:
            assert item["status"] == "completed", item
            assert item["output"] == "collected answer", item

        # No results for an empty or malformed request.
        assert (await await_agents(run_ids=[]))["success"] is False
        unknown = await await_agents(run_ids=["11111111-1111-1111-1111-111111111111"], timeout_seconds=5)
        assert unknown["results"][0]["status"] == "unknown", unknown
    finally:
        uninstall_runner_factory()
        await _cleanup(session, *[uuid.UUID(s) for s in spawned_sessions])


async def test_await_agents_times_out_without_cancelling() -> None:
    manager = get_run_manager()
    manager.bind_loop()

    session = await _make_session("await timeout")
    install_runner_factory(StallingRunner())
    spawned: list = []
    spawned_runs: list = []
    try:
        result = await spawn_agents(
            tasks=[{"agent_id": _known_agent_id(), "prompt": "never finishes"}],
            tool_context=fake_tool_context(session),
        )
        spawned = [item["session_id"] for item in result["spawned"]]
        spawned_runs = [item["run_id"] for item in result["spawned"]]

        timed_out = await await_agents(run_ids=spawned_runs, timeout_seconds=1)
        assert timed_out["status"] == "timeout", timed_out
        assert timed_out["pending"], timed_out
        assert timed_out["success"] is False
        # Timing out must not stop the work it was waiting on.
        still_live = {r["run_id"] for r in (await list_active_runs())["runs"]}
        assert set(spawned_runs) <= still_live, (spawned_runs, still_live)
    finally:
        for run_id in spawned_runs:
            await cancel_agent_run(run_id)
        uninstall_runner_factory()
        await _cleanup(session, *[uuid.UUID(s) for s in spawned])


async def test_list_active_runs_reports_live_state() -> None:
    manager = get_run_manager()
    manager.bind_loop()

    session = await _make_session("active runs listing")
    install_runner_factory(StallingRunner())
    try:
        handle = await manager.start_run(
            session_uuid=session, agent_id=_known_agent_id(), prompt="hold"
        )
        await asyncio.sleep(0.05)

        listing = await list_active_runs()
        assert listing["active_count"] >= 1, listing
        entry = next(r for r in listing["runs"] if r["run_id"] == str(handle.run_id))
        assert entry["session_id"] == str(session)
        assert entry["origin"] == "user"
        assert entry["live"] is True
        assert {"run_id", "agent_id", "status", "elapsed_ms"} <= set(entry), entry
    finally:
        await manager.cancel_run(handle.run_id)
        uninstall_runner_factory()
        await _cleanup(session)


async def main() -> None:
    await init_db()
    tests = [
        test_spawn_agents_runs_in_parallel_and_reports_parent,
        test_spawn_agents_validates_tasks,
        test_await_agents_collects_outputs_and_times_out,
        test_await_agents_times_out_without_cancelling,
        test_list_active_runs_reports_live_state,
    ]
    for test in tests:
        await test()
        print(f"PASS {test.__name__}")
    await shutdown_runs()
    print("\nOrchestration tools suite passed.")


if __name__ == "__main__":
    asyncio.run(main())
