"""
HITL (human-in-the-loop) routes.

An agent that calls the ``ask_user`` tool blocks until one of these endpoints
resolves its question. See :mod:`app.services.hitl_service` for the mechanics.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.controllers.hitl_controller import HitlController
from app.schemas.hitl import HumanInputAnswer, HumanInputAnswerResponse, PendingHumanInputResponse

router = APIRouter(tags=["Human in the loop"])


@router.get(
    "/sessions/{session_id}/hitl/pending",
    response_model=PendingHumanInputResponse,
)
async def list_pending_questions(session_id: str):
    """Outstanding questions for a session, so the UI can re-render its card."""
    return HitlController.list_pending(session_id)


@router.post(
    "/hitl/{question_id}/answer",
    response_model=HumanInputAnswerResponse,
)
async def answer_question(question_id: str, payload: HumanInputAnswer):
    """Answers a question and unblocks the run that asked it."""
    return HitlController.answer(question_id, payload.answer)
