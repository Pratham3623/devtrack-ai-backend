from typing import Any, Dict, Optional


class BaseAppException(Exception):
    """Base exception class for all custom application errors."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = 500,
        details: Optional[Any] = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class EntityNotFoundException(BaseAppException):
    def __init__(self, entity_name: str, entity_id: Any):
        super().__init__(
            message=f"{entity_name} with ID '{entity_id}' was not found.",
            code="ENTITY_NOT_FOUND",
            status_code=404,
        )


class UnauthorizedException(BaseAppException):
    def __init__(self, message: str = "Invalid or missing authentication credentials."):
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=401,
        )


class ForbiddenException(BaseAppException):
    def __init__(self, message: str = "Access denied for requested resource."):
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=403,
        )


class ValidationException(BaseAppException):
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            details=details,
        )


class ServiceUnavailableException(BaseAppException):
    def __init__(self, service_name: str):
        super().__init__(
            message=f"External dependency service '{service_name}' is currently unavailable.",
            code="SERVICE_UNAVAILABLE",
            status_code=503,
        )
