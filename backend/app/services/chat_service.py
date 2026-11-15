"""
Shared agent execution core.

This module owns two things:

1. The ADK runner registry. Runners are built once per agent id and share a
   *persistent* ``DatabaseSessionService`` so a conversation keeps its memory
   across process restarts. The ADK session key is ``<session_id>::<agent_id>``
   which preserves the previous per-agent isolation (one runner per agent) while
   making it durable.
2. :meth:`ChatService.run_turn`, which drives one ``runner.run_async`` call and
   publishes every event through :class:`~app.services.run_manager.RunManager`
   instead of yielding them to an HTTP response.

ADK's session store lives in its **own** database (``ADK_SESSION_DB_URL``):
ADK's schema declares a ``sessions`` table that collides with this app's own
``sessions`` table.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.ids import parse_uuid_or_derive
from db.connection import async_session_scope
from db.repository import Repository
from app.schemas.chat import ChatRequest

logger = logging.getLogger("app.services.chat")

ADK_APP_NAME = "agents_app"
ADK_USER_ID = "default_user"

_agents_map: Dict[str, Any] = {}
_runners_map: Dict[str, Any] = {}
_adk_session_service: Any = None
_registry_lock: Optional[asyncio.Lock] = None
_runner_factory: Optional[Any] = None


def tool_event_detail(value: Any, limit: Optional[int] = None) -> Optional[str]:
    """Renders tool arguments/outputs into a bounded, JSON-safe string.

    The steps panel shows one line per agent action, so it needs to know *what*
    is being executed ("run_command: git status") rather than just the tool name.
    Tool arguments can be large file contents or deep dicts, so this coerces to a
    string and truncates before the value enters the run's event buffer.
    """
    if value is None:
        return None
    if isinstance(value, str):
        text = value
    elif isinstance(value, (dict, list, tuple)):
        # Prefer a compact single-line rendering; the full shape is rarely useful
        # in a one-line step and multiline JSON would break the panel's layout.
        try:
            import json

            text = json.dumps(value, default=str, ensure_ascii=False)
        except Exception:  # pragma: no cover - defensive
            text = str(value)
    else:
        text = str(value)

    text = " ".join(text.split())
    if not text:
        return None
    cap = limit if limit is not None else settings.TOOL_STREAM_DETAIL_CHARS
    if cap > 0 and len(text) > cap:
        return text[: cap - 1] + "…"
    return text


def parse_final_response(raw_text: str) -> Tuple[str, str]:
    """Separates clean final answer from internal thought/reasoning logs."""
    if not raw_text:
        return "", ""

    import re

    # Check for <think>...</think> or <thought>...</thought> tags
    think_blocks = re.findall(r"<(?:think|thought)>([\s\S]*?)</(?:think|thought)>", raw_text, flags=re.IGNORECASE)
    cleaned = re.sub(r"<(?:think|thought)>[\s\S]*?</(?:think|thought)>", "", raw_text, flags=re.IGNORECASE).strip()
    thought_from_tags = "\n\n".join(b.strip() for b in think_blocks if b.strip())

    if "<DONE>" in cleaned:
        parts = cleaned.split("<DONE>")
        thought = "<DONE>".join(parts[:-1]).strip()
        ans = parts[-1].replace("</DONE>", "").strip()
        if not ans and len(parts) >= 2:
            ans = parts[-2].replace("</DONE>", "").strip()
        if ans:
            combined = (thought_from_tags + "\n\n" + thought).strip() if thought_from_tags else thought
            return ans, combined

    if "**Description:**" in cleaned:
        idx = cleaned.find("**Description:**")
        ans = cleaned[idx:].replace("<DONE>", "").replace("</DONE>", "").strip()
        thought = cleaned[:idx].strip()
        combined = (thought_from_tags + "\n\n" + thought).strip() if thought_from_tags else thought
        return ans, combined
    if "Description:" in cleaned:
        idx = cleaned.find("Description:")
        ans = cleaned[idx:].replace("<DONE>", "").replace("</DONE>", "").strip()
        thought = cleaned[:idx].strip()
        combined = (thought_from_tags + "\n\n" + thought).strip() if thought_from_tags else thought
        return ans, combined

    return cleaned, thought_from_tags


def get_agents() -> Dict[str, Any]:
    """Lazily imports the code-defined agents (mirrors the previous behavior)."""
    global _agents_map
    if not _agents_map:
        try:
            from adk_agents.root_agent.agent import root_agent
            from adk_agents.browser_agent.agent import browser_agent
            from adk_agents.cli_agent.agent import cli_agent
            from adk_agents.scheduler_agent.agent import scheduler_agent
            from adk_agents.job_assist_agent.agent import job_assist_agent
            from adk_agents.firecrawl_agent.agent import firecrawl_agent
            from adk_agents.job_scout_agent.agent import job_scout_agent
            from adk_agents.job_matcher_agent.agent import job_matcher_agent
            from adk_agents.resume_tailor_agent.agent import resume_tailor_agent

            _agents_map = {
                "job_scout_agent": job_scout_agent,
                "job_matcher_agent": job_matcher_agent,
                "resume_tailor_agent": resume_tailor_agent,
                "root_agent": root_agent,
                "browser_agent": browser_agent,
                "cli_agent": cli_agent,
                "scheduler_agent": scheduler_agent,
                "job_assist_agent": job_assist_agent,
                "firecrawl_agent": firecrawl_agent,
            }
        except Exception as e:  # pragma: no cover - environment dependent
            logger.warning("Could not load some agents: %s", e)
    return _agents_map


def get_adk_session_service():
    """Returns the process-wide ADK session service (persistent, dedicated DB)."""
    global _adk_session_service
    if _adk_session_service is None:
        from google.adk.sessions import DatabaseSessionService

        from app.core.config import settings

        _adk_session_service = DatabaseSessionService(db_url=settings.ADK_SESSION_DB_URL)
        logger.info("ADK session service bound to %s", settings.ADK_SESSION_DB_URL)
    return _adk_session_service


def get_runner(agent_id: str):
    """Builds (once per agent) the ADK runner, with persistent sessions."""
    global _runners_map
    if agent_id not in _runners_map:
        agents = get_agents()
        target_agent = agents.get(agent_id) or agents.get("root_agent")
        if not target_agent:
            return None
        from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
        from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
        from google.adk.runners import Runner

        _runners_map[agent_id] = Runner(
            app_name=ADK_APP_NAME,
            agent=target_agent,
            session_service=get_adk_session_service(),
            artifact_service=InMemoryArtifactService(),
            memory_service=InMemoryMemoryService(),
            auto_create_session=True,
        )
    return _runners_map.get(agent_id)


async def get_runner_async(agent_id: str):
    """Serializes lazy runner creation so parallel first requests cannot race."""
    global _registry_lock
    if _runner_factory is not None:
        return _runner_factory(agent_id)
    if agent_id in _runners_map:
        return _runners_map.get(agent_id)
    if _registry_lock is None:
        _registry_lock = asyncio.Lock()
    async with _registry_lock:
        return get_runner(agent_id)


def adk_session_id_for(session_id: str, agent_id: str) -> str:
    """One ADK session per (conversation, agent) so each agent keeps its own thread."""
    return f"{session_id}::{agent_id}"


def reset_runner_cache() -> None:
    """Test hook: drops cached runners (and their session-service handle)."""
    global _agents_map, _runners_map, _adk_session_service, _registry_lock, _runner_factory
    _agents_map = {}
    _runners_map = {}
    _adk_session_service = None
    _registry_lock = None
    _runner_factory = None


def set_runner_factory(factory: Optional[Any]) -> None:
    """Test hook: replaces ADK runner construction with a fake runner factory.

    ``factory(agent_id)`` returns an object exposing
    ``run_async(user_id=..., session_id=..., new_message=...)`` as an async
    generator of ADK-like events, which lets the suite exercise run management,
    cancellation, peer messaging and fan-out without calling an LLM.
    """
    global _runner_factory
    _runner_factory = factory


def register_agent_for_test(agent_id: str, agent: Any) -> None:
    """Test hook: injects a fake agent without importing the real agent tree."""
    _agents_map[agent_id] = agent


def _is_known_agent(agent_id: Optional[str]) -> bool:
    return bool(agent_id) and agent_id in get_agents()


class ChatService:
    """Executes one agent turn and publishes its events."""

    # ───────── request preparation ─────────
    @staticmethod
    async def prepare_turn_context(request: ChatRequest) -> Dict[str, Any]:
        """Ensures the session/user message/artifact links exist.

        Returns the pieces :meth:`RunManager.start_run` needs. Kept separate from
        execution so the run can outlive the request that started it.
        """
        agent_id = request.agent_id or "root_agent"
        session_uuid = parse_uuid_or_derive(request.session_id)
        session_id_str = str(session_uuid)

        async with async_session_scope() as db:
            user, workspace = await Repository.get_or_create_default_identity(db)
            sess = await Repository.get_session(db, session_uuid)
            if not sess:
                sess = await Repository.create_session(
                    db,
                    workspace_id=workspace.id,
                    user_id=user.id,
                    title=request.message[:40] if request.message else "Conversation",
                    primary_agent_id=agent_id,
                    session_id=session_uuid,
                )

            user_msg = await Repository.create_message(
                db,
                session_id=session_uuid,
                role="user",
                content=request.message,
                sender_user_id=user.id,
            )

            attached_context = ""
            if request.artifact_ids:
                attached_items = []
                for a_id in request.artifact_ids:
                    try:
                        art_uuid = parse_uuid_or_derive(a_id)
                        await Repository.link_message_artifact(db, user_msg.id, art_uuid, relation="attachment")
                        art_info = await Repository.get_artifact_with_latest_version(db, art_uuid)
                        if art_info:
                            attached_items.append(f"{art_info['name']} (Garage URI: {art_info['storage_uri']})")
                    except Exception as exc:
                        logger.warning("Failed linking artifact %s: %s", a_id, exc)
                if attached_items:
                    attached_context = (
                        "\n\n[User attached artifact(s) stored in Garage S3: "
                        f"{', '.join(attached_items)}. Retrieve content via read_from_garage tool if needed.]"
                    )

            workspace_id = workspace.id

        return {
            "agent_id": agent_id,
            "session_uuid": session_uuid,
            "session_id_str": session_id_str,
            "workspace_id": workspace_id,
            "trigger_message_id": user_msg.id,
            "prompt": (request.message or "") + attached_context,
        }

    # ───────── execution ─────────
    @staticmethod
    async def run_turn(handle, manager) -> None:
        """Runs one agent turn, publishing events and persisting the trace."""
        runner = await get_runner_async(handle.agent_id)
        session_id_str = str(handle.session_id)
        adk_session_id = adk_session_id_for(session_id_str, handle.agent_id)

        if not runner:
            text = f"Agent {handle.agent_id} ready."
            handle.final_output = text
            manager.publish(handle.run_id, {"type": "chunk", "text": text})
            manager.publish(
                handle.run_id,
                {
                    "type": "done",
                    "final_output": text,
                    "thought_process": "",
                    "raw_text": text,
                    "run_id": str(handle.run_id),
                },
            )
            return

        accumulated_full_text = ""
        accumulated_thought = ""
        current_active_agent = handle.agent_id
        active_run_id = handle.run_id
        child_run_ids: List[uuid.UUID] = []
        tool_call_map: Dict[str, uuid.UUID] = {}
        open_tool_calls: List[uuid.UUID] = []

        try:
            from google.genai import types

            user_content = types.Content(
                role="user",
                parts=[types.Part.from_text(text=handle.prompt)],
            )

            async for event in runner.run_async(
                user_id=ADK_USER_ID,
                session_id=adk_session_id,
                new_message=user_content,
            ):
                # 1. Author/Agent switch -> child AgentRun in the trace tree
                event_author = getattr(event, "author", None)
                if event_author and event_author != current_active_agent:
                    previous_agent = current_active_agent
                    current_active_agent = str(event_author)
                    async with async_session_scope() as db:
                        child_run = await Repository.create_agent_run(
                            db,
                            agent_id=current_active_agent,
                            session_id=handle.session_id,
                            parent_run_id=handle.run_id,
                            status="running",
                            origin="delegated",
                        )
                        child_run_ids.append(child_run.id)
                        active_run_id = child_run.id
                    manager.publish(
                        handle.run_id,
                        {
                            "type": "agent_transfer",
                            "from_agent": previous_agent,
                            "to_agent": current_active_agent,
                            "run_id": str(handle.run_id),
                        },
                    )

                # 2. Tool calls
                fn_calls = event.get_function_calls() if hasattr(event, "get_function_calls") else []
                for fc in fn_calls:
                    fn_name = getattr(fc, "name", "tool")
                    fn_args = getattr(fc, "args", {})
                    if "transfer" in fn_name.lower():
                        target = fn_args.get("agent_name") or fn_name
                        manager.publish(
                            handle.run_id,
                            {
                                "type": "agent_transfer",
                                "to_agent": str(target),
                                "tool": fn_name,
                                "run_id": str(handle.run_id),
                            },
                        )
                    else:
                        async with async_session_scope() as db:
                            tc = await Repository.create_tool_call(
                                db,
                                run_id=active_run_id,
                                tool_name=fn_name,
                                status="running",
                                input_args=fn_args if isinstance(fn_args, dict) else {},
                            )
                            tool_call_map[fn_name] = tc.id
                            open_tool_calls.append(tc.id)
                        manager.publish(
                            handle.run_id,
                            {
                                "type": "tool_call",
                                "tool": fn_name,
                                "status": "running",
                                # `args` is what lets the steps panel render one
                                # readable line ("run_command: git status").
                                "args": fn_args if isinstance(fn_args, dict) else {},
                                "detail": tool_event_detail(fn_args),
                                "run_id": str(handle.run_id),
                            },
                        )

                # 3. Tool results
                fn_responses = event.get_function_responses() if hasattr(event, "get_function_responses") else []
                for fr in fn_responses:
                    fn_name = getattr(fr, "name", "tool")
                    fn_response_data = getattr(fr, "response", {})
                    async with async_session_scope() as db:
                        tc_id = tool_call_map.get(fn_name)
                        if tc_id:
                            await Repository.update_tool_call(
                                db,
                                tool_call_id=tc_id,
                                status="completed",
                                output=str(fn_response_data)[:1000] if fn_response_data else None,
                            )
                            if tc_id in open_tool_calls:
                                open_tool_calls.remove(tc_id)
                    manager.publish(
                        handle.run_id,
                        {
                            "type": "tool_result",
                            "tool": fn_name,
                            "status": "completed",
                            "output": tool_event_detail(fn_response_data),
                            "run_id": str(handle.run_id),
                        },
                    )

                # 4. Content chunks
                text_piece = ""
                thought_piece = ""
                if hasattr(event, "content") and event.content:
                    for part in getattr(event.content, "parts", []):
                        is_thought = getattr(part, "thought", False)
                        p_text = getattr(part, "text", "") or ""
                        if p_text:
                            if is_thought:
                                thought_piece += p_text
                            else:
                                text_piece += p_text
                elif hasattr(event, "text") and event.text:
                    text_piece += event.text

                if thought_piece:
                    accumulated_thought += thought_piece
                    manager.publish(handle.run_id, {"type": "thought", "text": thought_piece})

                if text_piece:
                    accumulated_full_text += text_piece
                    manager.publish(handle.run_id, {"type": "chunk", "text": text_piece})

        except asyncio.CancelledError:
            # Persist partial output from a detached task: this task is being
            # cancelled, so awaiting here could be interrupted mid-write.
            # ``RunManager.cancel_run`` awaits this handle before returning.
            handle.persist_task = asyncio.ensure_future(
                ChatService._persist_turn_result(
                    handle,
                    accumulated_full_text,
                    current_active_agent,
                    child_run_ids,
                    open_tool_calls,
                    cancelled=True,
                )
            )
            raise
        except Exception as e:
            logger.error("Stream exception for run %s: %s", handle.run_id, e)
            handle.error = str(e)
            if not accumulated_full_text:
                accumulated_full_text = f"Notice: {str(e)}"
            await ChatService._persist_turn_result(
                handle,
                accumulated_full_text,
                current_active_agent,
                child_run_ids,
                open_tool_calls,
                failed=True,
            )
            manager.publish(
                handle.run_id,
                {"type": "error", "run_id": str(handle.run_id), "error": str(e)},
            )
            final_ans, thought = parse_final_response(accumulated_full_text)
            combined_thought = (accumulated_thought + ("\n\n" + thought if thought else "")).strip()
            handle.final_output = final_ans or accumulated_full_text or combined_thought
            # A ``done`` frame keeps the client contract (``start`` ... ``done``)
            # and carries the error text the user should see; the run row itself
            # is marked failed by the run manager.
            manager.publish(
                handle.run_id,
                {
                    "type": "done",
                    "final_output": handle.final_output,
                    "thought_process": combined_thought,
                    "raw_text": accumulated_full_text,
                    "run_id": str(handle.run_id),
                    "failed": True,
                },
            )
            return

        final_ans, extracted_thought = parse_final_response(accumulated_full_text)
        combined_thought = (accumulated_thought + ("\n\n" + extracted_thought if extracted_thought else "")).strip()
        clean_output = final_ans or accumulated_full_text or combined_thought
        handle.final_output = clean_output
        await ChatService._persist_turn_result(
            handle,
            clean_output,
            current_active_agent,
            child_run_ids,
            open_tool_calls,
        )
        manager.publish(
            handle.run_id,
            {
                "type": "done",
                "final_output": clean_output,
                "thought_process": combined_thought,
                "raw_text": (combined_thought + "\n\n" + clean_output).strip() if combined_thought else clean_output,
                "run_id": str(handle.run_id),
            },
        )

    # ───────── persistence ─────────
    @staticmethod
    async def _persist_turn_result(
        handle,
        accumulated_full_text: str,
        final_agent: str,
        child_run_ids: List[uuid.UUID],
        open_tool_calls: List[uuid.UUID],
        cancelled: bool = False,
        failed: bool = False,
    ) -> None:
        """Persists the assistant message and closes the child trace rows."""
        final_ans, thought = parse_final_response(accumulated_full_text)

        metadata: Dict[str, Any] = {}
        if thought:
            metadata["thought_process"] = thought
        if accumulated_full_text:
            metadata["raw_text"] = accumulated_full_text
        if cancelled:
            metadata["cancelled"] = True
        if failed:
            metadata["failed"] = True

        content = final_ans or accumulated_full_text
        if not content:
            content = "(run stopped by user)" if cancelled else "(no output)"
        handle.final_output = final_ans or accumulated_full_text or handle.final_output

        async with async_session_scope() as db:
            sender_agent_id = final_agent if _is_known_agent(final_agent) else None
            await Repository.create_message(
                db,
                session_id=handle.session_id,
                role="assistant",
                content=content,
                sender_agent_id=sender_agent_id,
                run_id=handle.run_id,
                metadata=metadata,
            )

            child_status = "cancelled" if cancelled else ("failed" if failed else "completed")
            for child_id in child_run_ids:
                await Repository.update_agent_run(db, child_id, status=child_status)

            for tc_id in list(open_tool_calls):
                await Repository.update_tool_call(
                    db,
                    tool_call_id=tc_id,
                    status="cancelled" if cancelled else "failed",
                )

    @staticmethod
    async def collect_sync_response(handle, manager) -> Dict[str, Any]:
        """Drains a run's event stream and returns the pieces ``ChatResponse`` needs."""
        final_output = ""
        thought = ""
        tool_calls: List[Tuple[str, str]] = []

        async for evt in manager.subscribe(handle.run_id, cursor=0, emit_attach=False):
            etype = evt.get("type")
            if etype == "tool_call":
                tool_calls.append((evt.get("tool") or "tool", "running"))
            elif etype == "tool_result":
                tool_calls.append((evt.get("tool") or "tool", "completed"))
            elif etype == "done":
                final_output = evt.get("final_output") or ""
                thought = evt.get("thought_process") or ""
            elif etype == "cancelled":
                final_output = final_output or handle.final_output or "(stopped by user)"

        return {
            "response": final_output or handle.final_output or "",
            "thought_process": thought,
            "tool_calls": tool_calls,
        }
