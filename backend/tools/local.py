"""Safe local file and PDF tools for the browser agent."""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, TYPE_CHECKING

from pypdf import PdfReader

from config import settings

if TYPE_CHECKING:
    from browser_mcp import PlaywrightMcpClient


class LocalTools:
    """Tools limited to backend/storage/files so the agent cannot access arbitrary files."""

    def __init__(self) -> None:
        self.root = settings.files_dir.resolve()
        (self.root / "input").mkdir(parents=True, exist_ok=True)
        (self.root / "output").mkdir(parents=True, exist_ok=True)

    @property
    def schemas(self) -> list[dict[str, Any]]:
        return [
            self._schema("read_text_file", "Read a UTF-8 text, JSON, Markdown, HTML, or CSS file from storage/files.", {"path": self._path_field()}, ["path"]),
            self._schema("write_text_file", "Write a UTF-8 file under storage/files/output. Use this for HTML, CSS, Markdown, JSON, and cover letters.", {"path": self._path_field("A relative path beginning with output/."), "content": {"type": "string", "description": "Text to write."}}, ["path", "content"]),
            self._schema("read_pdf_text", "Extract readable text from a PDF under storage/files. Use this to read a resume.", {"path": self._path_field()}, ["path"]),
            self._schema("html_to_pdf", "Create a PDF from HTML and optional CSS with Playwright. It is written under storage/files/output.", {"path": self._path_field("A relative PDF path beginning with output/, e.g. output/resume.pdf."), "html": {"type": "string", "description": "HTML body or complete document."}, "css": {"type": "string", "description": "Optional CSS."}}, ["path", "html"]),
        ]

    async def execute(self, name: str, arguments: dict[str, Any], browser: "PlaywrightMcpClient") -> str | None:
        try:
            if name == "read_text_file":
                return self._path(arguments["path"]).read_text(encoding="utf-8")
            if name == "write_text_file":
                path = self._output_path(arguments["path"])
                path.write_text(arguments["content"], encoding="utf-8")
                return f"Wrote {path.relative_to(self.root)}"
            if name == "read_pdf_text":
                reader = PdfReader(self._path(arguments["path"]))
                return "\n\n".join(f"--- Page {i + 1} ---\n{page.extract_text() or ''}" for i, page in enumerate(reader.pages))
            if name == "html_to_pdf":
                return await self._html_to_pdf(arguments, browser)
        except (KeyError, OSError, ValueError) as error:
            return json.dumps({"error": str(error)})
        return None

    async def _html_to_pdf(self, arguments: dict[str, Any], browser: "PlaywrightMcpClient") -> str:
        output = self._output_path(arguments["path"])
        if output.suffix.lower() != ".pdf":
            raise ValueError("PDF output path must end with .pdf")
        document = self._document(arguments["html"], arguments.get("css", ""))
        data_url = "data:text/html;base64," + base64.b64encode(document.encode()).decode()
        navigation = await browser.call_tool("browser_navigate", {"url": data_url})
        if self._is_error(navigation):
            return navigation
        # Playwright MCP writes filenames into its configured --output-dir.
        result = await browser.call_tool("browser_pdf_save", {"filename": output.name})
        if self._is_error(result):
            return result
        if not output.is_file():
            return json.dumps({"error": "Playwright reported success, but the PDF was not found in output/."})
        return f"Created PDF at {output.relative_to(self.root)}"

    def _path(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Path must stay inside storage/files")
        if not path.is_file():
            raise ValueError(f"File does not exist: {relative_path}")
        return path

    def _output_path(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        output_root = (self.root / "output").resolve()
        if not path.is_relative_to(output_root):
            raise ValueError("Output path must begin with output/")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _document(html: str, css: str) -> str:
        if "<html" in html.lower():
            return html
        return f"<!doctype html><html><head><meta charset=\"utf-8\"><style>@page {{ size: A4; margin: 16mm; }} body {{ font-family: Arial, sans-serif; color: #1f2937; line-height: 1.45; }} {css}</style></head><body>{html}</body></html>"

    @staticmethod
    def _is_error(result: str) -> bool:
        try:
            return bool(json.loads(result).get("error"))
        except json.JSONDecodeError:
            return False

    @staticmethod
    def _path_field(description: str = "A relative path inside storage/files, e.g. input/resume.pdf.") -> dict[str, str]:
        return {"type": "string", "description": description}

    @staticmethod
    def _schema(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
        return {"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object", "properties": properties, "required": required}}}
