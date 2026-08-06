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
    """Readiness check.

    Includes object storage, because a deployment whose attachment store is
    unreachable is not ready to accept uploads — and finding that out on the
    first upload, from a user holding a file, is finding out too late.

    The body names the driver and whether it is reachable. It never carries the
    endpoint, the region, a bucket policy or a credential: a readiness probe is
    read by load balancers, monitoring systems and anybody who can reach the
    port.
    """
    from nanobio_studio.app.storage import storage_health

    storage = storage_health()
    return {
        "ready": storage.healthy,
        "service": "NanoBio Studio Backend",
        "storage": {
            "healthy": storage.healthy,
            "driver": storage.driver,
            "bucket": storage.bucket,
            "detail": storage.detail,
        },
    }
