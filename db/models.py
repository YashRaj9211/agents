"""
SQLAlchemy 2.0 ORM Models for Multi-Agent Orchestrator Platform.
Matches the enterprise schema definition with full type annotations.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def generate_uuid() -> uuid.UUID:
    """Generates UUIDv7 (time-ordered) if supported by runtime, else UUIDv4."""
    if hasattr(uuid, "uuid7"):
        return uuid.uuid7()
    return uuid.uuid4()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# JSON type supporting both Postgres JSONB and SQLite JSON
JsonType = JSONB().with_variant(sa.JSON(), "sqlite")


class Base(DeclarativeBase):
    pass


# ───────── 1. Identity ─────────
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=generate_uuid)
    auth_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    auth_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    handle: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("auth_provider", "auth_subject", name="uq_users_auth_provider_subject"),
    )

    owned_workspaces: Mapped[List[Workspace]] = relationship(
        "Workspace", back_populates="owner", cascade="all, delete-orphan"
    )
    sessions: Mapped[List[Session]] = relationship("Session", back_populates="user")
    notifications: Mapped[List[Notification]] = relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    owner: Mapped[User] = relationship("User", back_populates="owned_workspaces")
    members: Mapped[List[WorkspaceMember]] = relationship(
        "WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan"
    )
    sessions: Mapped[List[Session]] = relationship("Session", back_populates="workspace")


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(50), default="member", nullable=False)

    workspace: Mapped[Workspace] = relationship("Workspace", back_populates="members")
    user: Mapped[User] = relationship("User")


# ───────── 2. Secrets & Credentials ─────────
class Credential(Base):
    __tablename__ = "credentials"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=generate_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)  # 'api_key', 'oauth_token', 'basic'
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_id: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_credentials_workspace_name"),
    )


# ───────── 3. Tools & MCPs ─────────
class MCPServer(Base):
    __tablename__ = "mcp_servers"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=generate_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    transport: Mapped[str] = mapped_column(String(20), nullable=False)  # 'stdio', 'sse', 'http'
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    command: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    args: Mapped[List[Any]] = mapped_column(JsonType, default=list, nullable=False)
    env: Mapped[Dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)
    credential_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("credentials.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(50), default="unknown", nullable=False)
    last_health_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_mcp_servers_workspace_name"),
    )
    tools: Mapped[List[Tool]] = relationship("Tool", back_populates="mcp_server", cascade="all, delete-orphan")


class Tool(Base):
    __tablename__ = "tools"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # 'builtin', 'mcp', 'custom'
    mcp_server_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=True
    )
    input_schema: Mapped[Dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    mcp_server: Mapped[Optional[MCPServer]] = relationship("MCPServer", back_populates="tools")


# ───────── 4. Agent Catalog & Fleet ─────────
class AgentDefinition(Base):
    __tablename__ = "agent_definitions"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # e.g., 'root_agent', 'browser_agent'
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(String(50), default="worker", nullable=False)  # 'root', 'worker', 'scheduler'
    config: Mapped[Dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    sessions: Mapped[List[Session]] = relationship("Session", back_populates="primary_agent")
    runs: Mapped[List[AgentRun]] = relationship("AgentRun", back_populates="agent")


class AgentTool(Base):
    __tablename__ = "agent_tools"

    agent_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("agent_definitions.id", ondelete="CASCADE"), primary_key=True
    )
    tool_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("tools.id", ondelete="CASCADE"), primary_key=True
    )
    config: Mapped[Dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)


class AgentInstance(Base):
    __tablename__ = "agent_instances"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=generate_uuid)
    agent_id: Mapped[str] = mapped_column(String(100), ForeignKey("agent_definitions.id"), nullable=False)
    workspace_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("workspaces.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(50), default="idle", nullable=False)
    host: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    config_override: Mapped[Dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)
    last_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_agent_instances_agent_status", "agent_id", "status"),
    )


# ───────── 5. Browser Profiles ─────────
class BrowserProfile(Base):
    __tablename__ = "browser_profiles"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=generate_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    engine: Mapped[str] = mapped_column(String(50), default="chromium", nullable=False)
    storage_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    launch_options: Mapped[Dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)
    locked_by_run: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_browser_profiles_workspace_name"),
    )


# ───────── 6. Conversations (Sessions & Messages) ─────────
class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=generate_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    primary_agent_id: Mapped[Optional[str]] = mapped_column(
        String(100), ForeignKey("agent_definitions.id"), nullable=True
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    preview_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_sessions_sidebar", "user_id", "last_message_at"),
    )

    workspace: Mapped[Workspace] = relationship("Workspace", back_populates="sessions")
    user: Mapped[User] = relationship("User", back_populates="sessions")
    primary_agent: Mapped[Optional[AgentDefinition]] = relationship("AgentDefinition", back_populates="sessions")
    messages: Mapped[List[Message]] = relationship(
        "Message", back_populates="session", cascade="all, delete-orphan", order_by="Message.seq"
    )
    runs: Mapped[List[AgentRun]] = relationship(
        "AgentRun", back_populates="session", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=generate_uuid)
    session_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # 'user', 'assistant', 'system'
    sender_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    sender_agent_id: Mapped[Optional[str]] = mapped_column(
        String(100), ForeignKey("agent_definitions.id"), nullable=True
    )
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("agent_runs.id"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JsonType, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_messages_session_seq"),
    )

    session: Mapped[Session] = relationship("Session", back_populates="messages")
    run: Mapped[Optional[AgentRun]] = relationship("AgentRun", foreign_keys=[run_id])


# ───────── 7. Execution Trace (Agent Runs & Tool Calls) ─────────
class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=generate_uuid)
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True
    )
    trigger_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("messages.id"), nullable=True
    )
    parent_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("agent_runs.id"), nullable=True
    )
    agent_id: Mapped[str] = mapped_column(String(100), ForeignKey("agent_definitions.id"), nullable=False)
    instance_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("agent_instances.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(50), default="running", nullable=False)
    error: Mapped[Optional[Dict[str, Any]]] = mapped_column(JsonType, nullable=True)
    usage: Mapped[Dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_agent_runs_session_started", "session_id", "started_at"),
        Index("idx_agent_runs_parent", "parent_run_id"),
    )

    session: Mapped[Optional[Session]] = relationship("Session", back_populates="runs")
    agent: Mapped[AgentDefinition] = relationship("AgentDefinition", back_populates="runs")
    parent_run: Mapped[Optional[AgentRun]] = relationship("AgentRun", remote_side=[id], backref="child_runs")
    tool_calls: Mapped[List[ToolCall]] = relationship(
        "ToolCall", back_populates="run", cascade="all, delete-orphan", order_by="ToolCall.started_at"
    )


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=generate_uuid)
    run_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("messages.id"), nullable=True
    )
    tool_id: Mapped[Optional[uuid.UUID]] = mapped_column(sa.Uuid(as_uuid=True), ForeignKey("tools.id"), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="running", nullable=False)
    input_args: Mapped[Dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)
    output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_artifact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True
    )
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_tool_calls_run_started", "run_id", "started_at"),
    )

    run: Mapped[AgentRun] = relationship("AgentRun", back_populates="tool_calls")


# ───────── 7b. Agent Collaboration (peer mailbox) ─────────
class AgentMessage(Base):
    """A message an agent sends to another agent's session.

    Peer messages are delivered at turn boundaries: the receiving session gets a
    new run immediately when idle, or the message waits in `queued` until its
    current run finishes. `hop_count` bounds agent-to-agent ping-pong.
    """

    __tablename__ = "agent_messages"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=generate_uuid)
    sender_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    sender_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
    )
    sender_agent_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    recipient_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
    )
    recipient_agent_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reply_to_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("agent_messages.id", ondelete="SET NULL"), nullable=True
    )
    root_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("agent_messages.id", ondelete="SET NULL"), nullable=True
    )
    hop_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    kind: Mapped[str] = mapped_column(String(50), default="message", nullable=False)  # message | reply | broadcast
    expect_reply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="queued", nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    replied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_agent_messages_recipient_status", "recipient_session_id", "status"),
        Index("idx_agent_messages_recipient_agent", "recipient_agent_id", "status"),
        Index("idx_agent_messages_root", "root_message_id"),
    )


# ───────── 8. Artifacts ─────────
class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=generate_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
    )
    origin: Mapped[str] = mapped_column(String(50), nullable=False)  # 'user_upload', 'agent_generated', 'tool_output'
    created_by_run: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)  # 'file', 'image', 'code', 'report', 'screenshot'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    versions: Mapped[List[ArtifactVersion]] = relationship(
        "ArtifactVersion", back_populates="artifact", cascade="all, delete-orphan"
    )


class ArtifactVersion(Base):
    __tablename__ = "artifact_versions"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=generate_uuid)
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JsonType, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("artifact_id", "version", name="uq_artifact_versions_version"),
    )

    artifact: Mapped[Artifact] = relationship("Artifact", back_populates="versions")


class MessageArtifact(Base):
    __tablename__ = "message_artifacts"

    message_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("artifacts.id", ondelete="CASCADE"), primary_key=True
    )
    relation: Mapped[str] = mapped_column(String(50), default="attachment", nullable=False)


# ───────── 9. Platform: Notifications, Settings, Logs, Quick Actions ─────────
class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=generate_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload: Mapped[Dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    user: Mapped[User] = relationship("User", back_populates="notifications")


class Setting(Base):
    __tablename__ = "settings"

    scope_type: Mapped[str] = mapped_column(
        String(50), primary_key=True
    )  # 'system', 'workspace', 'user', 'agent', 'session'
    scope_id: Mapped[str] = mapped_column(String(100), primary_key=True, default="")
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any] = mapped_column(JsonType, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class Log(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(sa.Uuid(as_uuid=True), nullable=True)
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(sa.Uuid(as_uuid=True), nullable=True)
    instance_id: Mapped[Optional[uuid.UUID]] = mapped_column(sa.Uuid(as_uuid=True), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JsonType, nullable=True)

    __table_args__ = (
        Index("idx_logs_run_ts", "run_id", "ts"),
        Index("idx_logs_session_ts", "session_id", "ts"),
    )


class QuickAction(Base):
    __tablename__ = "quick_actions"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    emoji: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    style: Mapped[Dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)
    target_agent_id: Mapped[Optional[str]] = mapped_column(
        String(100), ForeignKey("agent_definitions.id"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
