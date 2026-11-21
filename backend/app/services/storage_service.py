"""
Garage S3 Object Storage Service.

Provides object storage operations for uploading, downloading, listing,
and deleting artifacts in Garage S3, avoiding local file persistence.
"""
from __future__ import annotations

import hashlib
import io
import logging
import mimetypes
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple, BinaryIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger("app.services.storage")


class StorageService:
    """Manages S3 object storage operations connected to Garage."""

    def __init__(self):
        self.endpoint_url = settings.S3_ENDPOINT_URL
        self.region_name = settings.S3_REGION
        self.access_key_id = settings.AWS_ACCESS_KEY_ID
        self.secret_access_key = settings.AWS_SECRET_ACCESS_KEY
        self.bucket = settings.S3_BUCKET

        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name=self.region_name,
                config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
            )
        return self._client

    def ensure_bucket_exists(self) -> None:
        """Verifies that the target bucket exists, creating it if necessary."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchBucket"):
                logger.info(f"Bucket {self.bucket} not found. Creating...")
                self.client.create_bucket(Bucket=self.bucket)
            else:
                logger.warning(f"Bucket check notice ({error_code}): {e}")

    @staticmethod
    def extract_key(key_or_uri: str) -> str:
        """Normalizes an s3:// URI or key into an object key."""
        if key_or_uri.startswith("s3://"):
            parts = key_or_uri[5:].split("/", 1)
            if len(parts) == 2:
                return parts[1]
            return parts[0]
        return key_or_uri

    @staticmethod
    def detect_kind(filename: str, mime_type: str) -> str:
        """Classifies artifact kind according to schema enum ('file', 'image', 'code', 'report', 'screenshot', 'pdf')."""
        fn_lower = filename.lower()
        if fn_lower.endswith(".pdf"):
            return "pdf"
        if mime_type.startswith("image/"):
            return "screenshot" if "screenshot" in fn_lower else "image"
        if fn_lower.endswith((".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".json", ".sql", ".sh", ".rs", ".go")):
            return "code"
        if fn_lower.endswith((".md", ".txt", ".csv", ".tsv", ".docx", ".xlsx", ".pptx")):
            return "report"
        return "file"

    def upload_bytes(
        self,
        content: bytes,
        filename: str,
        content_type: Optional[str] = None,
        prefix: str = "artifacts",
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Uploads in-memory bytes directly to Garage S3.
        Returns metadata including SHA256 checksum, size, and S3 URI.
        """
        self.ensure_bucket_exists()

        if not content_type:
            guessed, _ = mimetypes.guess_type(filename)
            content_type = guessed or "application/octet-stream"

        sha256 = hashlib.sha256(content).hexdigest()
        size_bytes = len(content)

        clean_filename = os.path.basename(filename).replace(" ", "_")
        key = f"{prefix}/{uuid.uuid4().hex}/{clean_filename}"

        extra_args: Dict[str, Any] = {
            "ContentType": content_type,
        }
        if metadata:
            extra_args["Metadata"] = metadata

        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            **extra_args,
        )

        storage_uri = f"s3://{self.bucket}/{key}"
        kind = self.detect_kind(clean_filename, content_type)

        logger.info(f"Stored artifact in Garage S3: {storage_uri} ({size_bytes} bytes, {content_type})")

        return {
            "key": key,
            "bucket": self.bucket,
            "storage_uri": storage_uri,
            "filename": clean_filename,
            "size_bytes": size_bytes,
            "sha256": sha256,
            "mime_type": content_type,
            "kind": kind,
        }

    def download_bytes(self, key_or_uri: str) -> Tuple[bytes, str, str]:
        """
        Downloads artifact content directly from Garage S3.
        Returns (content_bytes, content_type, filename).
        """
        key = self.extract_key(key_or_uri)
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        content_bytes = response["Body"].read()
        content_type = response.get("ContentType", "application/octet-stream")
        filename = os.path.basename(key)
        return content_bytes, content_type, filename

    def delete_object(self, key_or_uri: str) -> bool:
        """Deletes an object from Garage S3."""
        try:
            key = self.extract_key(key_or_uri)
            self.client.delete_object(Bucket=self.bucket, Key=key)
            logger.info(f"Deleted artifact from Garage S3: {key}")
            return True
        except Exception as e:
            logger.warning(f"Error deleting object {key_or_uri} from Garage S3: {e}")
            return False

    def list_objects(self, prefix: str = "artifacts/") -> List[Dict[str, Any]]:
        """Lists objects currently stored in Garage S3."""
        try:
            res = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
            contents = res.get("Contents", [])
            items = []
            for item in contents:
                items.append({
                    "key": item["Key"],
                    "size_bytes": item["Size"],
                    "last_modified": item["LastModified"].isoformat(),
                    "storage_uri": f"s3://{self.bucket}/{item['Key']}",
                })
            return items
        except Exception as e:
            logger.warning(f"Error listing objects in Garage S3: {e}")
            return []


_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service


async def store_agent_artifact_async(
    name: str,
    content: bytes | str,
    kind: Optional[str] = None,
    mime_type: Optional[str] = None,
    origin: str = "agent_generated",
    session_id: Optional[str] = None,
    run_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Asynchronously stores an artifact in Garage S3 and records it in PostgreSQL."""
    from db.connection import async_session_scope
    from db.repository import Repository
    from app.controllers.agent_controller import parse_uuid_or_derive

    raw_bytes = content.encode("utf-8") if isinstance(content, str) else content
    storage = get_storage_service()
    upload_res = storage.upload_bytes(
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
            name=upload_res["filename"],
            kind=kind or upload_res["kind"],
            origin=origin,
            storage_uri=upload_res["storage_uri"],
            mime_type=upload_res["mime_type"],
            size_bytes=upload_res["size_bytes"],
            sha256=upload_res["sha256"],
            session_id=session_uuid,
            created_by_run=run_uuid,
            metadata=metadata,
        )
        art_id = str(art.id)

    return {
        "id": art_id,
        "name": upload_res["filename"],
        "kind": kind or upload_res["kind"],
        "origin": origin,
        "storage_uri": upload_res["storage_uri"],
        "download_url": f"/api/artifacts/{art_id}/download",
        "content_url": f"/api/artifacts/{art_id}/content",
        "size_bytes": upload_res["size_bytes"],
        "mime_type": upload_res["mime_type"],
        "sha256": upload_res["sha256"],
    }


_bg_loop = None
_bg_thread = None
_bg_lock = None


def run_coro_sync(coro):
    """Safely executes an async coroutine synchronously using a dedicated background thread."""
    import asyncio
    import threading

    global _bg_loop, _bg_thread, _bg_lock
    if _bg_lock is None:
        _bg_lock = threading.Lock()

    with _bg_lock:
        if _bg_loop is None or not _bg_loop.is_running():
            _bg_loop = asyncio.new_event_loop()

            def _target(loop):
                asyncio.set_event_loop(loop)
                loop.run_forever()

            _bg_thread = threading.Thread(target=_target, args=(_bg_loop,), daemon=True)
            _bg_thread.start()

    future = asyncio.run_coroutine_threadsafe(coro, _bg_loop)
    return future.result()


def store_agent_artifact_sync(
    name: str,
    content: bytes | str,
    kind: Optional[str] = None,
    mime_type: Optional[str] = None,
    origin: str = "agent_generated",
    session_id: Optional[str] = None,
    run_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Synchronous wrapper for storing artifacts in Garage S3 and DB."""
    return run_coro_sync(
        store_agent_artifact_async(
            name=name,
            content=content,
            kind=kind,
            mime_type=mime_type,
            origin=origin,
            session_id=session_id,
            run_id=run_id,
            metadata=metadata,
        )
    )

