"""Health check endpoints for liveness and readiness probes."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint for Kubernetes liveness and readiness probes

    Returns:
        - 200 OK if the application is healthy and database is accessible
        - 500 Error if there are issues
    """
    try:
        # Check database connection
        await db.execute(text("SELECT 1"))

        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "error", "error": str(e)}, 500


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """
    Readiness check endpoint - checks if the application is ready to serve traffic
    """
    try:
        # Check database connection
        await db.execute(text("SELECT 1"))

        return {"status": "ready", "database": "connected"}
    except Exception as e:
        return {"status": "not_ready", "database": "error", "error": str(e)}, 503


@router.get("/live")
async def liveness_check():
    """
    Liveness check endpoint - checks if the application is alive
    (doesn't check external dependencies like database)
    """
    return {"status": "alive"}
