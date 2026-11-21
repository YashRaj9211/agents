"""
Messages API routes for chat history operations.
"""
from typing import Tuple
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import User, Workspace
from app.core.dependencies import get_db_session, get_current_identity
from app.controllers.message_controller import MessageController
from app.schemas.message import MessageCreate, MessageResponse, MessageListResponse
from app.schemas.common import StatusResponse

router = APIRouter(tags=["Messages"])


@router.get("/sessions/{session_id}/messages", response_model=MessageListResponse)
async def list_session_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    return await MessageController.list_messages(db, session_id)


@router.post(
    "/sessions/{session_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session_message(
    session_id: str,
    payload: MessageCreate,
    db: AsyncSession = Depends(get_db_session),
    identity: Tuple[User, Workspace] = Depends(get_current_identity),
):
    user, _ = identity
    return await MessageController.create_message(db, session_id, user.id, payload)


@router.delete("/sessions/{session_id}/messages", response_model=StatusResponse)
async def clear_session_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    count = await MessageController.clear_session_messages(db, session_id)
    return StatusResponse(
        status="success", message=f"Cleared {count} messages from session '{session_id}'"
    )


@router.delete("/messages/{message_id}", response_model=StatusResponse)
async def delete_message(
    message_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    await MessageController.delete_message(db, message_id)
    return StatusResponse(
        status="success", message=f"Message '{message_id}' deleted"
    )
