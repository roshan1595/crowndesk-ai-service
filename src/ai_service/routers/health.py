"""
CrownDesk V2 - Health Check Router
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "crowndesk-ai-service",
        "version": "1.0.0",
    }


@router.get("/ready")
async def readiness_check():
    """Kubernetes readiness probe."""
    return {"status": "ready"}


@router.get("/live")
async def liveness_check():
    """Kubernetes liveness probe."""
    return {"status": "live"}
