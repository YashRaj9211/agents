"""Session schemas for conversation thread management."""
from typing import Optional, List
from pydantic import BaseModel, Field
from app.schemas.message import MessageResponse


class SessionCreate(BaseModel):
    title: Optional[str] = Field(default="New Conversation", description="Session title")
    primary_agent_id: Optional[str] = Field(default="root_agent", description="Primary agent for this session")


class SessionUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    primary_agent_id: Optional[str] = None


class SessionResponse(BaseModel):
    id: str
    title: str
    preview: str
    primary_agent_id: Optional[str] = "root_agent"
    status: str
    last_message_at: str
    created_at: str

    class Config:
        from_attributes = True


class SessionDetailResponse(BaseModel):
    id: str
    title: str
    primary_agent_id: Optional[str] = "root_agent"
    status: str
    created_at: str
    messages: List[MessageResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True
