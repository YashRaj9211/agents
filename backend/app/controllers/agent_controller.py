"""
Agent Controller managing catalog definitions, quick actions, and execution timelines.
"""
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from db.repository import Repository
from app.core.config import settings
from app.core.ids import parse_uuid_or_derive
from app.schemas.agent import AgentInfo
from app.schemas.quick_action import QuickActionResponse

__all__ = ["AgentController", "parse_uuid_or_derive"]

class AgentController:
    @staticmethod
    async def list_agents(db: AsyncSession) -> List[AgentInfo]:
        """Lists active agents from database catalog or falls back to settings."""
        defs = await Repository.list_agent_definitions(db)
        if defs:
            return [
                AgentInfo(id=d.id, name=d.name, description=d.description or "")
                for d in defs
            ]
        return [
            AgentInfo(id=a["id"], name=a["name"], description=a["description"])
            for a in settings.DEFAULT_AGENTS
        ]

    @staticmethod
    async def list_quick_actions(db: AsyncSession) -> List[QuickActionResponse]:
        """Lists starter quick actions for prompt cards."""
        actions = await Repository.list_quick_actions(db)
        return [
            QuickActionResponse(
                id=a.id,
                title=a.title,
                description=a.description,
                prompt=a.prompt,
                emoji=a.emoji or "⚡",
                style=a.style or {},
                target_agent_id=a.target_agent_id,
            )
            for a in actions
        ]

    @staticmethod
    async def get_session_timeline(db: AsyncSession, session_id: str) -> List[Dict[str, Any]]:
        """Retrieves execution trace tree (agent runs & tool calls)."""
        s_uuid = parse_uuid_or_derive(session_id)
        return await Repository.get_session_timeline(db, s_uuid)
