"""
Human-in-the-loop tool: let an agent ask the user and wait for the answer.

How the blocking works
----------------------
``runner.run_async`` has no suspend/resume hook, so this is an ordinary tool call
that *awaits an asyncio future*:

1. the question is registered in :mod:`app.services.hitl_service`,
2. a ``human_input_request`` event goes onto the run's replayable event buffer,
   which the browser renders as a question card,
3. the tool awaits the future until ``POST /api/hitl/{question_id}/answer``
   resolves it, or ``HITL_TIMEOUT_SECONDS`` elapses.

Awaiting (not sleeping) keeps the event loop free, so heartbeats continue and the
rest of the fleet keeps working while this one run waits on a human.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.hitl_service import HumanInputError, get_hitl_service
from tools.orchestration_tools.orchestration_tools import _caller_identity

try:  # ADK is an optional import at tool-definition time in tests.
    from google.adk.tools.tool_context import ToolContext
except Exception:  # pragma: no cover
    ToolContext = Any  # type: ignore[assignment]

logger = logging.getLogger("tools.hitl")


async def ask_user(
    question: str,
    kind: str = "confirm",
    options: Optional[List[str]] = None,
    tool_context: ToolContext = None,  # type: ignore[assignment]
) -> Dict[str, Any]:
    """Ask the human a question and block until they answer.

    Use this whenever you need the user's decision or information you cannot infer:
    before a destructive or irreversible action, when the request is ambiguous, or
    when a required detail is missing. Do not use it for trivia you can look up.

    Args:
        question: The question to display, phrased so it can be answered directly.
        kind: One of "confirm" (yes/no), "choice" (pick one option),
            "multi_choice" (pick several), or "text" (free-form answer).
        options: The selectable answers, required for "choice"/"multi_choice" and
            ignored otherwise.

    Returns:
        A dict with ``status`` ("answered" | "timeout" | "no_route"), the rendered
        ``answer``, and a ``message`` restating the decision for the next step.
    """
    identity = _caller_identity(tool_context)
    if not identity:
        logger.warning("ask_user called without a resolvable ADK session context")
        return {
            "status": "no_route",
            "answer": "",
            "message": (
                "Could not identify the conversation to ask in. Proceed using your "
                "best judgement and state the assumption you made."
            ),
        }

    session_uuid = identity["session_uuid"]
    agent_id = identity.get("agent_id") or "root_agent"

    # A run is the unit the UI streams and the unit an answer resolves. Sessions
    # are single-flight (RunManager rejects a second concurrent run), so the
    # session's active run is unambiguously the one asking.
    from app.services.run_manager import get_run_manager

    handle = get_run_manager().active_run_id_for_session(session_uuid)
    run_id = str(handle) if handle else None
    if not run_id:
        logger.warning("ask_user found no active run for session %s", session_uuid)
        return {
            "status": "no_route",
            "answer": "",
            "message": (
                "There is no active run to route this question through. Proceed "
                "using your best judgement and state the assumption you made."
            ),
        }

    service = get_hitl_service()
    try:
        record = service.create_request(
            session_id=str(session_uuid),
            question=question,
            kind=kind,
            options=options,
            run_id=run_id,
            agent_id=agent_id,
        )
    except HumanInputError as exc:
        logger.warning("ask_user could not open a question: %s", exc)
        return {"status": "invalid_request", "answer": "", "message": str(exc)}

    # Publish before awaiting: the browser must see the card while the future is
    # still unresolved. The run buffer replays this to late subscribers too.
    get_run_manager().publish(
        run_id,
        {
            "type": "human_input_request",
            "question_id": record.question_id,
            "kind": record.kind,
            "question": record.question,
            "options": record.options,
            "agent_id": agent_id,
            "run_id": run_id,
        },
    )

    timeout = float(settings.HITL_TIMEOUT_SECONDS or 0)
    try:
        result = await asyncio.wait_for(record.future, timeout=timeout if timeout > 0 else None)
    except asyncio.TimeoutError:
        service.expire(record.question_id, reason="timeout")
        logger.info("HITL question %s timed out after %ss", record.question_id, timeout)
        return {
            "status": "timeout",
            "answer": "",
            "message": (
                f"No answer was received within {int(timeout)}s. Report that you are "
                "blocked on this question instead of guessing."
            ),
        }
    except asyncio.CancelledError:
        # The operator stopped the run (or the session was cancelled). Let the
        # cancellation propagate so the run manager can finish cleanly; the
        # registry entry is closed by HumanInputService.fail_all.
        service.expire(record.question_id, reason="cancelled")
        raise

    status = str(result.get("status") or "answered")
    answer = str(result.get("answer") or "")

    if status == "answered":
        if record.kind == "confirm":
            message = (
                "The user answered Yes; proceed with the action you asked about."
                if answer.lower() == "yes"
                else "The user answered No; do not perform that action and offer an alternative."
            )
        else:
            message = f"The user answered: {answer}"
    else:
        message = f"The question closed without an answer ({status}). Do not assume an answer."

    return {
        "status": status,
        "question": record.question,
        "kind": record.kind,
        "answer": answer,
        "message": message,
    }
