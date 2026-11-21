"""Message schemas for requests and responses."""
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    role: str = Field(default="user", description="Role of the sender: user, assistant, system")
    content: str = Field(..., description="Message text payload")
    sender_agent_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class MessageResponse(BaseModel):
    id: str
    seq: int
    role: str
    content: str
    sender_agent_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    session_id: str
    total: int
    messages: List[MessageResponse]
