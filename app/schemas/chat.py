"""Chat schemas for request and response streaming/sync payloads."""
from typing import Optional, List
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message text")
    agent_id: Optional[str] = Field(default="root_agent", description="Target agent to run")
    session_id: Optional[str] = Field(default=None, description="Session UUID string")
    artifact_ids: Optional[List[str]] = Field(default_factory=list, description="IDs of artifacts stored in Garage S3 attached to this message")


class ToolCallRecord(BaseModel):
    tool: str
    status: str
    output: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    thought_process: Optional[str] = None
    agent_id: str
    session_id: str
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)


class StreamEventPayload(BaseModel):
    """One SSE frame. Consumed by the UI's steps panel and HITL card.

    ``type`` widens beyond the original set as the UI grows: ``human_input_request``
    is emitted when an agent blocks in ``ask_user``, and ``heartbeat`` keeps an
    otherwise-idle stream alive while a run waits on a person.
    """

    type: str  # start, chunk, thought, agent_transfer, tool_call, tool_result, human_input_request, heartbeat, done, error
    agent_id: Optional[str] = None
    from_agent: Optional[str] = None
    to_agent: Optional[str] = None
    tool: Optional[str] = None
    status: Optional[str] = None
    text: Optional[str] = None
    final_output: Optional[str] = None
    thought_process: Optional[str] = None
    raw_text: Optional[str] = None
    session_id: Optional[str] = None
    run_id: Optional[str] = None
    error: Optional[str] = None
    # Steps panel: the arguments a tool was called with, plus a pre-rendered
    # one-line `detail` and the truncated tool `output`.
    args: Optional[dict] = None
    detail: Optional[str] = None
    output: Optional[str] = None
    # HITL: the pending question the run is blocked on.
    question_id: Optional[str] = None
    kind: Optional[str] = None
    question: Optional[str] = None
    options: Optional[List[dict]] = None
