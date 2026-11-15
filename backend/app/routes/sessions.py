"""
Sessions API routes for conversation thread CRUD operations.
"""
from typing import List, Tuple
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import User, Workspace
from app.core.dependencies import get_db_session, get_current_identity
from app.controllers.session_controller import SessionController
from app.schemas.session import (
    SessionCreate,
    SessionUpdate,
    SessionResponse,
    SessionDetailResponse,
)
from app.schemas.common import StatusResponse

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.get("", response_model=List[SessionResponse])
async def list_sessions(
    db: AsyncSession = Depends(get_db_session),
    identity: Tuple[User, Workspace] = Depends(get_current_identity),
):
    user, _ = identity
    return await SessionController.list_sessions(db, user.id)


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: SessionCreate,
    db: AsyncSession = Depends(get_db_session),
    identity: Tuple[User, Workspace] = Depends(get_current_identity),
):
    user, workspace = identity
    return await SessionController.create_session(db, user.id, workspace.id, payload)


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session_details(
    session_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    return await SessionController.get_session_details(db, session_id)


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    payload: SessionUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    return await SessionController.update_session(db, session_id, payload)


@router.delete("/{session_id}", response_model=StatusResponse)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    await SessionController.delete_session(db, session_id)
    return StatusResponse(status="success", message=f"Session '{session_id}' deleted")
