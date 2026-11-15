"""
Pydantic schemas for Artifacts and Object Storage operations.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ArtifactResponse(BaseModel):
    id: str
    workspace_id: str
    owner_id: str
    session_id: Optional[str] = None
    origin: str  # 'user_upload', 'agent_generated', 'tool_output'
    name: str
    kind: str  # 'file', 'image', 'code', 'report', 'screenshot', 'pdf'
    created_at: str
    version: int = 1
    storage_uri: str
    mime_type: str
    size_bytes: int
    sha256: str
    download_url: str
    content_url: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ArtifactListResponse(BaseModel):
    total: int
    artifacts: List[ArtifactResponse]
