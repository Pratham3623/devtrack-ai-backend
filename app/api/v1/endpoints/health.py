from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import get_redis
from app.db.session import get_db

router = APIRouter()


@router.get(
    "/health",
    summary="Aggregated System Health Check",
    status_code=status.HTTP_200_OK,
)
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis: Optional[Redis] = Depends(get_redis),
) -> Dict[str, Any]:
    """Returns general service operational status and health metrics."""
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    redis_status = "healthy"
    if redis is not None:
        try:
            await redis.ping()
        except Exception:
            redis_status = "unhealthy"
    else:
        redis_status = "disconnected"

    is_healthy = db_status == "healthy" and redis_status in ["healthy", "disconnected"]

    return {
        "status": "healthy" if is_healthy else "degraded",
        "service": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": {
            "database": db_status,
            "redis": redis_status,
        },
    }


@router.get(
    "/health/live",
    summary="Liveness Probe",
    status_code=status.HTTP_200_OK,
)
async def liveness_probe() -> Dict[str, str]:
    """Kubernetes / Docker Liveness probe confirming service process is running."""
    return {"status": "live", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get(
    "/health/ready",
    summary="Readiness Probe",
    status_code=status.HTTP_200_OK,
)
async def readiness_probe(
    db: AsyncSession = Depends(get_db),
    redis: Optional[Redis] = Depends(get_redis),
) -> JSONResponse:
    """Kubernetes / Docker Readiness probe confirming database and cache connectivity."""
    errors = []

    # Test Database
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        errors.append(f"Database connection failed: {str(e)}")

    # Test Redis
    if redis is not None:
        try:
            await redis.ping()
        except Exception as e:
            errors.append(f"Redis connection failed: {str(e)}")
    else:
        errors.append("Redis client uninitialized")

    if errors:
        return JSONResponse(
            status_code=status.HTTP_531_SERVICE_UNAVAILABLE if hasattr(status, "HTTP_531") else 503,
            content={
                "status": "not_ready",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "errors": errors,
            },
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "ready",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
