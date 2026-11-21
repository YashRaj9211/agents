"""
HTTP-level run management suite.

Two harness notes:

* Starlette's ``TestClient`` buffers a streaming response before returning it, so
  "open the SSE stream and walk away mid-run" cannot be expressed with
  ``client.stream``. Tests that need the app's loop to keep working after a
  viewer disappears therefore drive the run manager through ``client.portal``
  (the portal hosting the app's loop) and abandon a real
  ``RunManager.subscribe`` generator. Everything else goes over HTTP.
* All tests share **one** ``TestClient``. Each client runs the app on its own
  event loop while the database engine is a process-wide singleton, so a second
  client would reuse connections created on a loop that no longer runs -- which
  SQLite surfaces as "database is locked".

Claims pinned down here: a run keeps executing after its viewer goes away, a
finished run can be re-attached and replayed, stopping works from a different
request (by run id and by session id), and the sync endpoint still returns the
final answer.
"""
from __future__ import annotations

import time
import uuid

from fastapi.testclient import TestClient

from orchestration_helpers import (
    FakeEvent,
    ScriptedRunner,
    StallingRunner,
    done_event,
    install_runner_factory,
    parse_sse,
    uninstall_runner_factory,
)

from app.main import app
from app.services.run_manager import get_run_manager


def _create_session(client: TestClient, title: str = "srv-side session") -> str:
    response = client.post(
        "/api/sessions", json={"title": title, "primary_agent_id": "root_agent"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _start_run_via_portal(
    client: TestClient, session_id: str, prompt: str = "background work"
) -> str:
    """Starts a run on the app's own event loop, exactly as a request would."""
    manager = get_run_manager()

    async def starter() -> str:
        handle = await manager.start_run(
            session_uuid=uuid.UUID(session_id), agent_id="root_agent", prompt=prompt, origin="user"
        )
        return str(handle.run_id)

    return client.portal.call(starter)


def _chunked_script(session_id, message, chunks: int = 4):
    for index in range(chunks):
        yield FakeEvent(author="root_agent", text=f"chunk{index} ")
    yield done_event("survived the viewer going away")


def _wait_for_status(client: TestClient, run_id: str, statuses, timeout: float = 20.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        payload = client.get("/api/runs", params={"status": "all"}).json()
        matches = [r for r in payload["runs"] if r["run_id"] == run_id]
        if matches:
            last = matches[0]
            if last["status"] in statuses:
                return last
        time.sleep(0.15)
    return last


def _assistant_texts(client: TestClient, session_id: str) -> list:
    detail = client.get(f"/api/sessions/{session_id}").json()
    return [m["content"] for m in detail["messages"] if m["role"] == "assistant"]


def test_run_survives_its_viewer_disconnecting(client: TestClient) -> None:
    install_runner_factory(ScriptedRunner(_chunked_script, delay=0.2))
    try:
        session_id = _create_session(client, "disconnect session")
        run_id = _start_run_via_portal(client, session_id, "long task")
        assert run_id

        # A viewer attaches and immediately walks away. Breaking out of the async
        # generator closes it, which is what a dropped browser connection does.
        async def abandoned_viewer() -> None:
            manager = get_run_manager()
            async for _event in manager.subscribe(run_id, cursor=0, emit_attach=False):
                break

        client.portal.call(abandoned_viewer)

        # The agent is unaffected: it finishes and persists its answer.
        final = _wait_for_status(client, run_id, {"completed", "failed", "cancelled"})
        assert final is not None, "run disappeared from the run listing"
        assert final["status"] == "completed", final
        assert any(
            "survived the viewer going away" in text
            for text in _assistant_texts(client, session_id)
        ), _assistant_texts(client, session_id)
    finally:
        uninstall_runner_factory()


def test_attach_replays_run_events(client: TestClient) -> None:
    install_runner_factory(ScriptedRunner(lambda s, m: [done_event("replay target")]))
    try:
        session_id = _create_session(client, "attach session")
        with client.stream(
            "POST",
            "/api/chat/stream",
            json={"message": "go", "agent_id": "root_agent", "session_id": session_id},
        ) as response:
            initial = parse_sse("".join(response.iter_text()))
        run_id = initial[0]["run_id"]
        assert initial[0]["type"] == "start"
        assert initial[-1]["type"] == "done"

        # Attaching to a finished run replays its buffer and closes.
        response = client.get(f"/api/runs/{run_id}/stream", params={"cursor": 0})
        assert response.status_code == 200
        events = parse_sse(response.text)
        types = [e["type"] for e in events]
        assert types[0] == "attach", types
        assert types[-1] == "done", types
        assert events[0]["run_id"] == run_id
        assert any("replay target" in (e.get("final_output") or "") for e in events)

        # A cursor past the end acknowledges the whole buffer: nothing replays.
        tail = parse_sse(
            client.get(f"/api/runs/{run_id}/stream", params={"cursor": 10_000}).text
        )
        assert tail and tail[0]["type"] == "attach", tail
        assert len(tail) == 1, tail
    finally:
        uninstall_runner_factory()


def test_cancel_endpoint_stops_run_and_notifies_viewers(client: TestClient) -> None:
    install_runner_factory(StallingRunner())
    try:
        session_id = _create_session(client, "cancel session")
        run_id = _start_run_via_portal(client, session_id, "never ends")

        live = client.get("/api/runs", params={"status": "running"}).json()
        assert any(r["run_id"] == run_id for r in live["runs"]), live
        assert live["active_count"] >= 1

        cancelled = client.post(f"/api/runs/{run_id}/cancel", params={"reason": "user stop"})
        assert cancelled.status_code == 200, cancelled.text
        body = cancelled.json()
        assert body["success"] is True, body
        assert body["status"] == "cancelled", body
        assert body["cancelled"] is True, body

        final = _wait_for_status(client, run_id, {"cancelled"})
        assert final is not None and final["status"] == "cancelled", final

        # A viewer attaching now gets the terminal `cancelled` frame.
        events = parse_sse(client.get(f"/api/runs/{run_id}/stream", params={"cursor": 0}).text)
        assert events and events[0]["type"] == "attach", events[:2]
        assert any(e["type"] == "cancelled" for e in events), [e["type"] for e in events]

        # The session-level cancel is idle again once the run stopped.
        idle = client.post(f"/api/sessions/{session_id}/cancel")
        assert idle.status_code == 200
        assert idle.json()["status"] == "idle", idle.json()

        assert _assistant_texts(client, session_id), "a stopped run records what it produced"
    finally:
        uninstall_runner_factory()


def test_sync_chat_endpoint_returns_final_output(client: TestClient) -> None:
    install_runner_factory(ScriptedRunner(lambda s, m: [done_event("sync answer")]))
    try:
        session_id = _create_session(client, "sync session")
        res = client.post(
            "/api/chat",
            json={"message": "hi", "agent_id": "root_agent", "session_id": session_id},
        )
        assert res.status_code == 200, res.text
        payload = res.json()
        assert payload["response"] == "sync answer", payload
        assert payload["session_id"] == session_id, payload
    finally:
        uninstall_runner_factory()


def test_run_listing_and_detail_shapes(client: TestClient) -> None:
    install_runner_factory(ScriptedRunner(lambda s, m: [done_event("shape check")]))
    try:
        session_id = _create_session(client, "shape session")
        with client.stream(
            "POST",
            "/api/chat/stream",
            json={"message": "hi", "agent_id": "root_agent", "session_id": session_id},
        ) as response:
            events = parse_sse("".join(response.iter_text()))
        run_id = events[0]["run_id"]

        listing = client.get("/api/runs", params={"status": "all"}).json()
        assert set(listing) >= {"runs", "active_count", "limit"}, listing
        for run in listing["runs"]:
            assert set(run) >= {"run_id", "agent_id", "status", "live"}, run

        detail = client.get(f"/api/runs/{run_id}")
        assert detail.status_code == 200, detail.text
        payload = detail.json()
        assert payload["run_id"] == run_id
        assert payload["session_id"] == session_id
        assert payload["status"] == "completed"
        assert payload["session_title"] in ("shape session", None)

        missing = client.get("/api/runs/not-a-real-run")
        assert missing.status_code == 404
    finally:
        uninstall_runner_factory()


def main() -> None:
    tests = [
        test_run_survives_its_viewer_disconnecting,
        test_attach_replays_run_events,
        test_cancel_endpoint_stops_run_and_notifies_viewers,
        test_sync_chat_endpoint_returns_final_output,
        test_run_listing_and_detail_shapes,
    ]
    with TestClient(app) as client:
        for test in tests:
            test(client)
            print(f"PASS {test.__name__}")
    print("\nServer-side run suite passed.")


if __name__ == "__main__":
    main()
