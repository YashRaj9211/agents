"""Quick actions schema."""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class QuickActionResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    prompt: str
    emoji: Optional[str] = "⚡"
    style: Dict[str, Any] = Field(default_factory=dict)
    target_agent_id: Optional[str] = None

    class Config:
        from_attributes = True
