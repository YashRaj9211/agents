"""
Message Controller handling message sequences, persistence, and deletions.
"""
import uuid
from typing import List
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from db.repository import Repository
from app.schemas.message import MessageCreate, MessageResponse, MessageListResponse
from app.controllers.agent_controller import parse_uuid_or_derive


class MessageController:
    @staticmethod
    async def list_messages(db: AsyncSession, session_id: str) -> MessageListResponse:
        """Lists strictly sequenced messages for a session."""
        s_uuid = parse_uuid_or_derive(session_id)
        sess = await Repository.get_session(db, s_uuid)
        if not sess:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{session_id}' not found",
            )
        messages = await Repository.list_session_messages(db, s_uuid)
        items = [
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
        ]
        return MessageListResponse(
            session_id=str(s_uuid),
            total=len(items),
            messages=items,
        )

    @staticmethod
    async def create_message(
        db: AsyncSession,
        session_id: str,
        user_id: uuid.UUID,
        payload: MessageCreate,
    ) -> MessageResponse:
        """Inserts a new message into a session."""
        s_uuid = parse_uuid_or_derive(session_id)
        sess = await Repository.get_session(db, s_uuid)
        if not sess:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{session_id}' not found",
            )
        msg = await Repository.create_message(
            db,
            session_id=s_uuid,
            role=payload.role,
            content=payload.content,
            sender_user_id=user_id if payload.role == "user" else None,
            sender_agent_id=payload.sender_agent_id if payload.role != "user" else None,
            metadata=payload.metadata,
        )
        return MessageResponse(
            id=str(msg.id),
            seq=msg.seq,
            role=msg.role,
            content=msg.content,
            sender_agent_id=msg.sender_agent_id,
            metadata=msg.metadata_ or {},
            created_at=msg.created_at.isoformat(),
        )

    @staticmethod
    async def delete_message(db: AsyncSession, message_id: str) -> bool:
        """Deletes a single message."""
        m_uuid = parse_uuid_or_derive(message_id)
        deleted = await Repository.delete_message(db, m_uuid)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Message '{message_id}' not found",
            )
        return True

    @staticmethod
    async def clear_session_messages(db: AsyncSession, session_id: str) -> int:
        """Clears all messages within a session."""
        s_uuid = parse_uuid_or_derive(session_id)
        sess = await Repository.get_session(db, s_uuid)
        if not sess:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{session_id}' not found",
            )
        return await Repository.clear_session_messages(db, s_uuid)
