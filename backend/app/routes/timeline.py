"""Timeline execution trace route."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db_session
from app.controllers.agent_controller import AgentController
from app.schemas.agent import TimelineResponse

router = APIRouter(tags=["Timeline"])


@router.get("/sessions/{session_id}/timeline", response_model=TimelineResponse)
async def get_session_timeline(
    session_id: str, db: AsyncSession = Depends(get_db_session)
):
    timeline = await AgentController.get_session_timeline(db, session_id)
    return TimelineResponse(session_id=session_id, timeline=timeline)
