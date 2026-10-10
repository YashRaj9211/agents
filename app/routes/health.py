"""Health check route."""
from fastapi import APIRouter
from app.schemas.common import StatusResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=StatusResponse)
async def health():
    return StatusResponse(status="ok", message="Agents Backend API Operational")
