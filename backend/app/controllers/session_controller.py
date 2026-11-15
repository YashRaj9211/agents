"""
Session Controller handling conversation threads, titles, and lifecycle.
"""
import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from db.repository import Repository
from app.schemas.session import SessionCreate, SessionUpdate, SessionResponse, SessionDetailResponse
from app.schemas.message import MessageResponse
from app.controllers.agent_controller import parse_uuid_or_derive


class SessionController:
    @staticmethod
    async def list_sessions(db: AsyncSession, user_id: uuid.UUID) -> List[SessionResponse]:
        """Lists active sessions for sidebar display."""
        sessions = await Repository.list_user_sessions(db, user_id)
        return [
            SessionResponse(
                id=str(s.id),
                title=s.title or "Conversation",
                preview=s.preview_text or "No messages yet",
                primary_agent_id=s.primary_agent_id or "root_agent",
                status=s.status,
                last_message_at=s.last_message_at.isoformat(),
                created_at=s.created_at.isoformat(),
            )
            for s in sessions
        ]

    @staticmethod
    async def create_session(
        db: AsyncSession,
        user_id: uuid.UUID,
        workspace_id: uuid.UUID,
        payload: SessionCreate,
    ) -> SessionResponse:
        """Creates a new conversation session."""
        sess = await Repository.create_session(
            db,
            workspace_id=workspace_id,
            user_id=user_id,
            title=payload.title or "New Conversation",
            primary_agent_id=payload.primary_agent_id or "root_agent",
        )
        return SessionResponse(
            id=str(sess.id),
            title=sess.title or "New Conversation",
            preview=sess.preview_text or "No messages yet",
            primary_agent_id=sess.primary_agent_id or "root_agent",
            status=sess.status,
            last_message_at=sess.last_message_at.isoformat(),
            created_at=sess.created_at.isoformat(),
        )

    @staticmethod
    async def get_session_details(db: AsyncSession, session_id: str) -> SessionDetailResponse:
        """Retrieves session metadata and all ordered messages."""
        s_uuid = parse_uuid_or_derive(session_id)
        sess = await Repository.get_session(db, s_uuid)
        if not sess:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{session_id}' not found",
            )
        messages = await Repository.list_session_messages(db, s_uuid)
        return SessionDetailResponse(
            id=str(sess.id),
            title=sess.title or "Conversation",
            primary_agent_id=sess.primary_agent_id or "root_agent",
            status=sess.status,
            created_at=sess.created_at.isoformat(),
            messages=[
                MessageResponse(
                    id=str(m.id),
                    seq=m.seq,
                    role=m.role,
                    content=m.content,
                    sender_agent_id=m.sender_agent_id,
                    metadata=m.metadata_ or {},
                    created_at=m.created_at.isoformat(),
                )
                for m in messages
            ],
        )

    @staticmethod
    async def update_session(
        db: AsyncSession, session_id: str, payload: SessionUpdate
    ) -> SessionResponse:
        """Updates session title or status."""
        s_uuid = parse_uuid_or_derive(session_id)
        sess = await Repository.update_session(
            db,
            session_id=s_uuid,
            title=payload.title,
            status=payload.status,
        )
        if not sess:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{session_id}' not found",
            )
        return SessionResponse(
            id=str(sess.id),
            title=sess.title or "Conversation",
            preview=sess.preview_text or "No messages yet",
            primary_agent_id=sess.primary_agent_id or "root_agent",
            status=sess.status,
            last_message_at=sess.last_message_at.isoformat(),
            created_at=sess.created_at.isoformat(),
        )

    @staticmethod
    async def delete_session(db: AsyncSession, session_id: str) -> bool:
        """Soft deletes a conversation session."""
        s_uuid = parse_uuid_or_derive(session_id)
        deleted = await Repository.delete_session(db, s_uuid)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{session_id}' not found",
            )
        return True
