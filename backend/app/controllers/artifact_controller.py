"""
Artifact Controller managing Garage S3 storage and DB persistence.
Handles user uploads, agent-generated deliverables, and downloads.
"""
from __future__ import annotations

import io
import logging
import uuid
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, UploadFile, status
from fastapi.responses import Response

from app.core.config import settings
from db.connection import async_session_scope
from db.repository import Repository
from app.controllers.agent_controller import parse_uuid_or_derive
from app.services.storage_service import get_storage_service
from app.schemas.artifact import ArtifactResponse, ArtifactListResponse

logger = logging.getLogger("app.controllers.artifact")


def format_artifact_response(item: Dict[str, Any]) -> ArtifactResponse:
    art_id = item["id"]
    return ArtifactResponse(
        id=art_id,
        workspace_id=item["workspace_id"],
        owner_id=item["owner_id"],
        session_id=item.get("session_id"),
        origin=item["origin"],
        name=item["name"],
        kind=item["kind"],
        created_at=item["created_at"],
        version=item.get("version", 1),
        storage_uri=item.get("storage_uri", ""),
        mime_type=item.get("mime_type", "application/octet-stream"),
        size_bytes=item.get("size_bytes", 0),
        sha256=item.get("sha256", ""),
        download_url=f"/api/artifacts/{art_id}/download",
        content_url=f"/api/artifacts/{art_id}/content",
        metadata=item.get("metadata", {}),
    )


