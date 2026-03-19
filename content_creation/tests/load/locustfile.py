"""Locust load test for AI video draft assembly endpoints.

Targets:
- POST /v1/video-draft-assembly (assembly submission)
- GET /v1/video-draft-assembly/{id}/stream (SSE streaming)

Performance targets:
- >= 500 TPS throughput
- sub-200ms p95 latency
"""

import uuid

from locust import HttpUser, between, task


class VideoDraftAssemblyUser(HttpUser):
    """Simulates a creator using the AI video draft assembly API."""

    wait_time = between(0.1, 0.5)
    host = "http://localhost:8000"

    def on_start(self):
        """Set up authentication headers."""
        self.headers = {
            "Authorization": "Bearer test-token",
            "Content-Type": "application/json",
        }
        self.content_item_ids: list[str] = []

    @task(3)
    def submit_assembly(self):
        """Submit a new video draft assembly request."""
        payload = {
            "input_type": "script",
            "input_text": " ".join(["bonjour"] * 150),
        }
        with self.client.post(
            "/v1/video-draft-assembly",
            json=payload,
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 201:
                data = response.json()
                self.content_item_ids.append(data["content_item_id"])
                response.success()
            elif response.status_code == 422:
                response.success()  # Validation errors are expected
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(5)
    def list_content_items(self):
        """List content items with pagination."""
        with self.client.get(
            "/v1/video-draft-assembly?page=1&page_size=20",
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(3)
    def get_content_item(self):
        """Get a specific content item."""
        if not self.content_item_ids:
            return
        content_item_id = self.content_item_ids[-1]
        with self.client.get(
            f"/v1/video-draft-assembly/{content_item_id}",
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code in (200, 404):
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(2)
    def stream_assembly_status(self):
        """Stream assembly status via SSE."""
        if not self.content_item_ids:
            return
        content_item_id = self.content_item_ids[-1]
        with self.client.get(
            f"/v1/video-draft-assembly/{content_item_id}/stream",
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code in (200, 404):
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def get_version_history(self):
        """Get version history for a content item."""
        if not self.content_item_ids:
            return
        content_item_id = self.content_item_ids[-1]
        with self.client.get(
            f"/v1/video-draft-assembly/{content_item_id}/versions",
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code in (200, 404):
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")
