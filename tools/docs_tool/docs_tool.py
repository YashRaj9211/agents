"""
Documents Conversion Tools.

Provides a tool to convert different document formats (PDF, Word, Excel, PowerPoint, EPUB, etc.) into Markdown.
"""

import os
import pdf_inspector
import anydoc


def convert_to_markdown(file_path: str) -> dict:
    """Convert any document file (PDF, Word, Excel, PowerPoint, EPUB, RTF, CSV, ODF) to clean Markdown format.
    
    Use this tool whenever you need to read, inspect, parse, or extract text content from documents, presentations, or spreadsheets.
    
    Supported file extensions:
    - PDF: .pdf
    - Word: .doc, .docx, .docm
    - PowerPoint: .ppt, .pps, .pot, .pptx, .pptm, .ppsx, .ppsm
    - Excel: .xls, .xlsx, .xlsm, .xlsb
    - OpenDocument: .odt, .ods, .odp
    - Rich Text Format: .rtf
    - EPUB: .epub
    - CSV: .csv

    Args:
        file_path: Absolute or relative path to the document file on the filesystem.

    Returns:
        A dict containing:
        - 'content': The extracted markdown string (or None if conversion failed).
        - 'error': A string describing the error (or None if successful).
    """
    try:
        path = os.path.abspath(file_path)
        if not os.path.exists(path):
            return {"content": None, "error": f"File not found: {file_path}"}
            
        ext = os.path.splitext(path)[1].lower()
        
        # Check supported formats
        supported_anydoc_exts = {
            # Word
            ".doc", ".docx", ".docm",
            # PowerPoint
            ".ppt", ".pps", ".pot", ".pptx", ".pptm", ".ppsx", ".ppsm",
            # Excel
            ".xls", ".xlsx", ".xlsm", ".xlsb",
            # OpenDocument
            ".odt", ".ods", ".odp",
            # Rich Text Format
            ".rtf",
            # EPUB
            ".epub",
            # CSV
            ".csv",
        }
        
        if ext == ".pdf":
            result = pdf_inspector.process_pdf(path)
            if hasattr(result, "markdown") and result.markdown is not None:
                return {"content": result.markdown, "error": None}
            else:
                return {"content": None, "error": "Failed to extract markdown from PDF."}
        elif ext in supported_anydoc_exts:
            markdown_content = anydoc.to_markdown(path)
            return {"content": markdown_content, "error": None}
        else:
            return {"content": None, "error": f"Unsupported file extension '{ext}'."}
            
    except Exception as e:
        return {"content": None, "error": str(e)}


DOCS_TOOLS = [convert_to_markdown]