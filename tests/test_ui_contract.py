"""
Contract tests pinning the API shapes the React UI (ui/web/agents-ui) consumes.

Why this exists: the existing suite asserted only status codes for the list
endpoints, so the UI's assumptions about *payload shape* were never checked. The
frontend needs three specific guarantees that are easy to regress:

1. List endpoints return JSON arrays, not wrapper objects.
2. The SSE stream's first frame is a `start` event carrying the canonical
   `session_id`, so the UI can address the row the backend actually created.
3. A session created via POST /api/sessions keeps that same id through
   streaming, message listing and timeline lookup.
"""
from fastapi.testclient import TestClient

from server import app


def _parse_sse_events(raw_text: str):
    """Minimal SSE decoder mirroring src/services/api.ts."""
    events = []
    for frame in raw_text.replace("\r\n", "\n").split("\n\n"):
        data_lines = [
            line[len("data:"):].lstrip()
            for line in frame.split("\n")
            if line.startswith("data:")
        ]
        if not data_lines:
            continue
        import json

        events.append(json.loads("\n".join(data_lines)))
    return events


def test_ui_contract():
    with TestClient(app) as client:
        # 1. Health / agents / quick-actions must be arrays or flat objects.
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        agents = client.get("/api/agents").json()
        assert isinstance(agents, list), f"/api/agents must be a list, got {type(agents)}"
        for agent in agents:
            assert set(agent) >= {"id", "name", "description"}

        actions = client.get("/api/quick-actions").json()
        assert isinstance(actions, list), "/api/quick-actions must be a list"
        for action in actions:
            # Sidebar cards read `style.color_scheme` and `target_agent_id`.
            assert set(action) >= {"id", "title", "description", "prompt", "emoji", "style"}
            assert isinstance(action["style"], dict)

        sessions_list = client.get("/api/sessions").json()
        assert isinstance(sessions_list, list), "/api/sessions must be a list"

        # 2. Create a session the way the UI does, then stream against its real id.
        created = client.post(
            "/api/sessions",
            json={"title": "UI contract session", "primary_agent_id": "root_agent"},
        )
        assert created.status_code == 201
        session_id = created.json()["id"]

        with client.stream(
            "POST",
            "/api/chat/stream",
            json={"message": "contract probe", "agent_id": "root_agent", "session_id": session_id},
        ) as stream:
            assert stream.status_code == 200
            assert stream.headers["content-type"].startswith("text/event-stream")
            raw = "".join(stream.iter_text())

        events = _parse_sse_events(raw)
        types = [e["type"] for e in events]
        assert types[0] == "start", f"first SSE frame must be 'start', got {types}"
        assert types[-1] == "done", f"last SSE frame must be 'done', got {types}"

        start = events[0]
        assert start.get("session_id"), "start event must carry session_id for the UI to adopt"
        assert start.get("run_id"), "start event must carry run_id"
        # The id we streamed against must be the id reported back, otherwise the
        # UI's follow-up session/timeline fetches address a row that does not exist.
        assert start["session_id"] == session_id, (
            f"stream echoed session_id {start['session_id']} != created {session_id}"
        )

        # 3. The session and its messages/timeline must resolve under that same id.
        detail = client.get(f"/api/sessions/{session_id}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["id"] == session_id
        assert len(detail.json()["messages"]) >= 2, "user + assistant messages should persist"

        messages = client.get(f"/api/sessions/{session_id}/messages").json()
        assert isinstance(messages["messages"], list)
        assert messages["total"] >= 2

        timeline = client.get(f"/api/sessions/{session_id}/timeline")
        assert timeline.status_code == 200
        items = timeline.json()["timeline"]
        assert isinstance(items, list) and items, "timeline should expose at least the root agent run"
        # The UI maps these exact keys into TimelineEventItem.
        for item in items:
            assert item["type"] in {"agent_run", "tool_call"}
            assert "status" in item and "started_at" in item
            assert "agent_id" in item or "tool" in item

        # Cleanup keeps the shared dev database tidy across runs.
        assert client.delete(f"/api/sessions/{session_id}").status_code == 200


if __name__ == "__main__":
    test_ui_contract()
    print("UI contract tests passed.")
