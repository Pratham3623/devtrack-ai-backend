"""
Structured logging with structlog + stdlib integration.

- JSON output in production (APP_ENV=production).
- Human-readable colored output in development.
- Request-scoped context (request_id, user_id, org_id) via contextvars.
"""
import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

from app.core.config import settings


def _add_service_info(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Inject static service metadata into every log record."""
    event_dict.setdefault("service", settings.APP_NAME)
    event_dict.setdefault("env", settings.APP_ENV)
    return event_dict


def configure_logging() -> None:
    """Configure structlog + stdlib logging integration."""
    is_production = settings.APP_ENV == "production"

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_service_info,
        structlog.processors.StackInfoRenderer(),
    ]

    if is_production:
        processors = shared_processors + [
            structlog.stdlib.filter_by_level,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    # Configure root stdlib logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        root_logger.addHandler(handler)

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "watchfiles", "aiosqlite"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# Alias setup_logging to configure_logging for backward compatibility
setup_logging = configure_logging


def get_logger(name: str = "app") -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to the given module name."""
    return structlog.get_logger(name)


# Export standard logger
logger = get_logger("app")
