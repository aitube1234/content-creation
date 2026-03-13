"""Integration tests for script prompt ingestion API endpoints."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import CREATOR_ID, make_jwt_token


@pytest_asyncio.fixture
async def client(async_session: AsyncSession) -> AsyncClient:
    """Create a test client with session and pipeline mocked."""
    from backend.services.content_creation.database import get_async_session
    from backend.services.content_creation.main import app

    async def override_session():
        yield async_session

    app.dependency_overrides[get_async_session] = override_session

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {make_jwt_token()}"},
    ) as c:
        yield c
    app.dependency_overrides.clear()


def _create_payload(
    content_text: str = "This is valid test content for API testing.",
    input_type: str | None = "written_script",
) -> dict:
    payload: dict = {
        "content_text": content_text,
        "creator_id": str(CREATOR_ID),
    }
    if input_type is not None:
        payload["input_type"] = input_type
    return payload


class TestCreateEndpoint:
    @pytest.mark.asyncio
    async def test_creates_draft_201(self, client: AsyncClient):
        response = await client.post(
            "/v1/script-prompt-inputs",
            json=_create_payload(),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["workflow_state"] == "draft"
        assert data["content_text"] == "This is valid test content for API testing."

    @pytest.mark.asyncio
    async def test_auth_failure_401(self, async_session):
        from backend.services.content_creation.database import get_async_session
        from backend.services.content_creation.main import app

        async def override_session():
            yield async_session

        app.dependency_overrides[get_async_session] = override_session
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": "Bearer invalid-token"},
        ) as c:
            response = await c.post(
                "/v1/script-prompt-inputs",
                json=_create_payload(),
            )
            assert response.status_code == 401
        app.dependency_overrides.clear()


class TestGetEndpoint:
    @pytest.mark.asyncio
    async def test_get_existing_record(self, client: AsyncClient):
        create_resp = await client.post(
            "/v1/script-prompt-inputs",
            json=_create_payload(),
        )
        record_id = create_resp.json()["input_record_id"]

        response = await client.get(f"/v1/script-prompt-inputs/{record_id}")
        assert response.status_code == 200
        assert response.json()["input_record_id"] == record_id

    @pytest.mark.asyncio
    async def test_not_found_404(self, client: AsyncClient):
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/v1/script-prompt-inputs/{fake_id}")
        assert response.status_code == 404


class TestUpdateEndpoint:
    @pytest.mark.asyncio
    async def test_updates_draft(self, client: AsyncClient):
        create_resp = await client.post(
            "/v1/script-prompt-inputs",
            json=_create_payload(),
        )
        record_id = create_resp.json()["input_record_id"]

        response = await client.patch(
            f"/v1/script-prompt-inputs/{record_id}",
            json={"content_text": "Updated content for the test."},
        )
        assert response.status_code == 200
        assert response.json()["content_text"] == "Updated content for the test."


class TestDeleteEndpoint:
    @pytest.mark.asyncio
    async def test_deletes_draft_204(self, client: AsyncClient):
        create_resp = await client.post(
            "/v1/script-prompt-inputs",
            json=_create_payload(),
        )
        record_id = create_resp.json()["input_record_id"]

        response = await client.delete(f"/v1/script-prompt-inputs/{record_id}")
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_nonexistent_404(self, client: AsyncClient):
        fake_id = str(uuid.uuid4())
        response = await client.delete(f"/v1/script-prompt-inputs/{fake_id}")
        assert response.status_code == 404


class TestSubmitEndpoint:
    @pytest.mark.asyncio
    async def test_submit_validation_failure(self, client: AsyncClient):
        """Submit with short content should result in validation_failed state."""
        create_resp = await client.post(
            "/v1/script-prompt-inputs",
            json={
                "content_text": "short",
                "creator_id": str(CREATOR_ID),
                "input_type": "written_script",
            },
        )
        record_id = create_resp.json()["input_record_id"]

        response = await client.post(
            f"/v1/script-prompt-inputs/{record_id}/submit"
        )
        assert response.status_code == 200
        assert response.json()["workflow_state"] == "validation_failed"

    @pytest.mark.asyncio
    @patch(
        "backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.pipeline_client.VideoGenerationPipelineClient.submit_for_generation"
    )
    async def test_submit_happy_path(self, mock_pipeline, client: AsyncClient):
        """Submit with valid content and mocked pipeline should succeed."""
        gen_id = uuid.uuid4()
        mock_pipeline.return_value = gen_id

        create_resp = await client.post(
            "/v1/script-prompt-inputs",
            json=_create_payload(),
        )
        record_id = create_resp.json()["input_record_id"]

        response = await client.post(
            f"/v1/script-prompt-inputs/{record_id}/submit"
        )
        assert response.status_code == 200
        assert response.json()["workflow_state"] == "generation_initiated"
        assert response.json()["generation_request_id"] == str(gen_id)


class TestRevertEndpoint:
    @pytest.mark.asyncio
    async def test_revert_validation_failed_to_draft(self, client: AsyncClient):
        # Create and submit (will fail validation due to missing type)
        create_resp = await client.post(
            "/v1/script-prompt-inputs",
            json={
                "content_text": "short",
                "creator_id": str(CREATOR_ID),
                "input_type": "written_script",
            },
        )
        record_id = create_resp.json()["input_record_id"]

        await client.post(f"/v1/script-prompt-inputs/{record_id}/submit")

        response = await client.post(
            f"/v1/script-prompt-inputs/{record_id}/revert"
        )
        assert response.status_code == 200
        assert response.json()["workflow_state"] == "draft"

    @pytest.mark.asyncio
    async def test_revert_draft_fails_409(self, client: AsyncClient):
        create_resp = await client.post(
            "/v1/script-prompt-inputs",
            json=_create_payload(),
        )
        record_id = create_resp.json()["input_record_id"]

        response = await client.post(
            f"/v1/script-prompt-inputs/{record_id}/revert"
        )
        assert response.status_code == 409


class TestDuplicateEndpoint:
    @pytest.mark.asyncio
    async def test_duplicates_record_201(self, client: AsyncClient):
        create_resp = await client.post(
            "/v1/script-prompt-inputs",
            json=_create_payload(),
        )
        record_id = create_resp.json()["input_record_id"]

        response = await client.post(
            f"/v1/script-prompt-inputs/{record_id}/duplicate"
        )
        assert response.status_code == 201
        data = response.json()
        assert data["input_record_id"] != record_id
        assert data["workflow_state"] == "draft"
        assert data["content_text"] == "This is valid test content for API testing."


class TestListEndpoint:
    @pytest.mark.asyncio
    async def test_list_returns_paginated(self, client: AsyncClient):
        for i in range(3):
            await client.post(
                "/v1/script-prompt-inputs",
                json=_create_payload(content_text=f"Content for list test number {i}."),
            )

        response = await client.get(
            "/v1/script-prompt-inputs",
            params={"page": 1, "page_size": 2},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] >= 3
        assert data["has_next"] is True

    @pytest.mark.asyncio
    async def test_list_filters_by_input_type(self, client: AsyncClient):
        await client.post(
            "/v1/script-prompt-inputs",
            json=_create_payload(input_type="written_script"),
        )
        await client.post(
            "/v1/script-prompt-inputs",
            json=_create_payload(input_type="topic_outline"),
        )

        response = await client.get(
            "/v1/script-prompt-inputs",
            params={"input_type": "topic_outline"},
        )
        assert response.status_code == 200
        for item in response.json()["items"]:
            assert item["input_type"] == "topic_outline"
