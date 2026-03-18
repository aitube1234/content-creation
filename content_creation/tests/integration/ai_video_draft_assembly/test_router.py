"""Integration tests for AI video draft assembly API endpoints."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import CREATOR_ID, make_jwt_token


class TestSubmitAssemblyEndpoint:
    """POST /v1/video-draft-assembly"""

    @pytest.mark.asyncio
    async def test_submit_validation_error_short_script(self, test_client: AsyncClient):
        """FR-2: Script with fewer than 100 words should be rejected."""
        response = await test_client.post(
            "/v1/video-draft-assembly",
            json={
                "input_type": "script",
                "input_text": " ".join(["word"] * 99),
            },
        )
        assert response.status_code == 422
        data = response.json()
        assert data["error_code"] == "INPUT_VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_submit_validation_error_short_topic(self, test_client: AsyncClient):
        """FR-2: Topic prompt with fewer than 20 words should be rejected."""
        response = await test_client.post(
            "/v1/video-draft-assembly",
            json={
                "input_type": "topic_prompt",
                "input_text": " ".join(["word"] * 19),
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_submit_no_auth(self, test_client: AsyncClient):
        """Unauthenticated request should return 401."""
        from httpx import AsyncClient as AC
        from tests.conftest import create_test_app

        app = create_test_app()
        from httpx import ASGITransport

        transport = ASGITransport(app=app)
        async with AC(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/video-draft-assembly",
                json={
                    "input_type": "script",
                    "input_text": " ".join(["word"] * 150),
                },
            )
            assert response.status_code in (401, 403)


class TestListEndpoint:
    """GET /v1/video-draft-assembly"""

    @pytest.mark.asyncio
    async def test_list_empty(self, test_client: AsyncClient):
        response = await test_client.get("/v1/video-draft-assembly")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 0

    @pytest.mark.asyncio
    async def test_list_with_pagination(self, test_client: AsyncClient):
        response = await test_client.get(
            "/v1/video-draft-assembly?page=1&page_size=5"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 5

    @pytest.mark.asyncio
    async def test_list_with_filters(self, test_client: AsyncClient):
        response = await test_client.get(
            "/v1/video-draft-assembly?lifecycle_state=draft&assembly_status=completed"
        )
        assert response.status_code == 200


class TestGetEndpoint:
    """GET /v1/video-draft-assembly/{content_item_id}"""

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, test_client: AsyncClient):
        response = await test_client.get(
            f"/v1/video-draft-assembly/{uuid.uuid4()}"
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_existing(self, test_client: AsyncClient, sample_content_item):
        response = await test_client.get(
            f"/v1/video-draft-assembly/{sample_content_item.content_item_id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["content_item_id"] == str(sample_content_item.content_item_id)
        assert data["input_type"] == "script"


class TestRetryEndpoint:
    """POST /v1/video-draft-assembly/{content_item_id}/retry"""

    @pytest.mark.asyncio
    async def test_retry_nonexistent(self, test_client: AsyncClient):
        response = await test_client.post(
            f"/v1/video-draft-assembly/{uuid.uuid4()}/retry"
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_retry_not_failed(self, test_client: AsyncClient, sample_content_item):
        """Cannot retry COMPLETED assembly."""
        response = await test_client.post(
            f"/v1/video-draft-assembly/{sample_content_item.content_item_id}/retry"
        )
        assert response.status_code == 409


class TestSceneEditEndpoints:
    """Scene editing endpoints."""

    @pytest.mark.asyncio
    async def test_update_pacing(self, test_client: AsyncClient, sample_content_item):
        response = await test_client.patch(
            f"/v1/video-draft-assembly/{sample_content_item.content_item_id}/scenes/scene-001/pacing",
            json={"pacing_value": 2.0},
        )
        assert response.status_code == 200
        data = response.json()
        # Verify the scene pacing was updated
        scenes = data["scenes"]
        scene = next(s for s in scenes if s["scene_id"] == "scene-001")
        assert scene["pacing_value"] == 2.0

    @pytest.mark.asyncio
    async def test_update_pacing_scene_not_found(self, test_client: AsyncClient, sample_content_item):
        response = await test_client.patch(
            f"/v1/video-draft-assembly/{sample_content_item.content_item_id}/scenes/nonexistent/pacing",
            json={"pacing_value": 2.0},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_swap_visual(self, test_client: AsyncClient, sample_content_item):
        new_visual_id = str(uuid.uuid4())
        response = await test_client.patch(
            f"/v1/video-draft-assembly/{sample_content_item.content_item_id}/scenes/scene-001/visual",
            json={"visual_asset_id": new_visual_id},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_re_record_voice(self, test_client: AsyncClient, sample_content_item):
        response = await test_client.post(
            f"/v1/video-draft-assembly/{sample_content_item.content_item_id}/scenes/scene-001/voice",
            json={"voice_segment_url": "s3://voice/new.mp3"},
        )
        assert response.status_code == 200


class TestMetadataEndpoints:
    """Metadata editing endpoints."""

    @pytest.mark.asyncio
    async def test_update_title(self, test_client: AsyncClient, sample_content_item):
        response = await test_client.patch(
            f"/v1/video-draft-assembly/{sample_content_item.content_item_id}/metadata/title",
            json={"value": "New Title"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ai_title"] == "New Title"

    @pytest.mark.asyncio
    async def test_update_description(self, test_client: AsyncClient, sample_content_item):
        response = await test_client.patch(
            f"/v1/video-draft-assembly/{sample_content_item.content_item_id}/metadata/description",
            json={"value": "New Description"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_tags(self, test_client: AsyncClient, sample_content_item):
        response = await test_client.patch(
            f"/v1/video-draft-assembly/{sample_content_item.content_item_id}/metadata/tags",
            json={"tags": ["tag1", "tag2", "tag3"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ai_tags"] == ["tag1", "tag2", "tag3"]

    @pytest.mark.asyncio
    async def test_update_topic_cluster(self, test_client: AsyncClient, sample_content_item):
        response = await test_client.patch(
            f"/v1/video-draft-assembly/{sample_content_item.content_item_id}/metadata/topic-cluster",
            json={"value": "technologie"},
        )
        assert response.status_code == 200


class TestThumbnailEndpoint:
    """Thumbnail selection endpoint."""

    @pytest.mark.asyncio
    async def test_select_valid_thumbnail(self, test_client: AsyncClient, sample_content_item):
        response = await test_client.post(
            f"/v1/video-draft-assembly/{sample_content_item.content_item_id}/thumbnails/select",
            json={"selected_thumbnail_url": "s3://video-drafts/test/thumbnails/t2.jpg"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["selected_thumbnail_url"] == "s3://video-drafts/test/thumbnails/t2.jpg"

    @pytest.mark.asyncio
    async def test_select_invalid_thumbnail(self, test_client: AsyncClient, sample_content_item):
        response = await test_client.post(
            f"/v1/video-draft-assembly/{sample_content_item.content_item_id}/thumbnails/select",
            json={"selected_thumbnail_url": "s3://invalid/url.jpg"},
        )
        assert response.status_code == 404


class TestStreamEndpoint:
    """SSE streaming endpoint."""

    @pytest.mark.asyncio
    async def test_stream_existing_item(self, test_client: AsyncClient, sample_content_item):
        response = await test_client.get(
            f"/v1/video-draft-assembly/{sample_content_item.content_item_id}/stream"
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_stream_nonexistent(self, test_client: AsyncClient):
        response = await test_client.get(
            f"/v1/video-draft-assembly/{uuid.uuid4()}/stream"
        )
        assert response.status_code == 404


class TestVersionHistoryEndpoint:
    """Version history endpoint."""

    @pytest.mark.asyncio
    async def test_get_version_history(self, test_client: AsyncClient, sample_content_item):
        response = await test_client.get(
            f"/v1/video-draft-assembly/{sample_content_item.content_item_id}/versions"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["content_item_id"] == str(sample_content_item.content_item_id)
        assert "versions" in data
