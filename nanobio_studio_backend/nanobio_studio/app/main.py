"""
Main FastAPI application.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from nanobio_studio.app.core.config import settings
from nanobio_studio.app.core.logging import configure_logging
from nanobio_studio.app.db.session import init_db, close_db
from nanobio_studio.app.api.routes import health, ingestion, query, ml
from loguru import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for app startup and shutdown."""
    # Startup
    logger.info("Starting NanoBio Studio Backend...")
    await init_db()
    logger.info("Database initialized")
    yield
    # Shutdown
    logger.info("Shutting down NanoBio Studio Backend...")
    await close_db()
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="Backend API for NanoBio Studio™ - AI nanomedicine platform",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(ingestion.router)
app.include_router(query.router)
app.include_router(ml.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "NanoBio Studio Backend",
        "version": settings.api_version,
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn
    configure_logging()
    uvicorn.run(app, host="0.0.0.0", port=8000)
