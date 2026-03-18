"""Integration tests for Draft Content Item API endpoints."""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import CREATOR_ID, CONTRIBUTOR_ID, make_jwt_token


@pytest.mark.asyncio
async def test_create_draft_content_item(test_client: AsyncClient):
    """Test POST /v1/draft-content-items creates a Draft record."""
    response = await test_client.post(
        "/v1/draft-content-items",
        json={
            "creation_source": "script_to_video",
            "lead_creator_account_id": str(CREATOR_ID),
            "video_draft_url": "s3://video-drafts/test/draft/video.mp4",
            "pipeline_job_reference": "pipeline-job-123",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["lifecycle_state"] == "draft"
    assert data["creation_source"] == "script_to_video"
    assert data["video_draft_url"] == "s3://video-drafts/test/draft/video.mp4"
    assert "content_item_id" in data


@pytest.mark.asyncio
async def test_list_draft_content_items(test_client: AsyncClient):
    """Test GET /v1/draft-content-items returns paginated results."""
    # Create a draft first
    await test_client.post(
        "/v1/draft-content-items",
        json={
            "creation_source": "script_to_video",
            "lead_creator_account_id": str(CREATOR_ID),
            "video_draft_url": "s3://video-drafts/test/draft/video.mp4",
        },
    )

    response = await test_client.get(
        "/v1/draft-content-items",
        params={"page": 1, "page_size": 20},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "has_next" in data
    assert "has_previous" in data


@pytest.mark.asyncio
async def test_get_draft_content_item(test_client: AsyncClient):
    """Test GET /v1/draft-content-items/{id} returns a full record."""
    create_response = await test_client.post(
        "/v1/draft-content-items",
        json={
            "creation_source": "co_creator_workspace",
            "lead_creator_account_id": str(CREATOR_ID),
            "video_draft_url": "s3://workspace/video.mp4",
        },
    )
    content_item_id = create_response.json()["content_item_id"]

    response = await test_client.get(f"/v1/draft-content-items/{content_item_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["content_item_id"] == content_item_id


@pytest.mark.asyncio
async def test_get_draft_not_found(test_client: AsyncClient):
    """Test GET /v1/draft-content-items/{id} returns 404 for missing record."""
    fake_id = str(uuid.uuid4())
    response = await test_client.get(f"/v1/draft-content-items/{fake_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["error_code"] == "DRAFT_CONTENT_ITEM_NOT_FOUND"


@pytest.mark.asyncio
async def test_delete_draft_content_item(test_client: AsyncClient):
    """Test DELETE /v1/draft-content-items/{id} removes the record."""
    create_response = await test_client.post(
        "/v1/draft-content-items",
        json={
            "creation_source": "script_to_video",
            "lead_creator_account_id": str(CREATOR_ID),
            "video_draft_url": "s3://video-drafts/test/draft/video.mp4",
        },
    )
    content_item_id = create_response.json()["content_item_id"]

    response = await test_client.delete(f"/v1/draft-content-items/{content_item_id}")
    assert response.status_code == 204

    # Verify it's gone
    response = await test_client.get(f"/v1/draft-content-items/{content_item_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_with_filters(test_client: AsyncClient):
    """Test list endpoint with lifecycle_state and creation_source filters."""
    await test_client.post(
        "/v1/draft-content-items",
        json={
            "creation_source": "script_to_video",
            "lead_creator_account_id": str(CREATOR_ID),
            "video_draft_url": "s3://video1.mp4",
        },
    )

    response = await test_client.get(
        "/v1/draft-content-items",
        params={
            "lifecycle_state": "draft",
            "creation_source": "script_to_video",
        },
    )
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["lifecycle_state"] == "draft"
        assert item["creation_source"] == "script_to_video"


@pytest.mark.asyncio
async def test_version_history_endpoint(test_client: AsyncClient):
    """Test GET /v1/draft-content-items/{id}/version-history returns entries."""
    create_response = await test_client.post(
        "/v1/draft-content-items",
        json={
            "creation_source": "script_to_video",
            "lead_creator_account_id": str(CREATOR_ID),
            "video_draft_url": "s3://video.mp4",
        },
    )
    content_item_id = create_response.json()["content_item_id"]

    response = await test_client.get(
        f"/v1/draft-content-items/{content_item_id}/version-history",
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    # Should have at least the draft_created entry
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_thumbnails_endpoint(test_client: AsyncClient):
    """Test GET /v1/draft-content-items/{id}/thumbnails returns thumbnail list."""
    create_response = await test_client.post(
        "/v1/draft-content-items",
        json={
            "creation_source": "script_to_video",
            "lead_creator_account_id": str(CREATOR_ID),
            "video_draft_url": "s3://video.mp4",
        },
    )
    content_item_id = create_response.json()["content_item_id"]

    response = await test_client.get(
        f"/v1/draft-content-items/{content_item_id}/thumbnails",
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_unauthorized_request(test_client: AsyncClient):
    """Test endpoints require authentication."""
    from httpx import ASGITransport, AsyncClient as HttpxClient
    from backend.services.content_creation.main import app

    transport = ASGITransport(app=app)
    async with HttpxClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/draft-content-items")
        assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_error_response_format(test_client: AsyncClient):
    """Test consistent error response format."""
    fake_id = str(uuid.uuid4())
    response = await test_client.get(f"/v1/draft-content-items/{fake_id}")
    assert response.status_code == 404
    data = response.json()
    assert "error_code" in data
    assert "message" in data
    assert "details" in data
