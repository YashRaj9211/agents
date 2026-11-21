"""
Database Repository providing Phase 1 queries, mutations, and orchestration persistence.
Handles:
- Users & Workspaces
- Agent Definitions & Quick Actions synchronization
- Sessions & strictly-sequenced Messages
- Agent Runs & Tool Calls (Execution trace tree)
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import sqlalchemy as sa
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    AgentDefinition,
    AgentInstance,
    AgentMessage,
    AgentRun,
    Artifact,
    ArtifactVersion,
    Message,
    MessageArtifact,
    QuickAction,
    Session,
    ToolCall,
    User,
    Workspace,
    WorkspaceMember,
    generate_uuid,
    utc_now,
)


def _as_uuid(value: Any) -> Any:
    """Coerces a UUID column argument so callers may pass str or UUID.

    Route handlers and agent tools frequently hold string ids (they come straight
    from JSON), while SQLAlchemy's ``Uuid`` columns bind UUID objects; binding a
    string raises ``'str' object has no attribute 'hex'``.
    """
    if value is None or isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return value


class Repository:
    """Async repository for database entities."""

    # ───────── Identity & Setup ─────────
    @staticmethod
    async def get_or_create_default_identity(
        db: AsyncSession,
    ) -> Tuple[User, Workspace]:
        """Ensures a default user and workspace exist for local single-tenant or default operations."""
        stmt = select(User).where(User.handle == "default_user").limit(1)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()

        if not user:
            user = User(
                id=generate_uuid(),
                auth_provider="local",
                auth_subject="default_user",
                handle="default_user",
                full_name="Default Operator",
                avatar_url=None,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            db.add(user)
            await db.flush()

        stmt_ws = select(Workspace).where(Workspace.owner_id == user.id).limit(1)
        res_ws = await db.execute(stmt_ws)
        workspace = res_ws.scalar_one_or_none()

        if not workspace:
            workspace = Workspace(
                id=generate_uuid(),
                name="Default Workspace",
                owner_id=user.id,
                created_at=utc_now(),
            )
            db.add(workspace)
            await db.flush()

            member = WorkspaceMember(
                workspace_id=workspace.id,
                user_id=user.id,
                role="owner",
            )
            db.add(member)
            await db.flush()

        return user, workspace

    # ───────── Catalog Synchronization ─────────
    @staticmethod
    async def sync_agent_definitions(
        db: AsyncSession, agents: List[Dict[str, Any]]
    ) -> None:
        """Upserts code-defined agents into agent_definitions table."""
        for ag in agents:
            agent_id = ag["id"]
            stmt = select(AgentDefinition).where(AgentDefinition.id == agent_id)
            res = await db.execute(stmt)
            existing = res.scalar_one_or_none()

            if existing:
                existing.name = ag.get("name", existing.name)
                existing.description = ag.get("description", existing.description)
                existing.kind = ag.get("kind", existing.kind)
                existing.config = ag.get("config", existing.config)
                existing.is_active = ag.get("is_active", True)
                existing.updated_at = utc_now()
            else:
                new_agent = AgentDefinition(
                    id=agent_id,
                    name=ag.get("name", agent_id),
                    description=ag.get("description", ""),
                    kind=ag.get("kind", "worker"),
                    config=ag.get("config", {}),
                    version=1,
                    is_active=True,
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                db.add(new_agent)
        await db.flush()

    @staticmethod
    async def list_agent_definitions(db: AsyncSession) -> List[AgentDefinition]:
        stmt = select(AgentDefinition).where(AgentDefinition.is_active == True)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def sync_quick_actions(
        db: AsyncSession, actions: List[Dict[str, Any]]
    ) -> None:
        """Upserts quick action prompt templates."""
        for idx, act in enumerate(actions):
            act_id = act["id"]
            stmt = select(QuickAction).where(QuickAction.id == act_id)
            res = await db.execute(stmt)
            existing = res.scalar_one_or_none()

            if existing:
                existing.title = act.get("title", existing.title)
                existing.description = act.get("description", existing.description)
                existing.prompt = act.get("prompt", existing.prompt)
                existing.emoji = act.get("emoji", existing.emoji)
                existing.style = act.get("style", act.get("color_scheme", existing.style))
                existing.target_agent_id = act.get("target_agent_id", existing.target_agent_id)
                existing.sort_order = act.get("sort_order", idx)
            else:
                new_act = QuickAction(
                    id=act_id,
                    title=act.get("title", ""),
                    description=act.get("description", ""),
                    prompt=act.get("prompt", ""),
                    emoji=act.get("emoji", "⚡"),
                    style={"color_scheme": act.get("colorScheme", "blue")},
                    target_agent_id=act.get("target_agent_id"),
                    sort_order=act.get("sort_order", idx),
                    is_active=True,
                )
                db.add(new_act)
        await db.flush()

    @staticmethod
    async def list_quick_actions(db: AsyncSession) -> List[QuickAction]:
        stmt = (
            select(QuickAction)
            .where(QuickAction.is_active == True)
            .order_by(QuickAction.sort_order)
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    # ───────── Conversations: Sessions ─────────
    @staticmethod
    async def create_session(
        db: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        title: Optional[str] = "New Conversation",
        primary_agent_id: Optional[str] = "root_agent",
        session_id: Optional[uuid.UUID] = None,
        status: str = "active",
    ) -> Session:
        sid = session_id or generate_uuid()
        sess = Session(
            id=sid,
            workspace_id=workspace_id,
            user_id=user_id,
            primary_agent_id=primary_agent_id,
            title=title,
            preview_text="Started a new conversation...",
            status=status,
            last_message_at=utc_now(),
            created_at=utc_now(),
        )
        db.add(sess)
        await db.flush()
        return sess

    @staticmethod
    async def get_session(
        db: AsyncSession, session_id: uuid.UUID
    ) -> Optional[Session]:
        stmt = (
            select(Session)
            .where(Session.id == session_id, Session.deleted_at.is_(None))
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_user_sessions(
        db: AsyncSession, user_id: uuid.UUID, limit: int = 50
    ) -> List[Session]:
        # Sessions created by spawn_agents exist only to host a child run; their
        # output is returned to the parent chat, so they never get a sidebar row.
        stmt = (
            select(Session)
            .where(
                Session.user_id == user_id,
                Session.deleted_at.is_(None),
                Session.status != "spawned",
            )
            .order_by(Session.last_message_at.desc())
            .limit(limit)
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def update_session(
        db: AsyncSession,
        session_id: uuid.UUID,
        title: Optional[str] = None,
        preview_text: Optional[str] = None,
        last_message_at: Optional[datetime] = None,
        status: Optional[str] = None,
    ) -> Optional[Session]:
        sess = await Repository.get_session(db, session_id)
        if not sess:
            return None

        if title is not None:
            sess.title = title
        if preview_text is not None:
            sess.preview_text = preview_text
        if last_message_at is not None:
            sess.last_message_at = last_message_at
        if status is not None:
            sess.status = status

        await db.flush()
        return sess

    @staticmethod
    async def delete_session(
        db: AsyncSession, session_id: uuid.UUID
    ) -> bool:
        sess = await Repository.get_session(db, session_id)
        if not sess:
            return False
        sess.deleted_at = utc_now()
        await db.flush()
        return True

    # ───────── Conversations: Messages ─────────
    @staticmethod
    async def create_message(
        db: AsyncSession,
        session_id: uuid.UUID,
        role: str,
        content: str,
        sender_user_id: Optional[uuid.UUID] = None,
        sender_agent_id: Optional[str] = None,
        run_id: Optional[uuid.UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
        max_seq_attempts: int = 5,
    ) -> Message:
        """Appends a message, allocating ``seq = coalesce(max(seq), 0) + 1``.

        The run manager serializes runs *per session*, but a session can still
        receive inserts from two places at once (a finishing run persisting its
        answer while an incoming peer message is folded in, for example). The
        ``(session_id, seq)`` unique constraint turns that overlap into an
        `IntegrityError`, so the allocation is retried inside a SAVEPOINT: the
        loser re-reads the maximum and appends after the winner.
        """
        session_uuid = _as_uuid(session_id)
        preview = (content[:80] + "...") if len(content) > 80 else content

        for attempt in range(max(1, max_seq_attempts)):
            stmt = select(func.coalesce(func.max(Message.seq), 0)).where(
                Message.session_id == session_uuid
            )
            res = await db.execute(stmt)
            next_seq = int(res.scalar() or 0) + 1

            msg = Message(
                id=generate_uuid(),
                session_id=session_uuid,
                seq=next_seq,
                role=role,
                sender_user_id=sender_user_id,
                sender_agent_id=sender_agent_id,
                run_id=run_id,
                content=content,
                metadata_=metadata or {},
                created_at=utc_now(),
            )

            try:
                # SAVEPOINT: a duplicate seq must not poison the caller's
                # transaction, otherwise every later statement would fail too.
                async with db.begin_nested():
                    db.add(msg)
                    await db.flush()
            except IntegrityError:
                if attempt == max_seq_attempts - 1:
                    raise
                await asyncio.sleep(0.02 * (attempt + 1))
                continue

            # Update session timestamp & preview
            await Repository.update_session(
                db,
                session_id=session_uuid,
                preview_text=preview or "Active session",
                last_message_at=utc_now(),
            )
            await db.flush()
            return msg

        raise RuntimeError("unreachable: message sequence allocation exhausted retries")

    @staticmethod
    async def get_message(
        db: AsyncSession, message_id: uuid.UUID
    ) -> Optional[Message]:
        stmt = select(Message).where(Message.id == message_id)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_session_messages(
        db: AsyncSession, session_id: uuid.UUID
    ) -> List[Message]:
        stmt = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.seq.asc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def delete_message(
        db: AsyncSession, message_id: uuid.UUID
    ) -> bool:
        msg = await Repository.get_message(db, message_id)
        if not msg:
            return False
        await db.delete(msg)
        await db.flush()
        return True

    @staticmethod
    async def clear_session_messages(
        db: AsyncSession, session_id: uuid.UUID
    ) -> int:
        stmt = select(Message).where(Message.session_id == session_id)
        res = await db.execute(stmt)
        messages = list(res.scalars().all())
        count = len(messages)
        for m in messages:
            await db.delete(m)
        sess = await Repository.get_session(db, session_id)
        if sess:
            sess.preview_text = "No messages"
        await db.flush()
        return count

    # ───────── Execution Trace: Agent Runs & Tool Calls ─────────
    @staticmethod
    async def create_agent_run(
        db: AsyncSession,
        agent_id: str,
        session_id: Optional[uuid.UUID] = None,
        trigger_message_id: Optional[uuid.UUID] = None,
        parent_run_id: Optional[uuid.UUID] = None,
        status: str = "running",
        instance_id: Optional[uuid.UUID] = None,
        origin: str = "user",
        run_id: Optional[uuid.UUID] = None,
    ) -> AgentRun:
        run = AgentRun(
            id=run_id or generate_uuid(),
            session_id=session_id,
            trigger_message_id=trigger_message_id,
            parent_run_id=parent_run_id,
            agent_id=agent_id,
            instance_id=instance_id,
            status=status,
            # `origin` has no dedicated column, so it rides along in `usage`.
            usage={"origin": origin},
            started_at=utc_now(),
        )
        db.add(run)
        await db.flush()
        return run

    @staticmethod
    async def get_agent_run(
        db: AsyncSession, run_id: uuid.UUID
    ) -> Optional[AgentRun]:
        stmt = select(AgentRun).where(AgentRun.id == _as_uuid(run_id))
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_agent_runs(
        db: AsyncSession,
        status: Optional[str] = None,
        session_id: Optional[uuid.UUID] = None,
        statuses: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[AgentRun]:
        stmt = select(AgentRun)
        if status is not None:
            stmt = stmt.where(AgentRun.status == status)
        if statuses:
            stmt = stmt.where(AgentRun.status.in_(list(statuses)))
        if session_id is not None:
            stmt = stmt.where(AgentRun.session_id == session_id)
        stmt = stmt.order_by(AgentRun.started_at.desc()).limit(limit)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def list_unfinished_descendant_runs(
        db: AsyncSession, root_run_id: uuid.UUID, max_depth: int = 5
    ) -> List[AgentRun]:
        """Returns every not-yet-finished run below `root_run_id` (breadth-first)."""
        finished = {"completed", "failed", "cancelled", "interrupted"}
        frontier = [root_run_id]
        found: List[AgentRun] = []
        for _ in range(max_depth):
            if not frontier:
                break
            stmt = select(AgentRun).where(AgentRun.parent_run_id.in_(frontier))
            res = await db.execute(stmt)
            children = [r for r in res.scalars().all() if r.status not in finished]
            found.extend(children)
            frontier = [r.id for r in children]
        return found

    @staticmethod
    async def reconcile_interrupted_runs(db: AsyncSession) -> int:
        """Closes out runs left `running`/`cancelling` by a previous process.

        ``schema.sql`` constrains ``agent_runs.status`` to
        ``('queued','running','completed','failed','cancelled')``, so an orphaned
        run is recorded as ``failed`` with an explicit error instead of inventing
        a status the deployed database would reject.
        """
        stmt = (
            update(AgentRun)
            .where(AgentRun.status.in_(["running", "cancelling"]))
            .values(
                status="failed",
                error={"detail": "interrupted: the backend restarted while this run was in flight"},
                finished_at=utc_now(),
            )
        )
        res = await db.execute(stmt)
        await db.flush()
        return int(res.rowcount or 0)

    # ───────── Agent Fleet Instances ─────────
    @staticmethod
    async def create_agent_instance(
        db: AsyncSession,
        agent_id: str,
        workspace_id: Optional[uuid.UUID] = None,
        status: str = "running",
        host: Optional[str] = None,
        config_override: Optional[Dict[str, Any]] = None,
    ) -> AgentInstance:
        instance = AgentInstance(
            id=generate_uuid(),
            agent_id=agent_id,
            workspace_id=workspace_id,
            status=status,
            host=host,
            config_override=config_override or {},
            last_heartbeat_at=utc_now(),
            started_at=utc_now(),
        )
        db.add(instance)
        await db.flush()
        return instance

    @staticmethod
    async def update_agent_instance(
        db: AsyncSession,
        instance_id: uuid.UUID,
        status: Optional[str] = None,
        stopped_at: Optional[datetime] = None,
    ) -> Optional[AgentInstance]:
        stmt = select(AgentInstance).where(AgentInstance.id == instance_id)
        res = await db.execute(stmt)
        instance = res.scalar_one_or_none()
        if not instance:
            return None
        if status:
            instance.status = status
        if status in ("idle", "stopped", "failed"):
            instance.stopped_at = stopped_at or utc_now()
        instance.last_heartbeat_at = utc_now()
        await db.flush()
        return instance

    # ───────── Agent Collaboration (peer mailbox) ─────────
    @staticmethod
    async def create_agent_message(
        db: AsyncSession,
        content: str,
        recipient_session_id: Optional[uuid.UUID] = None,
        recipient_agent_id: Optional[str] = None,
        sender_run_id: Optional[uuid.UUID] = None,
        sender_session_id: Optional[uuid.UUID] = None,
        sender_agent_id: Optional[str] = None,
        reply_to_message_id: Optional[uuid.UUID] = None,
        root_message_id: Optional[uuid.UUID] = None,
        hop_count: int = 0,
        kind: str = "message",
        expect_reply: bool = False,
        payload: Optional[Dict[str, Any]] = None,
        status: str = "queued",
    ) -> AgentMessage:
        message = AgentMessage(
            id=generate_uuid(),
            sender_run_id=sender_run_id,
            sender_session_id=sender_session_id,
            sender_agent_id=sender_agent_id,
            recipient_session_id=recipient_session_id,
            recipient_agent_id=recipient_agent_id,
            reply_to_message_id=reply_to_message_id,
            root_message_id=root_message_id,
            hop_count=hop_count,
            kind=kind,
            expect_reply=expect_reply,
            content=content,
            payload=payload or {},
            status=status,
            created_at=utc_now(),
        )
        db.add(message)
        await db.flush()
        return message

    @staticmethod
    async def get_agent_message(
        db: AsyncSession, message_id: uuid.UUID
    ) -> Optional[AgentMessage]:
        stmt = select(AgentMessage).where(AgentMessage.id == _as_uuid(message_id))
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_agent_messages(
        db: AsyncSession,
        session_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[AgentMessage]:
        stmt = select(AgentMessage)
        if session_id is not None:
            stmt = stmt.where(AgentMessage.recipient_session_id == session_id)
        if status is not None:
            stmt = stmt.where(AgentMessage.status == status)
        stmt = stmt.order_by(AgentMessage.created_at.asc()).limit(limit)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def update_agent_message(
        db: AsyncSession,
        message_id: uuid.UUID,
        status: Optional[str] = None,
        delivered_at: Optional[datetime] = None,
        replied_at: Optional[datetime] = None,
        error: Optional[str] = None,
    ) -> Optional[AgentMessage]:
        stmt = select(AgentMessage).where(AgentMessage.id == _as_uuid(message_id))
        res = await db.execute(stmt)
        message = res.scalar_one_or_none()
        if not message:
            return None
        if status:
            message.status = status
        if delivered_at:
            message.delivered_at = delivered_at
        if replied_at:
            message.replied_at = replied_at
        if error is not None:
            message.error = error
        await db.flush()
        return message

    @staticmethod
    async def mark_agent_messages_delivered(
        db: AsyncSession, message_ids: List[uuid.UUID]
    ) -> int:
        if not message_ids:
            return 0
        stmt = (
            update(AgentMessage)
            .where(AgentMessage.id.in_(message_ids))
            .values(status="delivered", delivered_at=utc_now())
        )
        res = await db.execute(stmt)
        await db.flush()
        return int(res.rowcount or 0)


    @staticmethod
    async def update_agent_run(
        db: AsyncSession,
        run_id: uuid.UUID,
        status: Optional[str] = None,
        error: Optional[Dict[str, Any]] = None,
        usage: Optional[Dict[str, Any]] = None,
        finished_at: Optional[datetime] = None,
    ) -> Optional[AgentRun]:
        stmt = select(AgentRun).where(AgentRun.id == run_id)
        res = await db.execute(stmt)
        run = res.scalar_one_or_none()
        if not run:
            return None

        if status:
            run.status = status
        if error:
            run.error = error
        if usage:
            run.usage = usage
        if finished_at or (status in ["completed", "failed", "cancelled"] and not run.finished_at):
            run.finished_at = finished_at or utc_now()

        await db.flush()
        return run

    @staticmethod
    async def create_tool_call(
        db: AsyncSession,
        run_id: uuid.UUID,
        tool_name: str,
        status: str = "running",
        input_args: Optional[Dict[str, Any]] = None,
        message_id: Optional[uuid.UUID] = None,
    ) -> ToolCall:
        tc = ToolCall(
            id=generate_uuid(),
            run_id=run_id,
            message_id=message_id,
            tool_name=tool_name,
            status=status,
            input_args=input_args or {},
            started_at=utc_now(),
        )
        db.add(tc)
        await db.flush()
        return tc

    @staticmethod
    async def update_tool_call(
        db: AsyncSession,
        tool_call_id: uuid.UUID,
        status: Optional[str] = None,
        output: Optional[str] = None,
        error: Optional[str] = None,
        completed_at: Optional[datetime] = None,
    ) -> Optional[ToolCall]:
        stmt = select(ToolCall).where(ToolCall.id == tool_call_id)
        res = await db.execute(stmt)
        tc = res.scalar_one_or_none()
        if not tc:
            return None

        if status:
            tc.status = status
        if output is not None:
            tc.output = output
        if error is not None:
            tc.error = error
        if completed_at or (status in ["completed", "failed"] and not tc.completed_at):
            tc.completed_at = completed_at or utc_now()

        await db.flush()
        return tc

    @staticmethod
    async def get_session_timeline(
        db: AsyncSession, session_id: uuid.UUID
    ) -> List[Dict[str, Any]]:
        """Returns ordered timeline of agent runs and tool calls for the session."""
        stmt_runs = (
            select(AgentRun)
            .where(AgentRun.session_id == session_id)
            .order_by(AgentRun.started_at.asc())
        )
        runs_res = await db.execute(stmt_runs)
        runs = list(runs_res.scalars().all())

        timeline_items = []
        for r in runs:
            timeline_items.append({
                "id": str(r.id),
                "type": "agent_run",
                "agent_id": r.agent_id,
                "parent_run_id": str(r.parent_run_id) if r.parent_run_id else None,
                "status": r.status,
                "started_at": r.started_at.isoformat(),
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            })

            stmt_tools = (
                select(ToolCall)
                .where(ToolCall.run_id == r.id)
                .order_by(ToolCall.started_at.asc())
            )
            tools_res = await db.execute(stmt_tools)
            for t in tools_res.scalars().all():
                timeline_items.append({
                    "id": str(t.id),
                    "type": "tool_call",
                    "run_id": str(r.id),
                    "tool": t.tool_name,
                    "status": t.status,
                    "started_at": t.started_at.isoformat(),
                    "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                    "output": t.output[:200] if t.output else None,
                })

        return sorted(timeline_items, key=lambda x: x["started_at"])

    # ───────── Artifacts & Garage Object Storage ─────────
    @staticmethod
    async def create_artifact(
        db: AsyncSession,
        workspace_id: uuid.UUID,
        owner_id: uuid.UUID,
        name: str,
        kind: str,
        origin: str,
        storage_uri: str,
        mime_type: str,
        size_bytes: int,
        sha256: str,
        session_id: Optional[uuid.UUID] = None,
        created_by_run: Optional[uuid.UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
        artifact_id: Optional[uuid.UUID] = None,
    ) -> Tuple[Artifact, ArtifactVersion]:
        """Creates an artifact record along with its initial version in Garage S3."""
        art_id = artifact_id or generate_uuid()
        artifact = Artifact(
            id=art_id,
            workspace_id=workspace_id,
            owner_id=owner_id,
            session_id=session_id,
            origin=origin,
            created_by_run=created_by_run,
            name=name,
            kind=kind,
            created_at=utc_now(),
        )
        db.add(artifact)

        version = ArtifactVersion(
            id=generate_uuid(),
            artifact_id=art_id,
            version=1,
            storage_uri=storage_uri,
            mime_type=mime_type,
            size_bytes=size_bytes,
            sha256=sha256,
            metadata_=metadata or {},
            created_at=utc_now(),
        )
        db.add(version)
        await db.flush()
        return artifact, version

    @staticmethod
    async def add_artifact_version(
        db: AsyncSession,
        artifact_id: uuid.UUID,
        storage_uri: str,
        mime_type: str,
        size_bytes: int,
        sha256: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ArtifactVersion:
        """Adds a new sequential version to an existing artifact."""
        stmt = (
            select(func.coalesce(func.max(ArtifactVersion.version), 0))
            .where(ArtifactVersion.artifact_id == artifact_id)
        )
        res = await db.execute(stmt)
        max_ver = res.scalar() or 0

        version = ArtifactVersion(
            id=generate_uuid(),
            artifact_id=artifact_id,
            version=max_ver + 1,
            storage_uri=storage_uri,
            mime_type=mime_type,
            size_bytes=size_bytes,
            sha256=sha256,
            metadata_=metadata or {},
            created_at=utc_now(),
        )
        db.add(version)
        await db.flush()
        return version

    @staticmethod
    async def link_message_artifact(
        db: AsyncSession,
        message_id: uuid.UUID,
        artifact_id: uuid.UUID,
        relation: str = "attachment",
    ) -> MessageArtifact:
        """Links an artifact to a chat message."""
        link = MessageArtifact(
            message_id=message_id,
            artifact_id=artifact_id,
            relation=relation,
        )
        db.add(link)
        await db.flush()
        return link

    @staticmethod
    async def get_artifact(
        db: AsyncSession, artifact_id: uuid.UUID
    ) -> Optional[Artifact]:
        """Fetches an artifact by ID."""
        stmt = select(Artifact).where(Artifact.id == artifact_id, Artifact.deleted_at.is_(None))
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_artifact_with_latest_version(
        db: AsyncSession, artifact_id: uuid.UUID
    ) -> Optional[Dict[str, Any]]:
        """Fetches artifact details joined with its latest version."""
        stmt_art = select(Artifact).where(Artifact.id == artifact_id, Artifact.deleted_at.is_(None))
        res_art = await db.execute(stmt_art)
        art = res_art.scalar_one_or_none()
        if not art:
            return None

        stmt_ver = (
            select(ArtifactVersion)
            .where(ArtifactVersion.artifact_id == artifact_id)
            .order_by(ArtifactVersion.version.desc())
            .limit(1)
        )
        res_ver = await db.execute(stmt_ver)
        ver = res_ver.scalar_one_or_none()

        return {
            "id": str(art.id),
            "workspace_id": str(art.workspace_id),
            "owner_id": str(art.owner_id),
            "session_id": str(art.session_id) if art.session_id else None,
            "origin": art.origin,
            "name": art.name,
            "kind": art.kind,
            "created_at": art.created_at.isoformat(),
            "version": ver.version if ver else 1,
            "storage_uri": ver.storage_uri if ver else "",
            "mime_type": ver.mime_type if ver else "application/octet-stream",
            "size_bytes": ver.size_bytes if ver else 0,
            "sha256": ver.sha256 if ver else "",
            "metadata": ver.metadata_ if ver else {},
        }

    @staticmethod
    async def list_artifacts(
        db: AsyncSession,
        workspace_id: Optional[uuid.UUID] = None,
        session_id: Optional[uuid.UUID] = None,
        origin: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Lists active artifacts with their latest version info."""
        stmt = select(Artifact).where(Artifact.deleted_at.is_(None))
        if workspace_id:
            stmt = stmt.where(Artifact.workspace_id == workspace_id)
        if session_id:
            stmt = stmt.where(Artifact.session_id == session_id)
        if origin:
            stmt = stmt.where(Artifact.origin == origin)

        stmt = stmt.order_by(Artifact.created_at.desc()).limit(limit)
        res = await db.execute(stmt)
        artifacts = list(res.scalars().all())

        results = []
        for art in artifacts:
            stmt_ver = (
                select(ArtifactVersion)
                .where(ArtifactVersion.artifact_id == art.id)
                .order_by(ArtifactVersion.version.desc())
                .limit(1)
            )
            res_ver = await db.execute(stmt_ver)
            ver = res_ver.scalar_one_or_none()

            results.append({
                "id": str(art.id),
                "workspace_id": str(art.workspace_id),
                "owner_id": str(art.owner_id),
                "session_id": str(art.session_id) if art.session_id else None,
                "origin": art.origin,
                "name": art.name,
                "kind": art.kind,
                "created_at": art.created_at.isoformat(),
                "version": ver.version if ver else 1,
                "storage_uri": ver.storage_uri if ver else "",
                "mime_type": ver.mime_type if ver else "application/octet-stream",
                "size_bytes": ver.size_bytes if ver else 0,
                "sha256": ver.sha256 if ver else "",
                "metadata": ver.metadata_ if ver else {},
            })

        return results

    @staticmethod
    async def soft_delete_artifact(
        db: AsyncSession, artifact_id: uuid.UUID
    ) -> bool:
        """Soft-deletes an artifact."""
        stmt = (
            update(Artifact)
            .where(Artifact.id == artifact_id)
            .values(deleted_at=utc_now())
        )
        res = await db.execute(stmt)
        await db.flush()
        return res.rowcount > 0
