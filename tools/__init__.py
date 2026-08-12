"""
Top-level tools package.

All tool lists are exported here so agents can import them in one line:
    from tools import FILE_TOOLS, CLI_TOOLS, SCHEDULE_TOOLS
"""

from tools.file_tools import FILE_TOOLS
from tools.cli_tools import CLI_TOOLS
from tools.schedule_tools import SCHEDULE_TOOLS
from tools.resume_tools import generate_resume_pdf
from tools.docs_tool import DOCS_TOOLS

RESUME_TOOLS = [generate_resume_pdf]

__all__ = [
    "FILE_TOOLS",
    "CLI_TOOLS",
    "SCHEDULE_TOOLS",
    "RESUME_TOOLS",
    "DOCS_TOOLS",
]


