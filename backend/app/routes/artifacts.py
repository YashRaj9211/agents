"""
Artifacts API Routes for Garage S3 object storage operations.
Handles file uploads, listing, inline inspection, and downloads.
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, File, Form, UploadFile, Query, Response

from app.controllers.artifact_controller import ArtifactController
from app.schemas.artifact import ArtifactResponse, ArtifactListResponse

router = APIRouter(prefix="/artifacts", tags=["Artifacts"])


@router.post("/upload", response_model=ArtifactResponse)
async def upload_artifact(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    message_id: Optional[str] = Form(None),
):
    """Uploads a file directly into Garage S3 object storage (no local file persistence)."""
    return await ArtifactController.upload_user_artifact(
        file=file,
        session_id=session_id,
        message_id=message_id,
    )


@router.get("", response_model=ArtifactListResponse)
async def list_artifacts(
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    origin: Optional[str] = Query(None, description="Filter by origin: 'user_upload' or 'agent_generated'"),
    limit: int = Query(100, ge=1, le=500),
):
    """Lists artifacts stored in Garage S3."""
    return await ArtifactController.list_artifacts(
        session_id=session_id,
        origin=origin,
        limit=limit,
    )


@router.get("/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(artifact_id: str):
    """Retrieves metadata and latest version pointer for an artifact."""
    return await ArtifactController.get_artifact(artifact_id)


@router.get("/{artifact_id}/download")
async def download_artifact(artifact_id: str):
    """Streams the artifact file from Garage S3 as an attachment download."""
    return await ArtifactController.serve_artifact_content(artifact_id, inline=False)


@router.get("/{artifact_id}/content")
async def view_artifact_content(artifact_id: str):
    """Streams the artifact file from Garage S3 inline for browser rendering (images, pdfs, text)."""
    return await ArtifactController.serve_artifact_content(artifact_id, inline=True)


@router.delete("/{artifact_id}")
async def delete_artifact(artifact_id: str):
    """Removes an artifact from Garage S3 and marks it deleted in PostgreSQL."""
    return await ArtifactController.delete_artifact(artifact_id)
