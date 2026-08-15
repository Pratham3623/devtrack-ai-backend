import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import get_redis
from app.db.session import get_db

router = APIRouter()


def _uptime_seconds(request: Request) -> float:
    start = getattr(request.app.state, "start_time", time.time())
    return round(time.time() - start, 1)


@router.get(
    "/health",
    summary="Aggregated System Health Check",
    status_code=status.HTTP_200_OK,
)
async def health_check(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Optional[Redis] = Depends(get_redis),
) -> Dict[str, Any]:
    """Returns service operational status, dependency health, and runtime metrics."""
    db_status = "healthy"
    db_latency_ms: Optional[float] = None
    try:
        t0 = time.perf_counter()
        await db.execute(text("SELECT 1"))
        db_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    except Exception:
        db_status = "unhealthy"

    redis_status = "healthy"
    redis_latency_ms: Optional[float] = None
    if redis is not None:
        try:
            t0 = time.perf_counter()
            await redis.ping()
            redis_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        except Exception:
            redis_status = "unhealthy"
    else:
        redis_status = "disconnected"

    is_healthy = db_status == "healthy" and redis_status in ("healthy", "disconnected")

    return {
        "status": "healthy" if is_healthy else "degraded",
        "service": settings.APP_NAME,
        "version": "1.0.0",
        "environment": settings.APP_ENV,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": _uptime_seconds(request),
        "dependencies": {
            "database": {
                "status": db_status,
                "latency_ms": db_latency_ms,
            },
            "redis": {
                "status": redis_status,
                "latency_ms": redis_latency_ms,
            },
        },
    }


@router.get(
    "/health/live",
    summary="Liveness Probe",
    status_code=status.HTTP_200_OK,
)
async def liveness_probe() -> Dict[str, str]:
    """Kubernetes / Docker liveness probe — confirms the process is running."""
    return {
        "status": "live",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get(
    "/health/ready",
    summary="Readiness Probe",
    status_code=status.HTTP_200_OK,
)
async def readiness_probe(
    db: AsyncSession = Depends(get_db),
    redis: Optional[Redis] = Depends(get_redis),
) -> JSONResponse:
    """Kubernetes / Docker readiness probe — confirms all dependencies are reachable."""
    errors: list[str] = []

    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        errors.append(f"Database connection failed: {exc}")

    if redis is not None:
        try:
            await redis.ping()
        except Exception as exc:
            errors.append(f"Redis connection failed: {exc}")
    else:
        errors.append("Redis client uninitialized")

    if errors:
        return JSONResponse(
            status_code=503,
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
