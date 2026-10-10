"""
Peer messaging suite: agents in different sessions talking to each other.

Covers the delivery rules of the mailbox service: immediate dispatch to an idle
session, queue-and-drain for a busy one, automatic replies back to the asker, the
hop limit, and the ``send_message_to_agent`` tool surface.
"""
from __future__ import annotations

import asyncio
import uuid

from orchestration_helpers import (
    ScriptedRunner,
    done_event,
    fake_tool_context,
    install_runner_factory,
    shutdown_runs,
    uninstall_runner_factory,
    wait_for,
)

from app.core.config import settings
from app.services.agent_mailbox_service import AgentMailboxService
from app.services.run_manager import get_run_manager
from db.connection import async_session_scope, init_db
from db.repository import Repository
from tools.orchestration_tools import list_agent_sessions, send_message_to_agent


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


async def _message_status(message_id) -> str:
    async with async_session_scope() as db:
        stored = await Repository.get_agent_message(db, message_id)
    return stored.status if stored else "missing"


async def _status_is(message_id, wanted: str) -> bool:
    """Async predicate helper: ``wait_for`` must receive a coroutine, not a bool."""
    return await _message_status(message_id) == wanted


async def _assistant_texts(session_id) -> list:
    async with async_session_scope() as db:
        messages = await Repository.list_session_messages(db, session_id)
    return [m.content for m in messages if m.role == "assistant"]


async def _peer_messages(session_id) -> list:
    async with async_session_scope() as db:
        messages = await Repository.list_session_messages(db, session_id)
    return [m for m in messages if (m.metadata_ or {}).get("peer")]


def _session_script(replies: dict):
    """Replies depend on the conversation, not the agent, in these tests."""

    def script(adk_session_id, message):
        conversation = str(adk_session_id).split("::")[0]
        yield done_event(replies.get(conversation, "unknown-session"))

    return script


async def test_peer_round_trip_and_automatic_reply() -> None:
    manager = get_run_manager()
    manager.bind_loop()

    a = await _make_session("peer A")
    b = await _make_session("peer B")
    replies = {str(a): "ack-from-A", str(b): "answer-from-B"}
    install_runner_factory(ScriptedRunner(_session_script(replies)))

    try:
        # An idle target starts working immediately.
        result = await manager.send_peer_message(
            sender=None,
            to_session_id=b,
            content="peer ping",
            expect_reply=True,
            sender_agent_id="root_agent",
            sender_session_id=a,
        )
        assert result["success"] is True, result
        assert result["status"] == "delivered", result
        message_id = result["message_id"]

        # The receiving session sees the peer message folded in as a user turn.
        assert await wait_for(
            lambda: _status_is(message_id, "replied"), timeout=15
        ), f"message ended as {await _message_status(message_id)}"

        # The answer came back to the asking session automatically.
        assert await wait_for(
            lambda: not manager.is_session_busy(a) and not manager.is_session_busy(b), timeout=15
        ), "peer conversation did not settle"

        assert "answer-from-B" in await _assistant_texts(b), await _assistant_texts(b)
        assert "ack-from-A" in await _assistant_texts(a), await _assistant_texts(a)

        peer_rows = await _peer_messages(a)
        assert peer_rows, "the reply should appear in the asking session as a peer message"
        assert peer_rows[-1].content == "answer-from-B", peer_rows[-1].content
        assert peer_rows[-1].metadata_.get("from_agent") == "root_agent"

        # Exactly two runs' worth of work: B answered, A absorbed the answer.
        async with async_session_scope() as db:
            runs_a = await Repository.list_agent_runs(db, session_id=a, limit=10)
            runs_b = await Repository.list_agent_runs(db, session_id=b, limit=10)
        assert len(runs_b) >= 1 and runs_b[0].agent_id == "root_agent"
        assert all(r.usage.get("origin") in ("peer", "user") for r in runs_a + runs_b), [
            (r.agent_id, r.usage) for r in runs_a + runs_b
        ]
    finally:
        uninstall_runner_factory()
        await _cleanup(a, b)


