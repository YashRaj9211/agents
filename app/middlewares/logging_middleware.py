"""
Logging and execution timing middleware.
Adds X-Process-Time response header and logs request execution metrics.
"""
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.middleware.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.perf_counter()
        response: Response = await call_next(request)
        process_time = (time.perf_counter() - start_time) * 1000  # ms
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
        
        # Don't log spammy health endpoints continuously
        if not request.url.path.endswith("/health"):
            logger.info(
                f"{request.method} {request.url.path} - {response.status_code} ({process_time:.2f}ms)"
            )
        return response
