"""Manual check: assistant messages persist raw_text so history reloads match the live stream."""
import json
import os
import urllib.request

BASE = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")


def post(path, body):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=180).read())


def get(path):
    return json.loads(urllib.request.urlopen(BASE + path, timeout=60).read())


def main():
    session_id = post("/api/sessions", {"title": "metadata probe"})["id"]

    req = urllib.request.Request(
        f"{BASE}/api/chat/stream",
        data=json.dumps(
            {"message": "say METADATA_OK", "agent_id": "root_agent", "session_id": session_id}
        ).encode(),
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        resp.read()

    detail = get(f"/api/sessions/{session_id}")
    assistant = [m for m in detail["messages"] if m["role"] == "assistant"]
    print(f"assistant messages: {len(assistant)}")

    ok = False
    for message in assistant:
        meta = message.get("metadata") or {}
        has_raw = bool(meta.get("raw_text"))
        ok = ok or has_raw
        print(f"  metadata keys: {sorted(meta.keys())}")
        print(f"  raw_text present: {has_raw}")
        print(f"  content preview: {message['content'][:70]!r}")

    print("RESULT:", "raw_text PERSISTED" if ok else "MISSING raw_text")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
