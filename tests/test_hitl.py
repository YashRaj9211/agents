"""
Human-in-the-loop suite: the question registry, the answer endpoint, and the
blocking ``ask_user`` tool that connects them.

The property under test is that an agent can *stop* on a question and resume
inside the same run with the user's real answer -- and that every failure path
(timeout, cancellation, duplicate answer, unknown question) closes cleanly
instead of leaving the agent or the UI hanging.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./agents.db")

import httpx  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.services.hitl_service import (  # noqa: E402
    HumanInputError,
    PendingHumanInput,
    get_hitl_service,
    reset_hitl_service,
)
from app.services.run_manager import RunHandle, get_run_manager  # noqa: E402
from orchestration_helpers import fake_tool_context  # noqa: E402
from tools.hitl_tools.ask_user import ask_user  # noqa: E402


async def _client() -> httpx.AsyncClient:
    """An in-process HTTP client bound to the real FastAPI app."""
    transport = httpx.ASGITransport(app=fastapi_app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


class _LiveQuestion:
    """Opens a question inside the caller's loop and cleans it up afterwards."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.record: PendingHumanInput | None = None

    async def __aenter__(self) -> PendingHumanInput:
        self.record = get_hitl_service().create_request(**self.kwargs)
        return self.record

    async def __aexit__(self, *exc) -> None:
        if self.record is not None:
            get_hitl_service().expire(self.record.question_id, reason="test_cleanup")


async def test_answer_endpoint_resolves_the_question() -> None:
    """POST /api/hitl/{id}/answer must resolve exactly the question it names."""
    reset_hitl_service()
    session_id = str(uuid.uuid4())

    async with _LiveQuestion(
        session_id=session_id,
        question="Delete build artifacts?",
        kind="confirm",
        run_id="run-confirm",
        agent_id="cli_agent",
    ) as record:
        async with await _client() as client:
            # The UI can rediscover the card after a reload.
            pending = await client.get(f"/api/sessions/{session_id}/hitl/pending")
            assert pending.status_code == 200, pending.text
            body = pending.json()
            assert body["total"] == 1, body
            assert body["questions"][0]["question_id"] == record.question_id
            assert body["questions"][0]["kind"] == "confirm"

            answered = await client.post(
                f"/api/hitl/{record.question_id}/answer", json={"answer": "yes"}
            )
            assert answered.status_code == 200, answered.text
            assert answered.json()["answered"] is True
            assert answered.json()["answer"] == "Yes"

            # The agent waiting on the future has now been unblocked.
            assert record.future is not None and record.future.done()
            assert record.future.result()["status"] == "answered"

            # And the card is gone from the pending list.
            pending_after = await client.get(f"/api/sessions/{session_id}/hitl/pending")
            assert pending_after.json()["total"] == 0, pending_after.json()

            # A second answer must not silently succeed.
            duplicate = await client.post(
                f"/api/hitl/{record.question_id}/answer", json={"answer": "no"}
            )
            assert duplicate.status_code == 404, duplicate.text


async def test_answer_endpoint_rejects_bad_answers_and_unknown_ids() -> None:
    reset_hitl_service()

    async with _LiveQuestion(
        session_id=str(uuid.uuid4()),
        question="Which environment?",
        kind="choice",
        options=["dev", "prod"],
    ) as record:
        async with await _client() as client:
            invalid = await client.post(
                f"/api/hitl/{record.question_id}/answer", json={"answer": "staging"}
            )
            assert invalid.status_code == 409, invalid.text
            # The app's error middleware wraps HTTPException detail under `message`.
            assert "options" in invalid.json()["message"]

            unknown = await client.post(
                "/api/hitl/does-not-exist/answer", json={"answer": "yes"}
            )
            assert unknown.status_code == 404, unknown.text

            # The question survives a rejected answer and can still be answered.
            valid = await client.post(
                f"/api/hitl/{record.question_id}/answer", json={"answer": "prod"}
            )
            assert valid.status_code == 200, valid.text


async def test_registry_normalizes_kinds_answers_and_timeouts() -> None:
    reset_hitl_service()
    service = get_hitl_service()
    session_id = str(uuid.uuid4())

    # Multi-select answers are normalized against the declared options.
    async with _LiveQuestion(
        session_id=session_id,
        question="Which checks should run?",
        kind="multi_choice",
        options=["lint", "tests", "types"],
    ) as record:
        resolved = service.resolve(record.question_id, ["lint", "types", "nonsense"])
        assert resolved.future.result()["raw_answer"] == ["lint", "types"]

    # An unknown kind degrades to free text instead of raising.
    async with _LiveQuestion(
        session_id=session_id, question="Anything else?", kind="sorcery"
    ) as record:
        assert record.kind == "text"
        service.resolve(record.question_id, "some words")
        assert record.future.result()["answer"] == "some words"

    # A choice question with no options cannot be rendered, so it is refused.
    try:
        service.create_request(
            session_id=session_id, question="Pick one", kind="choice", options=[]
        )
        raise AssertionError("a choice question without options must be rejected")
    except HumanInputError:
        pass

    # Timeout closes the question without an answer rather than leaving it open.
    async with _LiveQuestion(
        session_id=session_id, question="Still there?", kind="text"
    ) as record:
        service.expire(record.question_id, reason="timeout")
        assert record.future.result()["status"] == "timeout"
        assert service.get(record.question_id) is None


