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
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    AssemblyStatus,
    ContentInputType,
    ContentItem,
    LifecycleState,
    MetadataStatus,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.repository import (
    ContentItemRepository,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.service import (
    AssemblyService,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.integrations.s3_client import (
    S3Client,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.integrations.metadata_engine_client import (
    MetadataEngineClient,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.integrations.lifecycle_client import (
    LifecycleClient,
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


# --- AI Video Draft Assembly fixtures ---


@pytest_asyncio.fixture
async def sample_content_item(async_session: AsyncSession) -> ContentItem:
    """Create and return a sample content item in DRAFT/COMPLETED state."""
    record = ContentItem(
        content_item_id=uuid.uuid4(),
        creator_id=CREATOR_ID,
        input_type=ContentInputType.SCRIPT,
        input_text=" ".join(["word"] * 150),
        input_locale="fr",
        lifecycle_state=LifecycleState.DRAFT,
        assembly_status=AssemblyStatus.COMPLETED,
        video_draft_url="s3://video-drafts/test/draft/video.mp4",
        scenes=[
            {
                "scene_id": "scene-001",
                "pacing_value": 1.0,
                "visual_asset_id": "visual-001",
                "voice_segment_id": "voice-001",
            },
            {
                "scene_id": "scene-002",
                "pacing_value": 1.0,
                "visual_asset_id": "visual-002",
                "voice_segment_id": "voice-002",
            },
        ],
        metadata_status=MetadataStatus.GENERATED,
        ai_title="Test Title",
        ai_description="Test Description",
        ai_tags=["test", "video"],
        ai_topic_cluster="general",
        thumbnail_options=[
            "s3://video-drafts/test/thumbnails/t1.jpg",
            "s3://video-drafts/test/thumbnails/t2.jpg",
            "s3://video-drafts/test/thumbnails/t3.jpg",
        ],
        selected_thumbnail_url=None,
        version_history=[],
        word_count=150,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    async_session.add(record)
    await async_session.commit()
    return record


@pytest.fixture
def content_item_repository() -> ContentItemRepository:
    """Provide a ContentItemRepository instance."""
    return ContentItemRepository()


@pytest.fixture
def mock_s3_client() -> AsyncMock:
    """Provide a mocked S3 client."""
    client = AsyncMock(spec=S3Client)
    client.upload_video_draft = AsyncMock(return_value="s3://video-drafts/test/draft/video.mp4")
    client.upload_visual_asset = AsyncMock(return_value="s3://video-drafts/test/visuals/v.mp4")
    client.upload_voice_segment = AsyncMock(return_value="s3://video-drafts/test/voice/v.mp3")
    client.upload_thumbnail = AsyncMock(return_value="s3://video-drafts/test/thumbnails/t.jpg")
    return client


@pytest.fixture
def mock_metadata_engine_client() -> AsyncMock:
    """Provide a mocked metadata engine client."""
    client = AsyncMock(spec=MetadataEngineClient)
    client.write_metadata = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_lifecycle_client() -> AsyncMock:
    """Provide a mocked lifecycle client."""
    client = AsyncMock(spec=LifecycleClient)
    client.register_draft = AsyncMock(return_value=True)
    client.check_availability = AsyncMock(return_value=True)
    return client


@pytest.fixture
def assembly_service(
    mock_s3_client: AsyncMock,
    mock_metadata_engine_client: AsyncMock,
    mock_lifecycle_client: AsyncMock,
) -> AssemblyService:
    """Provide an AssemblyService with mocked external clients."""
    return AssemblyService(
        s3_client=mock_s3_client,
        metadata_engine_client=mock_metadata_engine_client,
        lifecycle_client=mock_lifecycle_client,
    )


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
