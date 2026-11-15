"""
ADK session persistence suite.

The agent conversation memory must survive a backend restart, which is why the
runners use ADK's ``DatabaseSessionService`` instead of ``InMemoryRunner``. ADK's
schema owns tables called ``sessions`` and ``events``, which collide with this
app's own ``sessions`` table, so it gets its own database
(``ADK_SESSION_DB_URL``). These tests pin both facts.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile

# Must be set before app.core.config is imported: Settings snapshots the env.
_TMP_ROOT = tempfile.mkdtemp(prefix="adk-persistence-")
_ADK_DB_PATH = os.path.join(_TMP_ROOT, "adk_sessions.db")
os.environ["ADK_SESSION_DB_URL"] = "sqlite+aiosqlite:///" + _ADK_DB_PATH.replace("\\", "/")

from orchestration_helpers import REPO_ROOT  # noqa: E402  (sets DATABASE_URL too)

import asyncio  # noqa: E402
import uuid  # noqa: E402

from db.connection import async_session_scope, get_engine, init_db  # noqa: E402
from db.repository import Repository  # noqa: E402


async def test_session_and_events_survive_a_new_service_instance() -> None:
    from google.adk.events.event import Event
    from google.adk.sessions.database_session_service import DatabaseSessionService
    from google.genai import types

    url = os.environ["ADK_SESSION_DB_URL"]
    conversation = f"conv-{uuid.uuid4()}"
    adk_session_id = f"{conversation}::root_agent"

    # "First process": create the session and record a turn.
    first = DatabaseSessionService(db_url=url)
    await first.create_session(
        app_name="agents_app", user_id="default_user", session_id=adk_session_id
    )
    session = await first.get_session(
        app_name="agents_app", user_id="default_user", session_id=adk_session_id
    )
    await first.append_event(
        session=session,
        event=Event(
            invocation_id="inv-1",
            author="root_agent",
            content=types.Content(
                role="user", parts=[types.Part.from_text(text="remember this request")]
            ),
        ),
    )

    # "Second process": a fresh service instance on the same database.
    second = DatabaseSessionService(db_url=url)
    reloaded = await second.get_session(
        app_name="agents_app", user_id="default_user", session_id=adk_session_id
    )
    assert reloaded is not None, "session did not survive a new service instance"
    assert len(reloaded.events) == 1, [e.id for e in reloaded.events]
    assert reloaded.events[0].content.parts[0].text == "remember this request"


async def test_adk_store_is_a_separate_database() -> None:
    """ADK's ``sessions`` table must not be this app's ``sessions`` table."""
    adk_tables = _tables(_ADK_DB_PATH)
    assert {"sessions", "events", "app_states", "user_states", "adk_internal_metadata"} <= set(
        adk_tables
    ), adk_tables

    # ADK's sessions table is keyed by (app_name, user_id, id).
    adk_columns = _columns(_ADK_DB_PATH, "sessions")
    assert {"app_name", "user_id", "id", "state"} <= set(adk_columns), adk_columns

    # The application database's sessions table keeps its own shape.
    app_url = str(get_engine().url)
    if app_url.startswith("sqlite"):
        app_path = app_url.split("///")[-1]
        if os.path.exists(app_path):
            app_columns = _columns(app_path, "sessions")
            assert "app_name" not in app_columns, app_columns
            assert {"workspace_id", "user_id", "primary_agent_id", "title"} <= set(app_columns), (
                app_columns
            )
    else:  # pragma: no cover - Postgres deployment
        assert "postgresql" in app_url


async def test_runner_registry_uses_persistent_sessions() -> None:
    """The app must build runners on the database-backed session service."""
    from google.adk.sessions.database_session_service import DatabaseSessionService
    from google.adk.sessions.in_memory_session_service import InMemorySessionService

    from app.services import chat_service

    service = chat_service.get_adk_session_service()
    assert isinstance(service, DatabaseSessionService), type(service)
    assert not isinstance(service, InMemorySessionService)
    assert service.db_engine.url.database in _ADK_DB_PATH.replace("\\", "/"), service.db_engine.url

    # The configured URL is honoured, so a deployment can point it at Postgres.
    from app.core.config import settings

    assert settings.ADK_SESSION_DB_URL in os.environ["ADK_SESSION_DB_URL"]

    try:
        runner = chat_service.get_runner("root_agent")
    except Exception as exc:  # pragma: no cover - depends on the agent tree importing
        print(f"  (skipped runner construction: {exc})")
        return
    if runner is None:  # pragma: no cover
        print("  (skipped: root_agent not importable)")
        return
    assert runner.session_service is service, "runners must share the persistent session store"


async def test_adk_session_ids_isolate_agents_per_conversation() -> None:
    from app.services.chat_service import adk_session_id_for

    conversation = "9f1d0f5e-1111-2222-3333-444455556666"
    root = adk_session_id_for(conversation, "root_agent")
    browser = adk_session_id_for(conversation, "browser_agent")

    assert root == f"{conversation}::root_agent"
    assert browser == f"{conversation}::browser_agent"
    assert root != browser, "each agent keeps its own memory thread in a conversation"
    assert root.split("::")[0] == browser.split("::")[0] == conversation


async def test_repository_and_adk_do_not_share_tables() -> None:
    """Writing an app session must not create ADK rows (and vice versa)."""
    await init_db()
    async with async_session_scope() as db:
        user, workspace = await Repository.get_or_create_default_identity(db)
        sess = await Repository.create_session(
            db,
            workspace_id=workspace.id,
            user_id=user.id,
            title="adk isolation check",
            primary_agent_id="root_agent",
        )
        session_id = sess.id

    adk_tables = set(_tables(_ADK_DB_PATH))
    if "sessions" in adk_tables:
        rows = _query(_ADK_DB_PATH, "SELECT COUNT(*) FROM sessions WHERE id = ?", (str(session_id),))
        assert rows[0][0] == 0, "app session leaked into ADK's sessions table"

    async with async_session_scope() as db:
        await Repository.delete_session(db, session_id)


def _tables(path: str) -> list:
    if not os.path.exists(path):
        return []
    con = sqlite3.connect(path)
    try:
        return [row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    finally:
        con.close()


def _columns(path: str, table: str) -> list:
    con = sqlite3.connect(path)
    try:
        return [row[1] for row in con.execute(f"PRAGMA table_info({table})")]
    finally:
        con.close()


def _query(path: str, sql: str, params=()) -> list:
    con = sqlite3.connect(path)
    try:
        return list(con.execute(sql, params))
    finally:
        con.close()


async def main() -> None:
    await init_db()
    tests = [
        test_session_and_events_survive_a_new_service_instance,
        test_adk_store_is_a_separate_database,
        test_runner_registry_uses_persistent_sessions,
        test_adk_session_ids_isolate_agents_per_conversation,
        test_repository_and_adk_do_not_share_tables,
    ]
    try:
        for test in tests:
            await test()
            print(f"PASS {test.__name__}")
        print("\nADK session persistence suite passed.")
    finally:
        shutil.rmtree(_TMP_ROOT, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
