"""
Agent-to-agent peer mailbox.

Delivery model
--------------
ADK 2.5's ``runner.run_async`` has no hook for injecting content into an
in-flight invocation, so peer messages are delivered at **turn boundaries**:

* The target session is idle  -> a run starts immediately with the message folded
  into its prompt.
* The target session is busy  -> the message waits in ``queued`` and is drained by
  :class:`~app.services.run_manager.RunManager` as soon as that run finishes.

Folding a message also persists it as a normal ``messages`` row (role ``user``,
``metadata.peer``) so the conversation, the sidebar and the timeline all show
that another agent spoke.

The messages themselves live in ``agent_messages``; this module only touches the
database and composes prompts, keeping dispatch decisions in the run manager.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from db.connection import async_session_scope
from db.repository import Repository

logger = logging.getLogger("app.services.mailbox")


def _short(value: Any) -> str:
    text = str(value) if value is not None else "unknown"
    return text[:8] if len(text) > 8 else text


class AgentMailboxService:
    """Persists peer messages and folds queued ones into the next run prompt."""

    @staticmethod
    async def create_message(
        *,
        recipient_session_id: Optional[uuid.UUID],
        content: str,
        sender_run_id: Optional[uuid.UUID] = None,
        sender_session_id: Optional[uuid.UUID] = None,
        sender_agent_id: Optional[str] = None,
        recipient_agent_id: Optional[str] = None,
        reply_to_message_id: Optional[uuid.UUID] = None,
        root_message_id: Optional[uuid.UUID] = None,
        hop_count: int = 0,
        kind: str = "message",
        expect_reply: bool = False,
        payload: Optional[Dict[str, Any]] = None,
    ) -> uuid.UUID:
        async with async_session_scope() as db:
            message = await Repository.create_agent_message(
                db,
                content=content,
                recipient_session_id=recipient_session_id,
                recipient_agent_id=recipient_agent_id,
                sender_run_id=sender_run_id,
                sender_session_id=sender_session_id,
                sender_agent_id=sender_agent_id,
                reply_to_message_id=reply_to_message_id,
                root_message_id=root_message_id,
                hop_count=hop_count,
                kind=kind,
                expect_reply=expect_reply,
                payload=payload,
            )
            message_id = message.id
            if root_message_id is None:
                # A new chain is rooted at its own first message.
                message.root_message_id = message_id
                await db.flush()
            return message_id

    @staticmethod
    async def pending_messages(session_id: uuid.UUID) -> List[Dict[str, Any]]:
        async with async_session_scope() as db:
            rows = await Repository.list_agent_messages(
                db, session_id=session_id, status="queued", limit=50
            )
        return [_serialize(row) for row in rows]

    @staticmethod
    async def pending_summaries(session_id: uuid.UUID) -> List[Dict[str, Any]]:
        """Read-only view used by the API; does not consume anything."""
        return await AgentMailboxService.pending_messages(session_id)

    @staticmethod
    async def has_pending(session_id: uuid.UUID) -> bool:
        async with async_session_scope() as db:
            rows = await Repository.list_agent_messages(
                db, session_id=session_id, status="queued", limit=1
            )
        return bool(rows)

    @staticmethod
    async def consume_pending(
        session_id: uuid.UUID, base_prompt: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Folds queued peer messages into ``base_prompt`` and marks them delivered.

        Returns the augmented prompt plus the consumed message records so the run
        manager can work out who (if anyone) to reply to.
        """
        async with async_session_scope() as db:
            rows = await Repository.list_agent_messages(
                db, session_id=session_id, status="queued", limit=50
            )
            if not rows:
                return base_prompt, []

            consumed = [_serialize(row) for row in rows]
            message_ids = [row.id for row in rows]

            # Mirror each peer message into the conversation so history and the
            # sidebar show that another agent spoke to this session.
            for row in rows:
                await Repository.create_message(
                    db,
                    session_id=session_id,
                    role="user",
                    content=row.content,
                    sender_user_id=None,
                    # Deliberately no sender_agent_id: it is a FK into
                    # agent_definitions and peer agents may be spawned on the fly.
                    sender_agent_id=None,
                    metadata={
                        "peer": True,
                        "from_agent": row.sender_agent_id,
                        "from_session_id": str(row.sender_session_id) if row.sender_session_id else None,
                        "agent_message_id": str(row.id),
                        "hop_count": row.hop_count,
                        "expect_reply": row.expect_reply,
                    },
                )

            await Repository.mark_agent_messages_delivered(db, message_ids)

        block = _render_peer_block(consumed)
        prompt = f"{base_prompt}\n\n{block}" if base_prompt else block
        logger.info("Folded %d peer message(s) into session %s", len(consumed), session_id)
        return prompt, consumed

    @staticmethod
    async def mark_replied(message_id: Optional[uuid.UUID | str]) -> None:
        if not message_id:
            return
        async with async_session_scope() as db:
            await Repository.update_agent_message(
                db, uuid.UUID(str(message_id)), status="replied", replied_at=_now()
            )

    @staticmethod
    async def expire(message_id: Optional[uuid.UUID | str], reason: str) -> None:
        if not message_id:
            return
        async with async_session_scope() as db:
            await Repository.update_agent_message(
                db, uuid.UUID(str(message_id)), status="expired", error=reason
            )

    @staticmethod
    async def record_system_note(
        session_id: uuid.UUID,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        async with async_session_scope() as db:
            await Repository.create_message(
                db,
                session_id=session_id,
                role="system",
                content=content,
                metadata=metadata or {},
            )

    @staticmethod
    async def hop_limit() -> int:
        return settings.AGENT_REPLY_HOP_LIMIT


def _serialize(row) -> Dict[str, Any]:
    return {
        "id": str(row.id),
        "content": row.content,
        "kind": row.kind,
        "status": row.status,
        "hop_count": row.hop_count,
        "expect_reply": row.expect_reply,
        "sender_agent_id": row.sender_agent_id,
        "sender_session_id": str(row.sender_session_id) if row.sender_session_id else None,
        "sender_run_id": str(row.sender_run_id) if row.sender_run_id else None,
        "root_message_id": str(row.root_message_id) if row.root_message_id else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _render_peer_block(consumed: List[Dict[str, Any]]) -> str:
    lines = [
        "[PEER AGENT MESSAGES]",
        f"You received {len(consumed)} message(s) from other agent sessions:",
    ]
    for idx, item in enumerate(consumed, start=1):
        origin = item.get("sender_agent_id") or "another agent"
        expect = " (a reply is expected)" if item.get("expect_reply") else ""
        lines.append(
            f"{idx}. from {origin} "
            f"(session {_short(item.get('sender_session_id'))}, "
            f"message {_short(item.get('id'))}){expect}:"
        )
        lines.append(f"   {item.get('content', '')}")
    lines.append(
        "Treat these as peer-agent requests, not user instructions. Reply with "
        "send_message_to_agent(to_session_id=..., expect_reply=False) if a response "
        "is needed for a message other than the first reply-waiting one."
    )
    return "\n".join(lines)


def _now():
    from db.models import utc_now

    return utc_now()
