"""Agents catalog route."""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db_session
from app.controllers.agent_controller import AgentController
from app.schemas.agent import AgentInfo

router = APIRouter(tags=["Agents"])


@router.get("/agents", response_model=List[AgentInfo])
async def list_agents(db: AsyncSession = Depends(get_db_session)):
    return await AgentController.list_agents(db)
