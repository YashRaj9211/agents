"""Task-local pointer to the run executing right now.

ADK's ``AgentTool`` runs sub-agents in a *fresh* ADK session, so a tool inside a
sub-agent cannot recover the user's conversation from ``tool_context``. The run
executes in one asyncio task, so a ContextVar set by ``ChatService.run_turn``
is visible to every tool beneath it, sub-agents included.
"""
from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Optional

current_session_id: ContextVar[Optional[uuid.UUID]] = ContextVar("current_session_id", default=None)
