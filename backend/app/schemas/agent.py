"""Agent catalog and timeline schemas."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AgentInfo(BaseModel):
    id: str
    name: str
    description: str


class TimelineItem(BaseModel):
    id: str
    type: str  # agent_run or tool_call
    started_at: str
    agent_id: Optional[str] = None
    parent_run_id: Optional[str] = None
    run_id: Optional[str] = None
    tool: Optional[str] = None
    status: str
    completed_at: Optional[str] = None
    finished_at: Optional[str] = None
    output: Optional[str] = None


class TimelineResponse(BaseModel):
    session_id: str
    timeline: List[Dict[str, Any]] = Field(default_factory=list)
