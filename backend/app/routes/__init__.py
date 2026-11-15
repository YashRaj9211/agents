"""
Aggregated API Router combining all sub-route modules.
"""
from fastapi import APIRouter
from app.routes.health import router as health_router
from app.routes.sessions import router as sessions_router
from app.routes.messages import router as messages_router
from app.routes.chat import router as chat_router
from app.routes.agents import router as agents_router
from app.routes.quick_actions import router as quick_actions_router
from app.routes.timeline import router as timeline_router
from app.routes.artifacts import router as artifacts_router
from app.routes.runs import router as runs_router
from app.routes.hitl import router as hitl_router
from app.routes.jobhunt import router as jobhunt_router

api_router = APIRouter(prefix="/api")

api_router.include_router(health_router)
api_router.include_router(sessions_router)
api_router.include_router(messages_router)
api_router.include_router(chat_router)
api_router.include_router(agents_router)
api_router.include_router(quick_actions_router)
api_router.include_router(timeline_router)
api_router.include_router(artifacts_router)
api_router.include_router(runs_router)
api_router.include_router(hitl_router)
api_router.include_router(jobhunt_router)

__all__ = ["api_router"]
