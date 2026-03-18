"""Locust load test scenarios for Draft Content Item endpoints.

Targets:
- POST /v1/draft-content-items: Creation endpoint
- GET /v1/draft-content-items: Listing endpoint

Performance targets: >= 500 TPS at sub-200ms p95 latency.
"""

import uuid

from locust import HttpUser, between, task

# JWT token for load testing (replace with a valid token in real environments)
AUTH_TOKEN = "Bearer test-load-test-token"
CREATOR_ID = str(uuid.UUID("11111111-1111-1111-1111-111111111111"))


class DraftContentItemUser(HttpUser):
    """Simulates a creator interacting with Draft Content Item endpoints."""

    wait_time = between(0.1, 0.5)
    host = "http://localhost:8000"

    def on_start(self):
        """Set up authentication headers."""
        self.client.headers = {
            "Authorization": AUTH_TOKEN,
            "Content-Type": "application/json",
        }
        self.created_ids: list[str] = []

    @task(3)
    def create_draft_content_item(self):
        """POST /v1/draft-content-items — create a new draft."""
        payload = {
            "creation_source": "script_to_video",
            "lead_creator_account_id": CREATOR_ID,
            "video_draft_url": f"s3://video-drafts/load-test/{uuid.uuid4()}/video.mp4",
            "pipeline_job_reference": f"load-test-{uuid.uuid4()}",
        }
        with self.client.post(
            "/v1/draft-content-items",
            json=payload,
            catch_response=True,
        ) as response:
            if response.status_code == 201:
                content_item_id = response.json().get("content_item_id")
                if content_item_id:
                    self.created_ids.append(content_item_id)
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(7)
    def list_draft_content_items(self):
        """GET /v1/draft-content-items — list with pagination."""
        with self.client.get(
            "/v1/draft-content-items",
            params={"page": 1, "page_size": 20, "sort_by": "created_at", "sort_order": "desc"},
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(2)
    def get_draft_content_item(self):
        """GET /v1/draft-content-items/{id} — retrieve a single item."""
        if not self.created_ids:
            return
        content_item_id = self.created_ids[-1]
        with self.client.get(
            f"/v1/draft-content-items/{content_item_id}",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")
