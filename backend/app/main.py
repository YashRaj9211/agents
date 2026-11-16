"""
Main FastAPI Application factory and startup configuration.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.middlewares.logging_middleware import RequestLoggingMiddleware
from app.middlewares.error_handler import register_error_handlers
from app.routes import api_router
from db.connection import init_db, async_session_scope
from db.repository import Repository

logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes the database, the run manager and the agent catalog."""
    try:
        import os
        import litellm
        litellm.drop_params = True
        litellm.request_timeout = int(os.getenv("LLM_TIMEOUT", "60"))
    except Exception as exc:
        logger.warning("Could not configure litellm defaults: %s", exc)

    try:
        await init_db()
        async with async_session_scope() as db:
            await Repository.get_or_create_default_identity(db)
            await Repository.sync_agent_definitions(db, settings.DEFAULT_AGENTS)
            await Repository.sync_quick_actions(db, settings.DEFAULT_QUICK_ACTIONS)

            # Runs cannot survive a process restart: mark anything the previous
            # process left "running" as interrupted instead of pretending it is
            # still alive. Queued peer messages deliberately stay queued and are
            # delivered on the session's next turn (no surprise runs on boot).
            interrupted = await Repository.reconcile_interrupted_runs(db)
            if interrupted:
                logger.warning("Marked %d stale agent run(s) as interrupted", interrupted)

        from app.services.run_manager import get_run_manager

        manager = get_run_manager()
        manager.bind_loop()

        # Build the ADK session store eagerly so its (separate) schema is
        # created once at startup rather than by the first concurrent run.
        try:
            from app.services.chat_service import get_adk_session_service

            get_adk_session_service()
        except Exception as exc:
            logger.warning("ADK persistent sessions unavailable: %s", exc)

        logger.info("Application startup initialization completed successfully.")
    except Exception as e:
        logger.error(f"Application startup notice: {e}", exc_info=True)
    try:
        yield
    finally:
        from app.services.run_manager import get_run_manager

        try:
            await get_run_manager().shutdown()
        except Exception as exc:  # pragma: no cover - best effort on shutdown
            logger.warning("Run manager shutdown notice: %s", exc)


def create_app() -> FastAPI:
    """Factory function to build and configure the FastAPI application."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.DESCRIPTION,
        version=settings.VERSION,
        lifespan=lifespan,
    )

    # 1. Register Custom Middlewares
    app.add_middleware(RequestLoggingMiddleware)

    # 2. Register CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 3. Register Error Handlers
    register_error_handlers(app)

    # 4. Include Routers
    app.include_router(api_router)

    return app


app = create_app()
