"""Quick Actions prompt cards route."""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db_session
from app.controllers.agent_controller import AgentController
from app.schemas.quick_action import QuickActionResponse

router = APIRouter(tags=["Quick Actions"])


@router.get("/quick-actions", response_model=List[QuickActionResponse])
async def list_quick_actions(db: AsyncSession = Depends(get_db_session)):
    return await AgentController.list_quick_actions(db)
