import uuid
from datetime import datetime, timezone
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import BaseAppException
from app.core.logging import logger


async def app_exception_handler(request: Request, exc: BaseAppException) -> JSONResponse:
    trace_id = str(uuid.uuid4())
    logger.warning(
        f"Custom app exception: [{exc.code}] {exc.message} | Path: {request.url.path} | TraceID: {trace_id}"
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "status": exc.status_code,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trace_id": trace_id,
                "details": exc.details,
            }
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    trace_id = str(uuid.uuid4())
    logger.warning(f"Request validation error on {request.url.path} | TraceID: {trace_id} | Errors: {exc.errors()}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "REQUEST_VALIDATION_ERROR",
                "message": "Input validation failed. Check parameter syntax.",
                "status": 422,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trace_id": trace_id,
                "details": exc.errors(),
            }
        },
    )


async def db_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    trace_id = str(uuid.uuid4())
    logger.error(f"Database error on {request.url.path} | TraceID: {trace_id} | Exception: {str(exc)}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "DATABASE_ERROR",
                "message": "A database operational error occurred.",
                "status": 500,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trace_id": trace_id,
            }
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    trace_id = str(uuid.uuid4())
    logger.critical(f"Unhandled exception on {request.url.path} | TraceID: {trace_id} | Error: {str(exc)}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected internal server error occurred.",
                "status": 500,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trace_id": trace_id,
            }
        },
    )
