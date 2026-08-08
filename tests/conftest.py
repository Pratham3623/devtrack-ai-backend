import asyncio
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.redis import get_redis
from app.db.base import Base
# Register all models with Base.metadata
from app.domain.models.audit_log import AuditLog  # noqa: F401
from app.domain.models.board import Board, BoardColumn  # noqa: F401
from app.domain.models.invitation import Invitation  # noqa: F401
from app.domain.models.issue import Issue  # noqa: F401
from app.domain.models.organization import Organization, OrgMember  # noqa: F401
from app.domain.models.project import Project, ProjectMember  # noqa: F401
from app.domain.models.refresh_token import RefreshToken  # noqa: F401
from app.domain.models.team import Team, TeamMember  # noqa: F401
from app.domain.models.user import User  # noqa: F401

from app.main import app

# Test In-Memory SQLite Engine
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_test_db():
    """Create fresh database tables before each test and drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an isolated test async database session."""
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Yield an async HTTP test client with overridden dependencies."""

    async def _override_get_db():
        yield db_session

    async def _override_get_redis():
        yield None

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client

    app.dependency_overrides.clear()
