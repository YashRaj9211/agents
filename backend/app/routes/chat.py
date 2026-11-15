"""
Chat API routes for SSE streaming and synchronous execution.
"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.controllers.chat_controller import ChatController
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """Server-Sent Events (SSE) streaming endpoint."""
    return StreamingResponse(
        ChatController.stream_chat(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Synchronous agent execution endpoint."""
    return await ChatController.sync_chat(request)
