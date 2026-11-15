"""
Shared fakes for the run-management and orchestration test suites.

The agent runs are driven through ``ChatService``'s runner-factory test hook, so
the suite can exercise parallel execution, cancellation and peer messaging
deterministically without calling an LLM.
"""
from __future__ import annotations

import asyncio
import os
import sys
from types import SimpleNamespace
from typing import Any, Callable, Dict, Iterator, List, Optional

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

# The suites default to a local SQLite file so they are hermetic and fast, but
# setting TEST_DATABASE_URL runs them against the real deployment database
# instead -- the Postgres schema enforces CHECK constraints that SQLite does not,
# so that run is worth doing before shipping.
_TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "").strip()
os.environ["DATABASE_URL"] = _TEST_DATABASE_URL or "sqlite+aiosqlite:///./data/agents.db"


class FakeEvent:
    """Minimal stand-in for a ``google.adk.events.Event``."""

    def __init__(
        self,
        author: Optional[str] = None,
        text: Optional[str] = None,
        function_calls: Optional[List[Any]] = None,
        function_responses: Optional[List[Any]] = None,
    ) -> None:
        self.author = author
        self.content = (
            SimpleNamespace(parts=[SimpleNamespace(text=text)]) if text is not None else None
        )
        self._function_calls = function_calls or []
        self._function_responses = function_responses or []

    def get_function_calls(self) -> List[Any]:
        return self._function_calls

    def get_function_responses(self) -> List[Any]:
        return self._function_responses


def done_event(text: str, author: str = "root_agent") -> FakeEvent:
    """An event whose text parses into a clean final answer."""
    return FakeEvent(author=author, text=f"<DONE>{text}</DONE>")


class ScriptedRunner:
    """Runner whose async generator is produced by ``script(session_id, message)``."""

    def __init__(self, script: Callable[[str, Any], Iterator[FakeEvent]], delay: float = 0.0):
        self.script = script
        self.delay = delay
        self.calls: List[Dict[str, Any]] = []

    async def run_async(self, *, user_id: str, session_id: str, new_message: Any = None, **_: Any):
        self.calls.append({"user_id": user_id, "session_id": session_id, "message": new_message})
        for event in self.script(session_id, new_message):
            if event is None:
                continue
            if self.delay:
                await asyncio.sleep(self.delay)
            yield event


class StallingRunner:
    """Runner that emits one chunk and then blocks until cancelled."""

    def __init__(self, stall_seconds: float = 3600.0):
        self.stall_seconds = stall_seconds
        self.calls: List[Dict[str, Any]] = []

    async def run_async(self, *, user_id: str, session_id: str, new_message: Any = None, **_: Any):
        self.calls.append({"user_id": user_id, "session_id": session_id})
        yield FakeEvent(author="root_agent", text="working...")
        await asyncio.sleep(self.stall_seconds)
        yield done_event("never reached")


def install_runner_factory(runner: Any, *, delays: Optional[Dict[str, float]] = None):
    """Installs a fake runner factory for the duration of a test.

    ``delays`` maps an agent id to a per-run delay so a test can make one agent
    slower than another. Returns the factory that was installed.
    """
    from app.services.chat_service import set_runner_factory

    def factory(agent_id: str):
        if delays and agent_id in delays:
            return ScriptedRunner(runner.script, delay=delays[agent_id])
        return runner

    set_runner_factory(factory)
    return factory


def uninstall_runner_factory() -> None:
    from app.services.chat_service import set_runner_factory

    set_runner_factory(None)


def fake_tool_context(session_id: Any, agent_id: str = "root_agent") -> Any:
    """A stand-in for ``google.adk.tools.tool_context.ToolContext``."""
    return SimpleNamespace(
        session=SimpleNamespace(id=f"{session_id}::{agent_id}"),
        agent_name=agent_id,
    )


async def wait_for(predicate: Callable[[], Any], timeout: float = 10.0, interval: float = 0.05):
    """Polls ``predicate`` until it is truthy or the timeout expires."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        result = predicate()
        if asyncio.iscoroutine(result):
            result = await result
        if result:
            return result
        await asyncio.sleep(interval)
    return None


async def shutdown_runs() -> None:
    """Cancels leftover runs at the end of a suite.

    Without this, a background run can still be writing when ``asyncio.run``
    closes the loop, which surfaces as confusing driver errors *after* the suite
    has passed. Cancelling first makes teardown deterministic.
    """
    from app.services.run_manager import get_run_manager

    manager = get_run_manager()
    if manager.loop is not None:
        await manager.shutdown()


def parse_sse(raw_text: str) -> List[Dict[str, Any]]:
    """Decodes SSE frames exactly like ``src/services/api.ts`` does."""
    import json

    events: List[Dict[str, Any]] = []
    for frame in raw_text.replace("\r\n", "\n").split("\n\n"):
        data_lines = [
            line[len("data:"):].lstrip()
            for line in frame.split("\n")
            if line.startswith("data:")
        ]
        if not data_lines:
            continue
        events.append(json.loads("\n".join(data_lines)))
    return events
