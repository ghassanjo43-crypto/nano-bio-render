"""
API dependency injection.
"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from nanobio_studio.app.db.session import AsyncSessionLocal


async def get_db() -> AsyncSession:
    """Get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
