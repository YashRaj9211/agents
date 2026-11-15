"""Run management schemas: live runs, run detail, cancellation, peer mailbox."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RunSummary(BaseModel):
    run_id: str
    session_id: Optional[str] = None
    session_title: Optional[str] = None
    agent_id: str
    status: str
    origin: Optional[str] = None
    parent_run_id: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    elapsed_ms: Optional[int] = None
    live: bool = False
    error: Optional[str] = None


class RunListResponse(BaseModel):
    runs: List[RunSummary] = Field(default_factory=list)
    active_count: int = 0
    limit: int = 0


class RunDetail(RunSummary):
    last_seq: int = 0
    truncated: bool = False
    final_output: Optional[str] = None
    prompt_preview: Optional[str] = None


class CancelRunResponse(BaseModel):
    success: bool
    run_id: Optional[str] = None
    session_id: Optional[str] = None
    status: str
    cancelled: bool = False
    cancelled_children: List[str] = Field(default_factory=list)
    message: Optional[str] = None


class PendingMessageItem(BaseModel):
    id: str
    content: str
    kind: str
    status: str
    hop_count: int
    expect_reply: bool
    sender_agent_id: Optional[str] = None
    sender_session_id: Optional[str] = None
    root_message_id: Optional[str] = None
    created_at: Optional[str] = None


class PendingMessagesResponse(BaseModel):
    session_id: str
    total: int
    messages: List[PendingMessageItem] = Field(default_factory=list)


class SpawnTaskResult(BaseModel):
    agent_id: str
    prompt: str
    run_id: Optional[str] = None
    session_id: Optional[str] = None
    session_title: Optional[str] = None
    status: str
    error: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)
