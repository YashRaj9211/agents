"""
File System Tools for ADK agents.

Provides read, write, edit, update, append, delete and list_directory
operations safe for use inside an LlmAgent tool list.
"""

import os
import shutil
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# List Directory
# ---------------------------------------------------------------------------

def list_directory(path: str, recursive: bool = False) -> dict:
    """List all files and subdirectories inside a given directory.

    Args:
        path: Absolute or relative path to the directory.
        recursive: If True, list all nested files and folders too.

    Returns:
        A dict with keys 'entries' (list of path strings) and 'error' (str or None).
    """
    try:
        root = Path(path).resolve()
        if not root.exists():
            return {"entries": [], "error": f"Path does not exist: {path}"}
        if not root.is_dir():
            return {"entries": [], "error": f"Path is not a directory: {path}"}

        if recursive:
            entries = [str(p) for p in root.rglob("*")]
        else:
            entries = [str(p) for p in root.iterdir()]

        return {"entries": sorted(entries), "error": None}
    except Exception as exc:
        return {"entries": [], "error": str(exc)}


# ---------------------------------------------------------------------------
# Read File
# ---------------------------------------------------------------------------

def read_file(path: str, encoding: str = "utf-8") -> dict:
    """Read the full content of a text file.

    Args:
        path: Absolute or relative path to the file.
        encoding: File encoding (default utf-8).

    Returns:
        A dict with keys 'content' (str) and 'error' (str or None).
    """
    try:
        content = Path(path).read_text(encoding=encoding)
        return {"content": content, "error": None}
    except Exception as exc:
        return {"content": "", "error": str(exc)}


# ---------------------------------------------------------------------------
# Write File  (create or overwrite)
# ---------------------------------------------------------------------------

def write_file(path: str, content: str, encoding: str = "utf-8") -> dict:
    """Write (or overwrite) a file with the given content.
    Parent directories are created automatically.

    Args:
        path: Absolute or relative path to the file.
        content: The text content to write.
        encoding: File encoding (default utf-8).

    Returns:
        A dict with keys 'success' (bool) and 'error' (str or None).
    """
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding=encoding)
        return {"success": True, "error": None}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Append to File
# ---------------------------------------------------------------------------

def append_file(path: str, content: str, encoding: str = "utf-8") -> dict:
    """Append text to the end of an existing file (creates the file if missing).

    Args:
        path: Absolute or relative path to the file.
        content: Text to append.
        encoding: File encoding (default utf-8).

    Returns:
        A dict with keys 'success' (bool) and 'error' (str or None).
    """
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding=encoding) as f:
            f.write(content)
        return {"success": True, "error": None}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Edit File  (find-and-replace)
# ---------------------------------------------------------------------------

def edit_file(path: str, old_text: str, new_text: str, encoding: str = "utf-8") -> dict:
    """Replace the first occurrence of old_text with new_text in a file.

    Args:
        path: Absolute or relative path to the file.
        old_text: Exact substring to find.
        new_text: Replacement text.
        encoding: File encoding (default utf-8).

    Returns:
        A dict with keys 'success' (bool), 'replacements' (int count), and 'error' (str or None).
    """
    try:
        p = Path(path)
        original = p.read_text(encoding=encoding)
        if old_text not in original:
            return {"success": False, "replacements": 0, "error": "old_text not found in file"}
        updated = original.replace(old_text, new_text, 1)
        p.write_text(updated, encoding=encoding)
        return {"success": True, "replacements": 1, "error": None}
    except Exception as exc:
        return {"success": False, "replacements": 0, "error": str(exc)}


# ---------------------------------------------------------------------------
# Update File  (replace all occurrences)
# ---------------------------------------------------------------------------

def update_file(path: str, old_text: str, new_text: str, encoding: str = "utf-8") -> dict:
    """Replace ALL occurrences of old_text with new_text in a file.

    Args:
        path: Absolute or relative path to the file.
        old_text: Exact substring to find.
        new_text: Replacement text.
        encoding: File encoding (default utf-8).

    Returns:
        A dict with keys 'success' (bool), 'replacements' (int count), and 'error' (str or None).
    """
    try:
        p = Path(path)
        original = p.read_text(encoding=encoding)
        count = original.count(old_text)
        if count == 0:
            return {"success": False, "replacements": 0, "error": "old_text not found in file"}
        updated = original.replace(old_text, new_text)
        p.write_text(updated, encoding=encoding)
        return {"success": True, "replacements": count, "error": None}
    except Exception as exc:
        return {"success": False, "replacements": 0, "error": str(exc)}


# ---------------------------------------------------------------------------
# Delete File or Directory
# ---------------------------------------------------------------------------

def delete_path(path: str, recursive: bool = False) -> dict:
    """Delete a file or directory.

    Args:
        path: Absolute or relative path to delete.
        recursive: If True and path is a directory, remove it and all its contents.

    Returns:
        A dict with keys 'success' (bool) and 'error' (str or None).
    """
    try:
        p = Path(path)
        if not p.exists():
            return {"success": False, "error": f"Path does not exist: {path}"}
        if p.is_dir():
            if recursive:
                shutil.rmtree(p)
            else:
                p.rmdir()   # only works if empty
        else:
            p.unlink()
        return {"success": True, "error": None}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Create Directory
