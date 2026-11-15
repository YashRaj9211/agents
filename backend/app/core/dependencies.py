"""
FastAPI dependency injection utilities.
"""
from typing import AsyncGenerator, Tuple
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from db.repository import Repository
from db.models import User, Workspace


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides an AsyncSession."""
    async for session in get_db():
        yield session


async def get_current_identity(
    db: AsyncSession = Depends(get_db_session),
) -> Tuple[User, Workspace]:
    """Resolves default user and workspace."""
    return await Repository.get_or_create_default_identity(db)