class ArtifactController:
    @staticmethod
    async def upload_user_artifact(
        file: UploadFile,
        session_id: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> ArtifactResponse:
        """
        Receives an uploaded file, saves it directly to Garage S3 (NO local file persistence),
        and records it in PostgreSQL as an artifact with origin 'user_upload'.
        """
        try:
            content = await file.read()
            if not content:
                raise HTTPException(status_code=400, detail="Uploaded file is empty.")

            storage = get_storage_service()
            filename = file.filename or "uploaded_file"
            content_type = file.content_type or "application/octet-stream"

            upload_result = storage.upload_bytes(
                content=content,
                filename=filename,
                content_type=content_type,
                prefix="user_uploads",
            )

            session_uuid = parse_uuid_or_derive(session_id) if session_id else None
            message_uuid = parse_uuid_or_derive(message_id) if message_id else None

            async with async_session_scope() as db:
                user, workspace = await Repository.get_or_create_default_identity(db)
                if session_uuid:
                    sess = await Repository.get_session(db, session_uuid)
                    if not sess:
                        await Repository.create_session(
                            db,
                            workspace_id=workspace.id,
                            user_id=user.id,
                            title="Conversation",
                            session_id=session_uuid,
                        )

                art, ver = await Repository.create_artifact(
                    db,
                    workspace_id=workspace.id,
                    owner_id=user.id,
                    name=upload_result["filename"],
                    kind=upload_result["kind"],
                    origin="user_upload",
                    storage_uri=upload_result["storage_uri"],
                    mime_type=upload_result["mime_type"],
                    size_bytes=upload_result["size_bytes"],
                    sha256=upload_result["sha256"],
                    session_id=session_uuid,
                )

                if message_uuid:
                    await Repository.link_message_artifact(
                        db,
                        message_id=message_uuid,
                        artifact_id=art.id,
                        relation="attachment",
                    )

                art_detail = await Repository.get_artifact_with_latest_version(db, art.id)

            if not art_detail:
                raise HTTPException(status_code=500, detail="Failed to retrieve saved artifact.")

            return format_artifact_response(art_detail)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error uploading artifact to Garage S3: {e}")
            raise HTTPException(status_code=500, detail=f"Storage upload error: {str(e)}")

    @staticmethod
    async def create_agent_artifact(
        name: str,
        content: bytes | str,
        kind: Optional[str] = None,
        session_id: Optional[str] = None,
        run_id: Optional[str] = None,
        mime_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ArtifactResponse:
        """
        Stores an agent-generated artifact (e.g. PDF resume, code output, report)
        directly in Garage S3 and records it with origin 'agent_generated'.
        """
        raw_bytes = content.encode("utf-8") if isinstance(content, str) else content

        storage = get_storage_service()
        upload_result = storage.upload_bytes(
            content=raw_bytes,
            filename=name,
            content_type=mime_type,
            prefix="agent_artifacts",
        )

        session_uuid = parse_uuid_or_derive(session_id) if session_id else None
        run_uuid = parse_uuid_or_derive(run_id) if run_id else None

        async with async_session_scope() as db:
            user, workspace = await Repository.get_or_create_default_identity(db)
            art, ver = await Repository.create_artifact(
                db,
                workspace_id=workspace.id,
                owner_id=user.id,
                name=upload_result["filename"],
                kind=kind or upload_result["kind"],
                origin="agent_generated",
                storage_uri=upload_result["storage_uri"],
                mime_type=upload_result["mime_type"],
                size_bytes=upload_result["size_bytes"],
                sha256=upload_result["sha256"],
                session_id=session_uuid,
                created_by_run=run_uuid,
                metadata=metadata,
            )
            art_detail = await Repository.get_artifact_with_latest_version(db, art.id)

        if not art_detail:
            raise HTTPException(status_code=500, detail="Failed to record agent artifact.")

        return format_artifact_response(art_detail)

    @staticmethod
    async def list_artifacts(
        session_id: Optional[str] = None,
        origin: Optional[str] = None,
        limit: int = 100,
    ) -> ArtifactListResponse:
        session_uuid = parse_uuid_or_derive(session_id) if session_id else None
        async with async_session_scope() as db:
            items = await Repository.list_artifacts(
                db,
                session_id=session_uuid,
                origin=origin,
                limit=limit,
            )

        artifacts = [format_artifact_response(item) for item in items]
        return ArtifactListResponse(total=len(artifacts), artifacts=artifacts)

    @staticmethod
    async def get_artifact(artifact_id: str) -> ArtifactResponse:
        art_uuid = parse_uuid_or_derive(artifact_id)
        async with async_session_scope() as db:
            item = await Repository.get_artifact_with_latest_version(db, art_uuid)

        if not item:
            raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found.")

        return format_artifact_response(item)

    @staticmethod
    async def serve_artifact_content(artifact_id: str, inline: bool = False) -> Response:
        """
        Streams file content directly from Garage S3 to client.
        """
        art_uuid = parse_uuid_or_derive(artifact_id)
        async with async_session_scope() as db:
            item = await Repository.get_artifact_with_latest_version(db, art_uuid)

        if not item:
            raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found.")

        storage_uri = item.get("storage_uri")
        if not storage_uri:
            raise HTTPException(status_code=404, detail="Artifact storage pointer missing.")

        storage = get_storage_service()
        try:
            content_bytes, content_type, filename = storage.download_bytes(storage_uri)
        except Exception as e:
            logger.error(f"Error fetching artifact from Garage S3 ({storage_uri}): {e}")
            raise HTTPException(status_code=502, detail=f"Garage object retrieval failed: {str(e)}")

        disp_type = "inline" if inline else "attachment"
        headers = {
            "Content-Disposition": f'{disp_type}; filename="{item["name"]}"',
            "Content-Length": str(len(content_bytes)),
        }

        return Response(
            content=content_bytes,
            media_type=item.get("mime_type") or content_type,
            headers=headers,
        )

    @staticmethod
    async def delete_artifact(artifact_id: str) -> Dict[str, Any]:
        art_uuid = parse_uuid_or_derive(artifact_id)
        async with async_session_scope() as db:
            item = await Repository.get_artifact_with_latest_version(db, art_uuid)
            if not item:
                raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found.")

            storage_uri = item.get("storage_uri")
            await Repository.soft_delete_artifact(db, art_uuid)

        if storage_uri:
            storage = get_storage_service()
            storage.delete_object(storage_uri)

        return {"status": "success", "deleted_id": artifact_id}
