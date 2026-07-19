"""Tool to parse text out of resumes (PDF or text files)."""
from __future__ import annotations

import os
from pypdf import PdfReader

CATEGORY = "resume"

SCHEMA = {
    "type": "function",
    "function": {
        "name": "parse_resume",
        "description": "Reads the text content of a resume file (PDF or text).",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The absolute or relative path to the resume file."
                }
            },
            "required": ["file_path"]
        }
    }
}


def parse_resume(file_path: str) -> str:
    """Read a text or PDF file and return its text content."""
    try:
        if file_path.lower().endswith(".pdf"):
            reader = PdfReader(file_path)
            text_parts = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"--- Page {i+1} ---\n{page_text}")
            return "\n\n".join(text_parts) if text_parts else "No readable text found in PDF."
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
    except Exception as e:
        return f"Error reading file {file_path}: {e}"
