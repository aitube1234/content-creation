"""Shared pytest fixtures for all tests."""

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.services.content_creation.config import settings
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.models import (
    Base,
    InputType,
    ScriptPromptInput,
    WorkflowState,
)
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.pipeline_client import (
    VideoGenerationPipelineClient,
)
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.repository import (
    ScriptPromptInputRepository,
)
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.service import (
    ScriptPromptIngestionService,
)


CREATOR_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_CREATOR_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


def make_jwt_token(creator_id: uuid.UUID | None = None) -> str:
    """Create a valid JWT token for testing."""
    payload = {
        "sub": str(creator_id or CREATOR_ID),
        "aud": settings.JWT_AUDIENCE,
        "exp": int(datetime.now(timezone.utc).timestamp()) + 3600,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def async_engine():
    """Create an async SQLite engine for unit tests (no PostgreSQL needed)."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def async_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide an async session for tests."""
    session_factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def sample_record(async_session: AsyncSession) -> ScriptPromptInput:
    """Create and return a sample Draft record."""
    record = ScriptPromptInput(
        input_record_id=uuid.uuid4(),
        creator_id=CREATOR_ID,
        input_type=InputType.WRITTEN_SCRIPT,
        content_text="This is a sample script content for testing purposes.",
        workflow_state=WorkflowState.DRAFT,
        character_count=52,
        created_at=datetime.now(timezone.utc),
        last_modified_at=datetime.now(timezone.utc),
    )
    async_session.add(record)
    await async_session.commit()
    return record


@pytest.fixture
def repository() -> ScriptPromptInputRepository:
    """Provide a repository instance."""
    return ScriptPromptInputRepository()


@pytest.fixture
def mock_pipeline_client() -> AsyncMock:
    """Provide a mocked pipeline client."""
    client = AsyncMock(spec=VideoGenerationPipelineClient)
    client.submit_for_generation = AsyncMock(return_value=uuid.uuid4())
    return client


@pytest.fixture
def service(mock_pipeline_client: AsyncMock) -> ScriptPromptIngestionService:
    """Provide a service instance with mocked pipeline client."""
    return ScriptPromptIngestionService(pipeline_client=mock_pipeline_client)


def create_test_app(session_override: AsyncSession | None = None) -> FastAPI:
    """Create a test FastAPI app with optional session override."""
    from backend.services.content_creation.database import get_async_session
    from backend.services.content_creation.main import app

    if session_override is not None:
        async def override_session():
            yield session_override

        app.dependency_overrides[get_async_session] = override_session

    return app


@pytest_asyncio.fixture
async def test_client(async_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an httpx AsyncClient for integration testing."""
    app = create_test_app(async_session)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {make_jwt_token()}"},
    ) as client:
        yield client
    app.dependency_overrides.clear()
