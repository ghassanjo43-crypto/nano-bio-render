"""
Database session and connection management.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from nanobio_studio.app.core.config import settings
from loguru import logger

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=40,
    connect_args={"timeout": 10, "check_same_thread": False},
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_session() -> AsyncSession:
    """
    Dependency for FastAPI to get a database session.
    
    Usage in routes:
        async def route_function(session: AsyncSession = Depends(get_session)):
            pass
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.exception(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    from nanobio_studio.app.db.base import Base
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized")


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
    logger.info("Database connections closed")
