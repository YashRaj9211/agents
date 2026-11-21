"""
Orchestration tools: peer messaging and parallel fan-out for agents.

These tools make several agents collaborate instead of one agent doing
everything itself:

* :func:`send_message_to_agent` -- talk to another session's agent (answers come
  back automatically).
* :func:`list_agent_sessions` / :func:`list_active_runs` -- find a target.
* :func:`spawn_agents` -- start N independent runs in parallel for separate tasks.
* :func:`await_agents` -- collect those runs' final answers.
* :func:`cancel_agent_run` -- stop a run (and, by default, what it spawned).

All of them are ``async def`` on purpose: ADK awaits async tool functions on the
server's own event loop, which is the loop the run manager is bound to, so no
threads or extra event loops are involved.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.run_manager import RunBusyError, RunCapacityError, get_run_manager
from db.connection import async_session_scope
from db.repository import Repository

logger = logging.getLogger("tools.orchestration")

#: Hard ceiling on one fan-out call, independent of the global run cap.
MAX_SPAWN_PER_CALL = 8

try:  # pragma: no cover - import guard for tooling environments without ADK types
    from google.adk.tools.tool_context import ToolContext
except Exception:  # pragma: no cover
    ToolContext = Any  # type: ignore[assignment]


# ───────────────────────── helpers ─────────────────────────

def _caller_identity(tool_context: Any) -> Optional[Dict[str, Any]]:
    """Extracts (session uuid, agent id, adk session id) from the ADK context.

    ADK session ids are ``<session_uuid>::<agent_id>`` (see
    ``app.services.chat_service.adk_session_id_for``), so the conversation uuid
    can be recovered without extra plumbing.
    """
    if tool_context is None:
        return None
    try:
        session = tool_context.session
        adk_session_id = str(getattr(session, "id", "") or "")
        agent_id = str(getattr(tool_context, "agent_name", "") or "")
    except Exception:
        return None

    if not adk_session_id:
        return None
    session_part, _, agent_part = adk_session_id.partition("::")
    try:
        session_uuid = uuid.UUID(session_part)
    except (ValueError, AttributeError):
        return None
    return {
        "session_uuid": session_uuid,
        "agent_id": agent_part or agent_id or "root_agent",
        "adk_session_id": adk_session_id,
    }


async def _resolve_session(identifier: str) -> Optional[uuid.UUID]:
    """Accepts a full/partial session UUID, or a session title."""
    if not identifier:
        return None
    try:
        return uuid.UUID(str(identifier))
    except (ValueError, AttributeError):
        pass

    needle = str(identifier).strip().lower()
    if not needle:
        return None

    async with async_session_scope() as db:
        user, _ = await Repository.get_or_create_default_identity(db)
        sessions = await Repository.list_user_sessions(db, user.id, limit=200)

    for sess in sessions:  # exact id prefix first
        if str(sess.id).startswith(needle):
            return sess.id
    for sess in sessions:  # then title match
        if needle in (sess.title or "").lower():
            return sess.id
    return None


async def _run_status(run_id: str) -> Optional[Dict[str, Any]]:
    """Status of a run: from the live registry when present, else from the DB."""
    manager = get_run_manager()
    handle = manager.get(run_id)
    if handle:
        return {
            "run_id": str(handle.run_id),
            "session_id": str(handle.session_id),
            "agent_id": handle.agent_id,
            "status": handle.status,
            "output": handle.final_output or None,
            "error": handle.error,
            "live": handle.status not in {"completed", "failed", "cancelled", "interrupted"},
        }

    try:
        run_uuid = uuid.UUID(str(run_id))
    except (ValueError, AttributeError):
        return None

    async with async_session_scope() as db:
        run = await Repository.get_agent_run(db, run_uuid)
        if not run:
            return None
        final_output = None
        if run.session_id:
            messages = await Repository.list_session_messages(db, run.session_id)
            for message in reversed(messages):
                if message.run_id == run.id and message.role == "assistant":
                    final_output = message.content
                    break
        return {
            "run_id": str(run.id),
            "session_id": str(run.session_id) if run.session_id else None,
            "agent_id": run.agent_id,
            "status": run.status,
            "output": final_output,
            "error": (run.error or {}).get("detail") if isinstance(run.error, dict) else None,
            "live": False,
        }


# ───────────────────────── tools ─────────────────────────

async def send_message_to_agent(
    to_session_id: str,
    content: str,
    expect_reply: bool = True,
    tool_context: ToolContext = None,  # type: ignore[assignment]
) -> Dict[str, Any]:
    """Send a message from this agent to the agent running in another session.

    Args:
        to_session_id: Target session UUID (or a unique prefix of it, or its title).
        content: What to tell the other agent. Be explicit about the request.
        expect_reply: When true, the target agent's answer is delivered back to
            this session automatically as a follow-up message.

    Returns:
        A dict with 'success', 'message_id' and 'status' ('delivered' when the
        target started working immediately, 'queued' when it finishes its
        current turn first).
    """
    manager = get_run_manager()
    caller = _caller_identity(tool_context)
    if not caller:
        return {"success": False, "error": "no caller session context available"}

    if not content or not str(content).strip():
        return {"success": False, "error": "content must not be empty"}

    target = await _resolve_session(to_session_id)
    if target is None:
        return {
            "success": False,
            "error": f"could not resolve target session '{to_session_id}'",
            "hint": "call list_agent_sessions() to see available session ids",
        }
    if str(target) == str(caller["session_uuid"]):
        return {"success": False, "error": "refused: target is this agent's own session"}

    handle = manager.get(manager.active_run_id_for_session(caller["session_uuid"]) or "")
    result = await manager.send_peer_message(
        sender=handle,
        to_session_id=target,
        content=str(content),
        expect_reply=bool(expect_reply),
        sender_agent_id=caller["agent_id"],
        sender_session_id=caller["session_uuid"],
    )
    return result


async def list_agent_sessions(limit: int = 20) -> Dict[str, Any]:
    """List recent agent sessions so you can choose who to message or inspect.

    Args:
        limit: Maximum number of sessions to return (most recently active first).

    Returns:
        A dict with a 'sessions' list holding id, title, primary agent, preview
        and whether the session currently has a running agent.
    """
    manager = get_run_manager()
    async with async_session_scope() as db:
        user, _ = await Repository.get_or_create_default_identity(db)
        sessions = await Repository.list_user_sessions(db, user.id, limit=max(1, min(limit, 100)))

    items = []
    for sess in sessions:
        active = manager.active_run_id_for_session(sess.id)
        items.append(
            {
                "session_id": str(sess.id),
                "title": sess.title or "Conversation",
                "primary_agent_id": sess.primary_agent_id or "root_agent",
                "preview": (sess.preview_text or "")[:160],
                "running": bool(active),
                "active_run_id": active,
            }
        )
    return {"sessions": items, "count": len(items)}


async def list_active_runs() -> Dict[str, Any]:
    """List agent runs that are executing right now.

    Returns:
        A dict with a 'runs' list holding run_id, session_id, agent_id, status,
        origin ('user', 'peer', 'spawn' or 'delegated') and elapsed time.
    """
    manager = get_run_manager()
    return {
        "runs": [handle.summary() for handle in manager.live_runs()],
        "active_count": manager.active_count(),
        "limit": settings.MAX_CONCURRENT_RUNS,
    }


async def spawn_agents(
    tasks: list,
    tool_context: ToolContext = None,  # type: ignore[assignment]
) -> Dict[str, Any]:
    """Start several agents in parallel, each in its own new session.

    Use this to hand independent pieces of work to different agents at once and
    then collect their results with await_agents().

    Args:
        tasks: A list of objects, each with:
            - 'agent_id' (str, required): e.g. 'browser_agent', 'cli_agent',
              'firecrawl_agent', 'job_assist_agent', 'scheduler_agent', 'root_agent'.
            - 'prompt' (str, required): the instruction for that agent.
            - 'session_title' (str, optional): title for the new session.

    Returns:
        A dict with 'spawned' (list of {run_id, session_id, agent_id, status}) and
        'failed' (list of tasks that could not start, with 'error').
    """
    manager = get_run_manager()
    caller = _caller_identity(tool_context)
    if not isinstance(tasks, list) or not tasks:
        return {"success": False, "error": "'tasks' must be a non-empty list"}

    if len(tasks) > MAX_SPAWN_PER_CALL:
        return {
            "success": False,
            "error": f"too many tasks ({len(tasks)}); at most {MAX_SPAWN_PER_CALL} per call",
        }

    try:
        from app.services.chat_service import get_agents

        known_agents = set(get_agents().keys()) or None
    except Exception:  # pragma: no cover - agents always importable in practice
        known_agents = None

    # The calling run becomes the parent of everything spawned here, which is
    # what makes cancelling the parent stop its fan-out (and gives the UI a real
    # run tree to show).
    parent_run_id: Optional[uuid.UUID] = None
    if caller:
        active_id = manager.active_run_id_for_session(caller["session_uuid"])
        if active_id:
            try:
                parent_run_id = uuid.UUID(active_id)
            except (ValueError, AttributeError):
                parent_run_id = None

    spawned: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []

    # Phase 1: create every session and let the transaction commit. Runs must not
    # be started inside this scope: agent_runs.session_id is a real FK, and
    # another connection would not see an uncommitted session row.
    planned: List[Dict[str, Any]] = []
    async with async_session_scope() as db:
        user, workspace = await Repository.get_or_create_default_identity(db)

        for index, task in enumerate(tasks):
            agent_id = str((task or {}).get("agent_id") or "root_agent")
            prompt = str((task or {}).get("prompt") or "").strip()
            title = str((task or {}).get("session_title") or "").strip()

            if not prompt:
                failed.append({"agent_id": agent_id, "error": "empty prompt"})
                continue
            if known_agents is not None and agent_id not in known_agents:
                failed.append({"agent_id": agent_id, "error": "unknown agent id"})
                continue

            session = await Repository.create_session(
                db,
                workspace_id=workspace.id,
                user_id=user.id,
                title=title or f"{agent_id} · {prompt[:40]}",
                primary_agent_id=agent_id,
                # Hidden from the sidebar: results come back into the parent chat.
                status="spawned",
            )
            planned.append(
                {
                    "index": index,
                    "agent_id": agent_id,
                    "prompt": prompt,
                    "session_title": title or None,
                    "session_id": session.id,
                    "workspace_id": workspace.id,
                }
            )

    # Phase 2: start the runs in parallel (each is a new background task).
    for item in planned:
        try:
            handle = await manager.start_run(
                session_uuid=item["session_id"],
                agent_id=item["agent_id"],
                prompt=item["prompt"],
                origin="spawn",
                parent_run_id=parent_run_id,
                workspace_id=item["workspace_id"],
                fold_pending_peers=False,
            )
        except RunBusyError as exc:
            failed.append(
                {"agent_id": item["agent_id"], "session_id": str(item["session_id"]), "error": str(exc)}
            )
            continue
        except RunCapacityError as exc:
            failed.append(
                {
                    "agent_id": item["agent_id"],
                    "session_id": str(item["session_id"]),
                    "error": f"capacity: {exc.limit} runs already active",
                }
            )
            continue

        spawned.append(
            {
                "agent_id": item["agent_id"],
                "prompt": item["prompt"],
                "run_id": str(handle.run_id),
                "session_id": str(item["session_id"]),
                "session_title": item["session_title"],
                "status": handle.status,
                "index": item["index"],
            }
        )

    if spawned and caller and parent_run_id:
        manager.publish(
            parent_run_id,
            {
                "type": "agent_spawned",
                "run_id": str(parent_run_id),
                "spawned": [
                    {
                        "run_id": item["run_id"],
                        "session_id": item["session_id"],
                        "agent_id": item["agent_id"],
                    }
                    for item in spawned
                ],
            },
        )

    return {
        "success": bool(spawned),
        "spawned": spawned,
        "failed": failed,
        "hint": "call await_agents(run_ids=[...]) to collect their answers",
    }


async def await_agents(run_ids: list, timeout_seconds: int = 600) -> Dict[str, Any]:
    """Wait for spawned runs to finish and return their final answers.

    Args:
        run_ids: Run ids returned by spawn_agents() (or seen in list_active_runs()).
        timeout_seconds: Give up (without cancelling) after this many seconds.

    Returns:
        A dict with 'status' ('completed' or 'timeout'), 'results' (one entry per
        run: run_id, session_id, agent_id, status, output) and 'pending'.
    """
    if not isinstance(run_ids, list) or not run_ids:
        return {"success": False, "error": "'run_ids' must be a non-empty list"}

    wanted = [str(rid) for rid in run_ids]
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(1, int(timeout_seconds))
    terminal = {"completed", "failed", "cancelled", "interrupted"}

    while True:
        results: List[Dict[str, Any]] = []
        pending: List[str] = []
        for rid in wanted:
            status = await _run_status(rid)
            if status is None:
                results.append({"run_id": rid, "status": "unknown", "output": None})
                continue
            results.append(
                {
                    "run_id": rid,
                    "session_id": status.get("session_id"),
                    "agent_id": status.get("agent_id"),
                    "status": status.get("status"),
                    "output": status.get("output"),
                    "error": status.get("error"),
                }
            )
            if status.get("status") not in terminal:
                pending.append(rid)

        if not pending:
            return {"success": True, "status": "completed", "results": results, "pending": []}
        if loop.time() >= deadline:
            return {
                "success": False,
                "status": "timeout",
                "results": results,
                "pending": pending,
                "hint": "the runs are still executing; poll again or cancel them",
            }
        await asyncio.sleep(0.5)


async def cancel_agent_run(run_id: str, cascade: bool = True) -> Dict[str, Any]:
    """Stop a running agent, optionally including the runs it spawned.

    Args:
        run_id: The run to cancel (from spawn_agents/list_active_runs).
        cascade: Also cancel runs started by that run.

    Returns:
        A dict with 'success', 'status' and 'cancelled_children'.
    """
    manager = get_run_manager()
    result = await manager.cancel_run(run_id, cascade=bool(cascade), reason="cancelled by agent")
    return result


ORCHESTRATION_TOOLS = [
    send_message_to_agent,
    list_agent_sessions,
    list_active_runs,
    spawn_agents,
    await_agents,
    cancel_agent_run,
]
