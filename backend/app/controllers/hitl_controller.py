"""
HITL controller: implements the answer side of an agent's question.

The asking side is the ``ask_user`` tool, which blocks on a future held by
:mod:`app.services.hitl_service`. Answering resolves that future, so the run
resumes inside its own task -- this controller never starts a run or writes a
message.
"""
from __future__ import annotations

from fastapi import HTTPException, status

from app.schemas.hitl import HumanInputAnswerResponse, PendingHumanInputResponse
from app.services.hitl_service import (
    HumanInputError,
    get_hitl_service,
)


class HitlController:
    @staticmethod
    def list_pending(session_id: str) -> PendingHumanInputResponse:
        """Questions a session is still waiting on (used to rehydrate a reloaded page)."""
        service = get_hitl_service()
        pending = service.pending_for_session(session_id)
        return PendingHumanInputResponse(
            session_id=session_id,
            total=len(pending),
            questions=[p.summary() for p in pending],
        )

    @staticmethod
    def answer(question_id: str, raw_answer) -> HumanInputAnswerResponse:
        """Resolves a pending question, unblocking the agent that asked it."""
        service = get_hitl_service()
        record = service.get(question_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"Question '{question_id}' is not pending. It was already "
                    "answered, timed out, or belonged to a previous server process."
                ),
            )

        try:
            resolved = service.resolve(question_id, raw_answer)
        except HumanInputError as exc:
            # 409: the question exists but this answer is not acceptable for it.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc

        rendered = None
        if resolved.future is not None and resolved.future.done():
            result = resolved.future.result()
            rendered = result.get("answer") if isinstance(result, dict) else None

        return HumanInputAnswerResponse(
            status="answered",
            question_id=question_id,
            answered=True,
            answer=rendered,
            message="The agent has resumed with your answer.",
        )