async def test_busy_target_queues_then_drains() -> None:
    manager = get_run_manager()
    manager.bind_loop()

    a = await _make_session("peer busy A")
    b = await _make_session("peer busy B")
    runner = ScriptedRunner(_session_script({str(a): "a-done", str(b): "b-done"}), delay=0.4)
    install_runner_factory(runner)

    try:
        await manager.start_run(session_uuid=b, agent_id="root_agent", prompt="occupying work")
        await asyncio.sleep(0.05)
        assert manager.is_session_busy(b)

        result = await manager.send_peer_message(
            sender=None,
            to_session_id=b,
            content="queued ping",
            expect_reply=False,
            sender_session_id=a,
        )
        assert result["success"] is True
        assert result["status"] == "queued", result
        assert result["dispatched_run_id"] is None, result
        message_id = result["message_id"]

        # Once the occupancy run finishes, the queued message is drained.
        assert await wait_for(
            lambda: _status_is(message_id, "delivered"), timeout=15
        ), "queued peer message was never drained"
        assert await wait_for(
            lambda: not manager.is_session_busy(b), timeout=15
        ), "drained run did not finish"

        async with async_session_scope() as db:
            runs = await Repository.list_agent_runs(db, session_id=b, limit=10)
        assert len(runs) >= 2, [str(r.id) for r in runs]
        assert any(r.usage.get("origin") == "peer" for r in runs), [r.usage for r in runs]
        assert "b-done" in await _assistant_texts(b), await _assistant_texts(b)
    finally:
        uninstall_runner_factory()
        await _cleanup(a, b)


async def test_hop_limit_stops_the_conversation() -> None:
    manager = get_run_manager()
    manager.bind_loop()

    a = await _make_session("peer hop A")
    b = await _make_session("peer hop B")
    install_runner_factory(ScriptedRunner(_session_script({str(b): "should not run"})))

    original = settings.AGENT_REPLY_HOP_LIMIT
    settings.AGENT_REPLY_HOP_LIMIT = 1
    try:
        result = await manager.send_peer_message(
            sender=None,
            to_session_id=b,
            content="one hop too far",
            expect_reply=True,
            sender_session_id=a,
            hop_count=1,
        )
        assert result["success"] is False, result
        assert "hop_limit" in result["error"], result
        assert not manager.is_session_busy(b), "hop-limited message must not start a run"

        async with async_session_scope() as db:
            notes = await Repository.list_session_messages(db, b)
        assert any(m.role == "system" and "hop limit" in m.content for m in notes), [
            m.content for m in notes
        ]
    finally:
        settings.AGENT_REPLY_HOP_LIMIT = original
        uninstall_runner_factory()
        await _cleanup(a, b)


async def test_messaging_your_own_session_is_refused() -> None:
    manager = get_run_manager()
    manager.bind_loop()

    a = await _make_session("peer self A")
    install_runner_factory(ScriptedRunner(_session_script({str(a): "self"})))
    try:
        result = await manager.send_peer_message(
            sender=None,
            to_session_id=a,
            content="hello me",
            sender_session_id=a,
        )
        assert result["success"] is False, result
        assert "refused" in result["error"], result

        tool_result = await send_message_to_agent(
            to_session_id=str(a), content="hello me", tool_context=fake_tool_context(a)
        )
        assert tool_result["success"] is False, tool_result
    finally:
        uninstall_runner_factory()
        await _cleanup(a)


async def test_send_message_tool_resolution_and_validation() -> None:
    manager = get_run_manager()
    manager.bind_loop()

    a = await _make_session("peer tool A")
    b = await _make_session("peer tool target")
    install_runner_factory(ScriptedRunner(_session_script({str(b): "tool target answered"})))

    try:
        context = fake_tool_context(a)

        by_id = await send_message_to_agent(
            to_session_id=str(b), content="via uuid", expect_reply=False, tool_context=context
        )
        assert by_id["success"] is True, by_id
        assert by_id["status"] == "delivered", by_id

        by_title = await send_message_to_agent(
            to_session_id="peer tool target",
            content="via title",
            expect_reply=False,
            tool_context=context,
        )
        assert by_title["success"] is True, by_title

        unknown = await send_message_to_agent(
            to_session_id="no-such-session-anywhere", content="x", tool_context=context
        )
        assert unknown["success"] is False and "could not resolve" in unknown["error"], unknown

        empty = await send_message_to_agent(
            to_session_id=str(b), content="   ", tool_context=context
        )
        assert empty["success"] is False and "content" in empty["error"], empty

        no_context = await send_message_to_agent(to_session_id=str(b), content="x")
        assert no_context["success"] is False, no_context

        listing = await list_agent_sessions(limit=50)
        assert listing["count"] >= 2, listing
        ids = {item["session_id"] for item in listing["sessions"]}
        assert str(b) in ids and str(a) in ids
        for item in listing["sessions"]:
            assert {"session_id", "title", "primary_agent_id", "running"} <= set(item), item
    finally:
        uninstall_runner_factory()
        await _cleanup(a, b)


async def main() -> None:
    await init_db()
    tests = [
        test_peer_round_trip_and_automatic_reply,
        test_busy_target_queues_then_drains,
        test_hop_limit_stops_the_conversation,
        test_messaging_your_own_session_is_refused,
        test_send_message_tool_resolution_and_validation,
    ]
    for test in tests:
        await test()
        print(f"PASS {test.__name__}")
    await shutdown_runs()
    print("\nPeer messaging suite passed.")


if __name__ == "__main__":
    asyncio.run(main())
