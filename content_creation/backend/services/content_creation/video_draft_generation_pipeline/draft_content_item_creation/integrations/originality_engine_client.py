"""Client for the Content Originality Engine."""

import asyncio
import logging
import uuid

import httpx

from backend.services.content_creation.config import settings
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.exceptions import (
    OriginalityCheckFailedError,
    OriginalityCheckTimeoutError,
    OriginalityEngineUnavailableError,
)

logger = logging.getLogger(__name__)


class OriginalityEngineClient:
    """HTTP client for the Content Originality Engine.

    Handles retry logic, SLA timeout detection, and structured error responses.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int | None = None,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
    ) -> None:
        self.base_url = base_url or getattr(
            settings, "ORIGINALITY_ENGINE_BASE_URL", "http://localhost:8090"
        )
        self.timeout = timeout or getattr(settings, "ORIGINALITY_SLA_TIMEOUT", 30)
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    async def check_originality(
        self,
        content_item_id: uuid.UUID,
        creator_account_id: uuid.UUID,
    ) -> dict:
        """Invoke the originality check for a content item.

        Returns the report dict on success. Raises on timeout or failure.
        """
        payload = {
            "content_item_id": str(content_item_id),
            "creator_account_id": str(creator_account_id),
        }

        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout)
                ) as client:
                    response = await client.post(
                        f"{self.base_url}/v1/originality/check",
                        json=payload,
                    )
                    response.raise_for_status()
                    logger.info(
                        "Originality check completed for content item %s",
                        content_item_id,
                    )
                    return response.json()
            except httpx.TimeoutException as exc:
                logger.warning(
                    "Originality check timeout for content item %s (attempt %d)",
                    content_item_id,
                    attempt + 1,
                )
                raise OriginalityCheckTimeoutError(
                    message=f"Originality check timed out after {self.timeout}s for content item '{content_item_id}'.",
                ) from exc
            except (httpx.HTTPError, Exception) as exc:
                last_exception = exc
                if attempt < self.max_retries:
                    wait_time = self.backoff_factor ** attempt
                    logger.warning(
                        "Originality check attempt %d failed: %s. Retrying in %.1fs",
                        attempt + 1,
                        exc,
                        wait_time,
                    )
                    await asyncio.sleep(wait_time)

        logger.error(
            "Originality engine unavailable after %d attempts for content item %s",
            self.max_retries + 1,
            content_item_id,
        )
        raise OriginalityEngineUnavailableError(
            message=f"Content Originality Engine unavailable after {self.max_retries + 1} attempts.",
            details=[str(last_exception)] if last_exception else [],
        )

    async def check_availability(self) -> bool:
        """Check if the originality engine is available."""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5)) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False
