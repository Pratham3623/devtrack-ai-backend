"""
Compatible UUID type that works on both PostgreSQL (native UUID) and SQLite (TEXT).
All models should import from here instead of sqlalchemy.dialects.postgresql.
"""
import uuid
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import TypeDecorator, CHAR

from app.core.config import settings


class CompatUUID(TypeDecorator):
    """
    Platform-independent UUID type.
    - On PostgreSQL: uses native UUID column.
    - On SQLite / others: stores UUID as a 36-char string.
    """
    impl = CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value) if isinstance(value, uuid.UUID) else str(uuid.UUID(str(value)))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(str(value))
        return value


# Convenience alias — drop-in replacement for UUID(as_uuid=True)
UUID = CompatUUID
