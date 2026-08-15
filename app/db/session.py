from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.logging import logger

# SQLite does not support pool_size / max_overflow — build kwargs dynamically
_is_sqlite = settings.ASYNC_DATABASE_URI.startswith("sqlite")
_engine_kwargs: dict = {"echo": settings.DEBUG}
if not _is_sqlite:
    _engine_kwargs["pool_size"] = settings.DATABASE_POOL_SIZE
    _engine_kwargs["max_overflow"] = settings.DATABASE_MAX_OVERFLOW
    _engine_kwargs["pool_pre_ping"] = True
else:
    # Required for SQLite async to allow multi-threaded access in the same process
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

# Create async engine
engine = create_async_engine(settings.ASYNC_DATABASE_URI, **_engine_kwargs)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection for FastAPI routes to yield an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session rolled back due to error: {str(e)}")
            raise
        finally:
            await session.close()