# ---------------------------------------------------------------------------

def create_directory(path: str) -> dict:
    """Create a directory (including all missing parent directories).

    Args:
        path: Absolute or relative path to create.

    Returns:
        A dict with keys 'success' (bool) and 'error' (str or None).
    """
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return {"success": True, "error": None}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Garage S3 Object Storage Tools (Stored in Garage, NOT local file)
# ---------------------------------------------------------------------------

def save_to_garage(name: str, content: str, kind: str = "file") -> dict:
    """Save an artifact, document, script, or report directly into Garage S3 object storage (not on local disk).
    
    Args:
        name: Filename (e.g., 'analysis.txt', 'script.py', 'report.md').
        content: The text/code content of the artifact.
        kind: Kind of artifact ('file', 'code', 'report', 'image', 'pdf'). Default 'file'.
        
    Returns:
        dict: Details of stored artifact in Garage S3 including artifact ID, storage URI, and download URL.
    """
    try:
        from app.services.storage_service import store_agent_artifact_sync
        res = store_agent_artifact_sync(
            name=name,
            content=content,
            kind=kind,
            origin="agent_generated",
        )
        return {
            "success": True,
            "message": f"Artifact '{name}' stored in Garage Object Storage.",
            "artifact_id": res["id"],
            "storage_uri": res["storage_uri"],
            "download_url": res["download_url"],
            "size_bytes": res["size_bytes"],
            "sha256": res["sha256"],
            "error": None,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def read_from_garage(name_or_id: str) -> dict:
    """Read the content of an artifact stored in Garage S3 object storage.
    
    Args:
        name_or_id: The artifact ID or filename.
        
    Returns:
        dict: 'content' (str) and 'error' (str or None).
    """
    try:
        from app.services.storage_service import get_storage_service, run_coro_sync
        from db.connection import async_session_scope
        from db.repository import Repository
        from app.controllers.agent_controller import parse_uuid_or_derive

        async def _find():
            async with async_session_scope() as db:
                try:
                    uuid_val = parse_uuid_or_derive(name_or_id)
                    item = await Repository.get_artifact_with_latest_version(db, uuid_val)
                    if item:
                        return item
                except Exception:
                    pass
                items = await Repository.list_artifacts(db, limit=200)
                for it in items:
                    if it["name"] == name_or_id:
                        return it
                return None

        item = run_coro_sync(_find())

        if not item or not item.get("storage_uri"):
            return {"content": "", "error": f"Artifact '{name_or_id}' not found in Garage S3."}

        storage = get_storage_service()
        data, _, _ = storage.download_bytes(item["storage_uri"])
        text = data.decode("utf-8", errors="replace")
        return {"content": text, "artifact_id": item["id"], "name": item["name"], "error": None}
    except Exception as exc:
        return {"content": "", "error": str(exc)}


def list_garage_artifacts() -> dict:
    """List all artifacts currently stored in Garage S3 object storage.
    
    Returns:
        dict: 'artifacts' (list of metadata dicts) and 'error' (str or None).
    """
    try:
        from app.services.storage_service import run_coro_sync
        from db.connection import async_session_scope
        from db.repository import Repository

        async def _list():
            async with async_session_scope() as db:
                return await Repository.list_artifacts(db, limit=100)

        items = run_coro_sync(_list())

        return {"artifacts": items, "count": len(items), "error": None}
    except Exception as exc:
        return {"artifacts": [], "count": 0, "error": str(exc)}


def delete_from_garage(name_or_id: str) -> dict:
    """Delete an artifact from Garage S3 object storage and remove from database.
    
    Args:
        name_or_id: Artifact ID or name.
        
    Returns:
        dict: 'success' (bool) and 'error' (str or None).
    """
    try:
        from app.services.storage_service import get_storage_service, run_coro_sync
        from db.connection import async_session_scope
        from db.repository import Repository
        from app.controllers.agent_controller import parse_uuid_or_derive

        async def _del():
            async with async_session_scope() as db:
                try:
                    uuid_val = parse_uuid_or_derive(name_or_id)
                    item = await Repository.get_artifact_with_latest_version(db, uuid_val)
                except Exception:
                    item = None
                if not item:
                    items = await Repository.list_artifacts(db, limit=200)
                    for it in items:
                        if it["name"] == name_or_id:
                            item = it
                            uuid_val = parse_uuid_or_derive(it["id"])
                            break
                if item:
                    await Repository.soft_delete_artifact(db, uuid_val)
                    return item.get("storage_uri")
                return None

        storage_uri = run_coro_sync(_del())

        if storage_uri:
            get_storage_service().delete_object(storage_uri)
            return {"success": True, "error": None}
        return {"success": False, "error": f"Artifact '{name_or_id}' not found."}

    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Convenience export list
# ---------------------------------------------------------------------------

GARAGE_TOOLS = [
    save_to_garage,
    read_from_garage,
    list_garage_artifacts,
    delete_from_garage,
]

FILE_TOOLS = [
    save_to_garage,
    read_from_garage,
    list_garage_artifacts,
    delete_from_garage,
    list_directory,
    read_file,
    write_file,
    append_file,
    edit_file,
    update_file,
    delete_path,
    create_directory,
]

