import time
import uuid

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


logger = structlog.get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware enforcing OWASP recommended security headers."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    - Generates a unique X-Request-ID per request.
    - Binds request context (request_id, method, path, ip) to structlog contextvars.
    - Logs request start and completion with duration and status.
    - Skips health check endpoints to avoid log spam.
    """

    SKIP_PATHS = {"/api/v1/health/live", "/api/v1/health/ready", "/metrics"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Skip noisy health/metrics paths
        if path in self.SKIP_PATHS:
            return await call_next(request)

        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Bind request context for all log statements in this request scope
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=path,
            client_ip=request.client.host if request.client else "unknown",
        )

        start_time = time.perf_counter()

        logger.info("request.started")

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            log_fn = logger.warning if response.status_code >= 400 else logger.info
            log_fn(
                "request.completed",
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration_ms}ms"
            return response

        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.exception(
                "request.failed",
                duration_ms=duration_ms,
                error=str(exc),
            )
            raise
        finally:
            structlog.contextvars.clear_contextvars()
