"""Client for Content Lifecycle Management state machine."""

import asyncio
import logging
import uuid

import httpx

from backend.services.content_creation.config import settings
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.exceptions import (
    LifecycleServiceUnavailableError,
)

logger = logging.getLogger(__name__)


class LifecycleClient:
    """Registers content items in the Content Lifecycle Management state machine.

    Handles service unavailability with structured error propagation.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
    ) -> None:
        self.base_url = base_url or getattr(
            settings, "LIFECYCLE_SERVICE_BASE_URL", "http://localhost:8003"
        )
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    async def register_draft(
        self,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> bool:
        """Register a new Draft content item in the lifecycle state machine.

        Returns True on success. Raises LifecycleServiceUnavailableError
        if the service is unavailable after retries.
        """
        payload = {
            "content_item_id": str(content_item_id),
            "creator_id": str(creator_id),
            "lifecycle_state": "draft",
        }

        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout)
                ) as client:
                    response = await client.post(
                        f"{self.base_url}/v1/lifecycle/register",
                        json=payload,
                    )
                    response.raise_for_status()
                    logger.info(
                        "Registered draft content item %s in lifecycle service",
                        content_item_id,
                    )
                    return True
            except (httpx.HTTPError, Exception) as exc:
                last_exception = exc
                if attempt < self.max_retries:
                    wait_time = self.backoff_factor ** attempt
                    logger.warning(
                        "Lifecycle registration attempt %d failed: %s. Retrying in %.1fs",
                        attempt + 1,
                        exc,
                        wait_time,
                    )
                    await asyncio.sleep(wait_time)

        logger.error(
            "Lifecycle service unavailable after %d attempts for content item %s",
            self.max_retries + 1,
            content_item_id,
        )
        raise LifecycleServiceUnavailableError(
            message=f"Content Lifecycle Management service is unavailable after {self.max_retries + 1} attempts.",
            details=[str(last_exception)] if last_exception else [],
        )

    async def check_availability(self) -> bool:
        """Check if the lifecycle service is available."""
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(5)
            ) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False
