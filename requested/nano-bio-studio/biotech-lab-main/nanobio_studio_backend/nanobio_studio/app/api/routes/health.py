"""
Health check routes.
"""
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", response_model=dict)
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "NanoBio Studio Backend",
        "version": "0.1.0"
    }


@router.get("/ready", response_model=dict)
async def readiness_check() -> dict:
    """Readiness check endpoint."""
    return {
        "ready": True,
        "service": "NanoBio Studio Backend"
    }
