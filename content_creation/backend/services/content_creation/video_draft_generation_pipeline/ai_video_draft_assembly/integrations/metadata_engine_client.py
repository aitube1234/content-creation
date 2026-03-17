"""Client for Content Metadata Engine write operations."""

import asyncio
import logging
import uuid

import httpx

from backend.services.content_creation.config import settings
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.exceptions import (
    MetadataEngineWriteError,
)

logger = logging.getLogger(__name__)


class MetadataEngineClient:
    """Writes generated metadata to the Content Metadata Engine.

    Handles write failures with retry queue and metadata_status flag management.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
    ) -> None:
        self.base_url = base_url or getattr(
            settings, "METADATA_ENGINE_BASE_URL", "http://localhost:8002"
        )
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    async def write_metadata(
        self,
        content_item_id: uuid.UUID,
        metadata: dict,
    ) -> bool:
        """Write metadata to the Content Metadata Engine.

        Returns True on success. Raises MetadataEngineWriteError on failure
        after exhausting retries.
        """
        payload = {
            "content_item_id": str(content_item_id),
            "ai_title": metadata.get("ai_title"),
            "ai_description": metadata.get("ai_description"),
            "ai_tags": metadata.get("ai_tags"),
            "ai_topic_cluster": metadata.get("ai_topic_cluster"),
        }

        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout)
                ) as client:
                    response = await client.post(
                        f"{self.base_url}/v1/metadata",
                        json=payload,
                    )
                    response.raise_for_status()
                    logger.info(
                        "Metadata written to engine for content item %s",
                        content_item_id,
                    )
                    return True
            except (httpx.HTTPError, Exception) as exc:
                last_exception = exc
                if attempt < self.max_retries:
                    wait_time = self.backoff_factor ** attempt
                    logger.warning(
                        "Metadata engine write attempt %d failed: %s. Retrying in %.1fs",
                        attempt + 1,
                        exc,
                        wait_time,
                    )
                    await asyncio.sleep(wait_time)

        logger.error(
            "Metadata engine write failed after %d attempts for content item %s",
            self.max_retries + 1,
            content_item_id,
        )
        raise MetadataEngineWriteError(
            message=f"Failed to write metadata after {self.max_retries + 1} attempts.",
            details=[str(last_exception)] if last_exception else [],
        )
