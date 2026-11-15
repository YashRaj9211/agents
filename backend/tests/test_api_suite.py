"""
Comprehensive automated test suite verifying the modular FastAPI architecture
and complete chat API suite.
"""
from fastapi.testclient import TestClient
from server import app


def test_full_api_suite():
    with TestClient(app) as client:
        # 1. Health check & middleware timing header
        res_health = client.get("/api/health")
        assert res_health.status_code == 200, res_health.text
        assert res_health.json()["status"] == "ok"
        assert "x-process-time" in res_health.headers

        # 2. Agent Catalog
        res_agents = client.get("/api/agents")
        assert res_agents.status_code == 200
        agents = res_agents.json()
        assert len(agents) >= 6
        assert any(a["id"] == "root_agent" for a in agents)

        # 3. Quick Actions
        res_actions = client.get("/api/quick-actions")
        assert res_actions.status_code == 200
        actions = res_actions.json()
        assert len(actions) >= 4

        # 4. Session Lifecycle: Create
        res_sess = client.post(
            "/api/sessions",
            json={"title": "Automated Test Session", "primary_agent_id": "root_agent"},
        )
        assert res_sess.status_code == 201, res_sess.text
        sess_data = res_sess.json()
        session_id = sess_data["id"]
        assert sess_data["title"] == "Automated Test Session"

        # 5. List Sessions
        res_list = client.get("/api/sessions")
        assert res_list.status_code == 200
        session_ids = [s["id"] for s in res_list.json()]
        assert session_id in session_ids

        # 6. Update Session Title (PATCH)
        res_patch = client.patch(
            f"/api/sessions/{session_id}",
            json={"title": "Renamed Session Title"},
        )
        assert res_patch.status_code == 200
        assert res_patch.json()["title"] == "Renamed Session Title"

        # 7. Session Details
        res_details = client.get(f"/api/sessions/{session_id}")
        assert res_details.status_code == 200
        assert res_details.json()["title"] == "Renamed Session Title"
        assert len(res_details.json()["messages"]) == 0

        # 8. Message Operations: Insert messages
        res_msg1 = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"role": "user", "content": "First manual test message"},
        )
        assert res_msg1.status_code == 201
        msg1 = res_msg1.json()
        assert msg1["seq"] == 1
        msg1_id = msg1["id"]

        res_msg2 = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"role": "assistant", "content": "Second manual test message"},
        )
        assert res_msg2.status_code == 201
        msg2 = res_msg2.json()
        assert msg2["seq"] == 2

        # 9. List Messages Endpoint
        res_msg_list = client.get(f"/api/sessions/{session_id}/messages")
        assert res_msg_list.status_code == 200
        assert res_msg_list.json()["total"] == 2

        # 10. Delete Single Message
        res_del_msg = client.delete(f"/api/messages/{msg1_id}")
        assert res_del_msg.status_code == 200

        res_msg_list_after = client.get(f"/api/sessions/{session_id}/messages")
        assert res_msg_list_after.json()["total"] == 1

        # 11. Clear Session Messages
        res_clear = client.delete(f"/api/sessions/{session_id}/messages")
        assert res_clear.status_code == 200

        res_msg_list_cleared = client.get(f"/api/sessions/{session_id}/messages")
        assert res_msg_list_cleared.json()["total"] == 0

        # 12. Chat Execution Endpoint
        res_chat = client.post(
            "/api/chat",
            json={
                "message": "Hello from automated test suite",
                "agent_id": "root_agent",
                "session_id": session_id,
            },
        )
        assert res_chat.status_code == 200
        chat_body = res_chat.json()
        assert "response" in chat_body
        assert chat_body["session_id"] == session_id

        # 13. Execution Timeline
        res_timeline = client.get(f"/api/sessions/{session_id}/timeline")
        assert res_timeline.status_code == 200
        timeline_items = res_timeline.json()["timeline"]
        assert len(timeline_items) >= 1

        # 14. Session Deletion
        res_del_sess = client.delete(f"/api/sessions/{session_id}")
        assert res_del_sess.status_code == 200

        res_list_final = client.get("/api/sessions")
        final_session_ids = [s["id"] for s in res_list_final.json()]
        assert session_id not in final_session_ids

        # 15. Garage S3 Artifacts Lifecycle (Upload, List, Download, Delete)
        file_content = b"This is a test artifact uploaded to Garage S3 object storage."
        res_upload = client.post(
            "/api/artifacts/upload",
            files={"file": ("test_artifact.txt", file_content, "text/plain")},
        )
        assert res_upload.status_code == 200, res_upload.text
        art_data = res_upload.json()
        assert art_data["origin"] == "user_upload"
        assert art_data["storage_uri"].startswith("s3://agents-artifacts/")
        art_id = art_data["id"]

        # Download from Garage S3
        res_down = client.get(f"/api/artifacts/{art_id}/download")
        assert res_down.status_code == 200
        assert res_down.content == file_content

        # List artifacts
        res_art_list = client.get("/api/artifacts")
        assert res_art_list.status_code == 200
        assert any(a["id"] == art_id for a in res_art_list.json()["artifacts"])

        # Delete artifact
        res_art_del = client.delete(f"/api/artifacts/{art_id}")
        assert res_art_del.status_code == 200

        print("\nAll 15 integration test assertions (including Garage S3 artifacts) passed successfully!")


if __name__ == "__main__":
    test_full_api_suite()
