import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import BaseAppException
from app.core.handlers import (
    app_exception_handler,
    db_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestLoggingMiddleware, SecurityHeadersMiddleware
from app.core.redis import close_redis, init_redis

# ── Boot-time: configure structured logging ──────────────────
configure_logging()
logger = get_logger(__name__)

# Track application start time for uptime reporting
_APP_START_TIME = time.time()


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    # ── Startup ───────────────────────────────────────────────
    logger.info(
        "application.starting",
        name=settings.APP_NAME,
        env=settings.APP_ENV,
        version="1.0.0",
    )

    # Auto-create database tables
    import app.domain.models  # noqa: F401 — ensures all ORM models registered
    from app.db.base import Base
    from app.db.session import engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database.tables_ready")

    # Redis (optional in local dev)
    try:
        await init_redis()
        logger.info("redis.connected")
    except Exception as exc:
        logger.warning("redis.unavailable", error=str(exc))

    yield

    # ── Shutdown ──────────────────────────────────────────────
    logger.info("application.stopping", name=settings.APP_NAME)
    try:
        await close_redis()
    except Exception:
        pass


app = FastAPI(
    title=settings.APP_NAME,
    description="DevTrack AI — AI-Powered Enterprise Project Management Engine",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

app.state.start_time = _APP_START_TIME

# ── Mount Prometheus instrumentation ─────────────────────
try:
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics", "/api/v1/health/live", "/api/v1/health/ready"],
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    logger.info("prometheus.instrumented", endpoint="/metrics")
except ImportError:
    logger.warning("prometheus.not_installed", hint="pip install prometheus-fastapi-instrumentator")

# ── Middleware stack (LIFO — last added = outermost) ─────────
app.add_middleware(RequestLoggingMiddleware)   # 1. Request ID + structured logging
app.add_middleware(SecurityHeadersMiddleware)  # 2. Security headers

# CORS
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# ── Global Exception Handlers ─────────────────────────────────
app.add_exception_handler(BaseAppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, db_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# ── API Routers ───────────────────────────────────────────────
app.include_router(api_router, prefix=settings.API_V1_STR)

# ── Static Frontend SPA ───────────────────────────────────────
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "documentation": "/docs",
        "health": f"{settings.API_V1_STR}/health",
        "metrics": "/metrics",
        "ui": "/ui",
    }


@app.get("/ui", include_in_schema=False)
async def serve_ui():
    """Serve the Project Management SPA."""
    idx = os.path.join(_STATIC_DIR, "index.html")
    if not os.path.exists(idx):
        return {"error": "UI not found"}
    return FileResponse(idx)
