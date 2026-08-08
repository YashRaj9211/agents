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
# Convenience export list
# ---------------------------------------------------------------------------

FILE_TOOLS = [
    list_directory,
    read_file,
    write_file,
    append_file,
    edit_file,
    update_file,
    delete_path,
    create_directory,
]
