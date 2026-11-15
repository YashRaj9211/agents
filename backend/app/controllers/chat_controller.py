"""
Chat controller: the request-lifecycle adapter over the run manager.

This module no longer executes agents. It prepares the conversation rows, asks
:class:`~app.services.run_manager.RunManager` to start (or find) a background
run, and then relays that run's events as SSE. Because execution lives in the
manager, closing the browser connection leaves the run running -- which is what
makes session switching and stopping possible.
"""
from __future__ import annotations

import json
import logging
from typing import AsyncGenerator, Dict

from app.schemas.chat import ChatRequest, ChatResponse, ToolCallRecord
from app.services.chat_service import (
    ChatService,
    get_agents,
    get_runner,
    parse_final_response,
    reset_runner_cache,
)
from app.services.run_manager import (
    RunBusyError,
    RunCapacityError,
    get_run_manager,
)

logger = logging.getLogger("app.controller.chat")

__all__ = [
    "ChatController",
    "get_agents",
    "get_runner",
    "parse_final_response",
    "reset_runner_cache",
]


def sse(payload: Dict) -> str:
    """Formats one Server-Sent Events frame."""
    return f"data: {json.dumps(payload)}\n\n"


class ChatController:
    @staticmethod
    async def stream_chat(request: ChatRequest) -> AsyncGenerator[str, None]:
        """Starts a run and relays its events.

        The run itself is owned by the run manager, so cancelling this generator
        (client disconnect, session switch, tab close) detaches the viewer without
        aborting the agent.
        """
        manager = get_run_manager()

        try:
            ctx = await ChatService.prepare_turn_context(request)
        except Exception as exc:
            logger.error("Could not prepare turn context: %s", exc, exc_info=True)
            yield sse({"type": "error", "error": str(exc)})
            yield sse(
                {
                    "type": "done",
                    "final_output": f"Notice: {exc}",
                    "thought_process": "",
                    "raw_text": "",
                }
            )
            return

        try:
            handle = await manager.start_run(
                session_uuid=ctx["session_uuid"],
                agent_id=ctx["agent_id"],
                prompt=ctx["prompt"],
                trigger_message_id=ctx["trigger_message_id"],
                origin="user",
                workspace_id=ctx["workspace_id"],
            )
        except RunBusyError as exc:
            active = manager.active_run_id_for_session(ctx["session_uuid"])
            message = (
                "This session already has a running agent. Attach to the running "
                "run or stop it before sending another message."
            )
            yield sse(
                {
                    "type": "error",
                    "error": "session_busy",
                    "session_id": ctx["session_id_str"],
                    "run_id": active,
                    "message": message,
                }
            )
            # A ``done`` frame keeps every client's "thinking" state consistent.
            yield sse(
                {
                    "type": "done",
                    "final_output": message,
                    "thought_process": "",
                    "raw_text": "",
                    "run_id": active,
                    "busy": True,
                }
            )
            return
        except RunCapacityError as exc:
            message = (
                f"Server is at its concurrent run limit ({exc.limit}). "
                "Stop a running agent or retry shortly."
            )
            yield sse({"type": "error", "error": "capacity_exceeded", "message": message})
            yield sse(
                {
                    "type": "done",
                    "final_output": message,
                    "thought_process": "",
                    "raw_text": "",
                    "capacity": True,
                }
            )
            return

        async for event in manager.subscribe(handle.run_id, cursor=0, emit_attach=False):
            yield sse(event)

    @staticmethod
    async def sync_chat(request: ChatRequest) -> ChatResponse:
        """Synchronous execution: starts a managed run and drains it."""
        agent_id = request.agent_id or "root_agent"
        manager = get_run_manager()

        ctx = await ChatService.prepare_turn_context(request)
        session_id_str = ctx["session_id_str"]

        try:
            handle = await manager.start_run(
                session_uuid=ctx["session_uuid"],
                agent_id=ctx["agent_id"],
                prompt=ctx["prompt"],
                trigger_message_id=ctx["trigger_message_id"],
                origin="user",
                workspace_id=ctx["workspace_id"],
            )
        except RunBusyError:
            return ChatResponse(
                response="This session already has a running agent. Stop it or use the streaming endpoint.",
                agent_id=agent_id,
                session_id=session_id_str,
            )
        except RunCapacityError as exc:
            return ChatResponse(
                response=f"Server is at its concurrent run limit ({exc.limit}).",
                agent_id=agent_id,
                session_id=session_id_str,
            )

        result = await ChatService.collect_sync_response(handle, manager)
        return ChatResponse(
            response=result["response"] or f"Task processed by {agent_id}.",
            thought_process=result["thought_process"],
            agent_id=agent_id,
            session_id=session_id_str,
            tool_calls=[
                ToolCallRecord(tool=tool, status=tool_status)
                for tool, tool_status in result["tool_calls"]
            ],
        )
