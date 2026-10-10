"""Manual end-to-end check: stream the SSE chat endpoint through the Vite dev proxy.

Run with the backend on BACKEND_PORT and Vite started with
VITE_DEV_BACKEND_URL pointing at it:

    .venv/Scripts/python.exe tools/dev/check_frontend_backend.py
"""
import json
import os
import sys
import time
import urllib.request

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5199")


def main() -> int:
    payload = json.dumps(
        {"message": "reply with exactly: PROXY_OK", "agent_id": "root_agent"}
    ).encode()

    req = urllib.request.Request(
        f"{FRONTEND_ORIGIN}/api/chat/stream",
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    )

    started = time.time()
    events = []

    with urllib.request.urlopen(req, timeout=180) as resp:
        print(f"HTTP {resp.status} | content-type: {resp.headers.get('Content-Type')}")
        buffer = b""
        while True:
            chunk = resp.read(4096)
            if not chunk:
                break
            buffer += chunk
            while b"\n\n" in buffer:
                frame, buffer = buffer.split(b"\n\n", 1)
                text = frame.decode("utf-8").strip()
                if not text.startswith("data:"):
                    continue
                event = json.loads(text[5:].strip())
                events.append(event)
                body = event.get("text") or event.get("final_output") or ""
                print(
                    f"  +{time.time() - started:5.1f}s  type={event.get('type'):<14}"
                    f"session_id={event.get('session_id')}  body={body[:60]!r}"
                )

    types = [e["type"] for e in events]
    start = next((e for e in events if e["type"] == "start"), {})
    print(f"\nevent types: {types}")
    print(f"start event carries session_id: {bool(start.get('session_id'))}")
    print(f"start event carries run_id:     {bool(start.get('run_id'))}")

    ok = "start" in types and "done" in types and bool(start.get("session_id"))
    print("\nRESULT:", "SSE THROUGH PROXY OK" if ok else "PROBLEM")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