async def test_fail_all_releases_a_cancelled_runs_questions() -> None:
    """Stopping a run must not leave its question card behind."""
    reset_hitl_service()
    service = get_hitl_service()
    session_id = str(uuid.uuid4())

    first = service.create_request(session_id=session_id, question="One?", kind="confirm")
    second = service.create_request(session_id=session_id, question="Two?", kind="text")

    closed = service.fail_all(session_id, reason="cancelled")
    assert closed == 2
    assert first.future.result()["status"] == "cancelled"
    assert second.future.result()["status"] == "cancelled"
    assert service.pending_for_session(session_id) == []


class _FakeRun:
    """Registers a run handle directly with the manager.

    ``ask_user`` only needs two things from a run: a resolvable session, and a
    live event buffer to publish the question onto. Driving a real agent would
    drag in an LLM call and a database write for no extra coverage, so tests
    register the handle the manager would have created.
    """

    def __init__(self, session_id: uuid.UUID, agent_id: str = "cli_agent"):
        self.session_id = session_id
        self.handle = RunHandle(
            run_id=uuid.uuid4(), session_id=session_id, agent_id=agent_id
        )

    async def __aenter__(self) -> RunHandle:
        manager = get_run_manager()
        manager.bind_loop()
        manager._runs[str(self.handle.run_id)] = self.handle  # noqa: SLF001 - test seam
        manager._session_active[str(self.session_id)] = str(self.handle.run_id)  # noqa: SLF001
        return self.handle

    async def __aexit__(self, *exc) -> None:
        manager = get_run_manager()
        manager._runs.pop(str(self.handle.run_id), None)  # noqa: SLF001
        manager._session_active.pop(str(self.session_id), None)  # noqa: SLF001
        get_hitl_service().fail_all(str(self.session_id), reason="test_cleanup")


async def _wait_for_question(run_id: str, timeout: float = 5.0) -> PendingHumanInput | None:
    """Waits for the blocking tool to register its question."""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        pending = get_hitl_service().pending_for_run(run_id)
        if pending:
            return pending[0]
        await asyncio.sleep(0.01)
    return None


async def test_ask_user_blocks_then_resumes_with_the_answer() -> None:
    """The end-to-end property: ask_user waits, the answer comes back as data."""
    reset_hitl_service()
    session_uuid = uuid.uuid4()

    original_timeout = settings.HITL_TIMEOUT_SECONDS
    settings.HITL_TIMEOUT_SECONDS = 20
    try:
        async with _FakeRun(session_uuid) as handle:
            # The tool blocks, exactly as it would inside the run's own task.
            tool_task = asyncio.create_task(
                ask_user(
                    question="This will delete the database. Continue?",
                    kind="confirm",
                    tool_context=fake_tool_context(session_uuid, "cli_agent"),
                )
            )

            record = await _wait_for_question(str(handle.run_id))
            assert record is not None, "ask_user never registered its question"

            # It must publish the question onto the run's replayable buffer, so a
            # viewer that attaches late still sees the card.
            events = [e for e in handle.events if e.get("type") == "human_input_request"]
            assert events, "human_input_request must be published for late subscribers"
            assert events[0]["question_id"] == record.question_id
            assert events[0]["kind"] == "confirm"
            assert not tool_task.done(), "ask_user must still be blocked on the question"

            # ...and the answer endpoint must unblock it with the user's decision.
            async with await _client() as client:
                response = await client.post(
                    f"/api/hitl/{record.question_id}/answer", json={"answer": True}
                )
                assert response.status_code == 200, response.text

            result = await asyncio.wait_for(tool_task, timeout=5)
            assert result["status"] == "answered", result
            assert result["answer"] == "Yes", result
            assert "Yes" in result["message"]
    finally:
        settings.HITL_TIMEOUT_SECONDS = original_timeout


async def test_ask_user_times_out_instead_of_hanging_forever() -> None:
    reset_hitl_service()
    session_uuid = uuid.uuid4()

    original_timeout = settings.HITL_TIMEOUT_SECONDS
    settings.HITL_TIMEOUT_SECONDS = 0.2
    try:
        async with _FakeRun(session_uuid) as handle:
            result = await asyncio.wait_for(
                ask_user(
                    question="Anyone there?",
                    kind="text",
                    tool_context=fake_tool_context(session_uuid, "cli_agent"),
                ),
                timeout=5,
            )
        assert result["status"] == "timeout", result
        assert get_hitl_service().pending_for_run(str(handle.run_id)) == []
    finally:
        settings.HITL_TIMEOUT_SECONDS = original_timeout


async def test_ask_user_without_a_route_does_not_block() -> None:
    """No session context means no place to ask: the agent must be told, not hung."""
    reset_hitl_service()
    result = await asyncio.wait_for(
        ask_user(question="Which one?", kind="text", tool_context=None), timeout=2
    )
    assert result["status"] == "no_route", result
    assert result["answer"] == ""


async def main() -> None:
    tests = [
        test_answer_endpoint_resolves_the_question,
        test_answer_endpoint_rejects_bad_answers_and_unknown_ids,
        test_registry_normalizes_kinds_answers_and_timeouts,
        test_fail_all_releases_a_cancelled_runs_questions,
        test_ask_user_blocks_then_resumes_with_the_answer,
        test_ask_user_times_out_instead_of_hanging_forever,
        test_ask_user_without_a_route_does_not_block,
    ]
    for test in tests:
        await test()
        print(f"PASS {test.__name__}")
    print("\nHITL suite passed.")


if __name__ == "__main__":
    asyncio.run(main())
