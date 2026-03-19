"""HTTP client for the downstream video generation pipeline service."""

import asyncio
import logging
import uuid

import httpx

from backend.services.content_creation.config import settings
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.exceptions import (
    PipelineUnavailableError,
)
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.models import (
    InputType,
)

logger = logging.getLogger(__name__)


class VideoGenerationPipelineClient:
    """Submits validated input records to the downstream pipeline."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
        backoff_factor: float | None = None,
    ) -> None:
        self.base_url = base_url or settings.PIPELINE_BASE_URL
        self.timeout = timeout if timeout is not None else settings.PIPELINE_TIMEOUT
        self.max_retries = max_retries if max_retries is not None else settings.PIPELINE_MAX_RETRIES
        self.backoff_factor = backoff_factor if backoff_factor is not None else settings.PIPELINE_BACKOFF_FACTOR

    async def submit_for_generation(
        self,
        input_record_id: uuid.UUID,
        input_type: InputType,
        content_text: str,
    ) -> uuid.UUID:
        """Submit content to the pipeline and return the generation_request_id."""
        payload = {
            "input_record_id": str(input_record_id),
            "input_type": input_type.value,
            "content_text": content_text,
        }

        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout)
                ) as client:
                    response = await client.post(
                        f"{self.base_url}/v1/generate",
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()
                    generation_request_id = uuid.UUID(data["generation_request_id"])
                    logger.info(
                        "Pipeline accepted generation request %s for input %s",
                        generation_request_id,
                        input_record_id,
                    )
                    return generation_request_id
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                last_exception = exc
                if attempt < self.max_retries:
                    wait_time = self.backoff_factor ** attempt
                    logger.warning(
                        "Pipeline request attempt %d failed: %s. Retrying in %.1fs",
                        attempt + 1,
                        exc,
                        wait_time,
                    )
                    await asyncio.sleep(wait_time)

        logger.error(
            "Pipeline unavailable after %d attempts for input %s",
            self.max_retries + 1,
            input_record_id,
        )
        raise PipelineUnavailableError(
            message=f"Video generation pipeline is unavailable after {self.max_retries + 1} attempts.",
            details=[str(last_exception)] if last_exception else [],
        )
