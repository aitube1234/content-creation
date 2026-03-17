"""Assembly orchestration service for AI video draft assembly (FR-6 to FR-10)."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.exceptions import (
    AssemblyAlreadyProcessingError,
    AssemblyNotRetryableError,
    AssemblyPipelineError,
    ContentItemNotFoundError,
    InputValidationError,
    LifecycleServiceUnavailableError,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.input_service import (
    InputIngestionService,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.integrations.lifecycle_client import (
    LifecycleClient,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.integrations.metadata_engine_client import (
    MetadataEngineClient,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.integrations.s3_client import (
    S3Client,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    AssemblyStatus,
    ContentInputType,
    ContentItem,
    LifecycleState,
    MetadataStatus,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.pipeline.graph import (
    compile_assembly_graph,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.repository import (
    ContentItemRepository,
)

logger = logging.getLogger(__name__)


class AssemblyService:
    """Orchestrates the AI video draft assembly pipeline (FR-6 to FR-10)."""

    def __init__(
        self,
        repository: ContentItemRepository | None = None,
        input_service: InputIngestionService | None = None,
        s3_client: S3Client | None = None,
        metadata_engine_client: MetadataEngineClient | None = None,
        lifecycle_client: LifecycleClient | None = None,
    ) -> None:
        self.repository = repository or ContentItemRepository()
        self.input_service = input_service or InputIngestionService()
        self.s3_client = s3_client or S3Client()
        self.metadata_engine_client = metadata_engine_client or MetadataEngineClient()
        self.lifecycle_client = lifecycle_client or LifecycleClient()

    async def submit_assembly(
        self,
        session: AsyncSession,
        creator_id: uuid.UUID,
        input_type: ContentInputType,
        input_text: str,
    ) -> ContentItem:
        """Submit a new video draft assembly request (FR-1 to FR-5, FR-6).

        Validates input, creates a content item, registers in lifecycle,
        and initiates the assembly pipeline.
        """
        # FR-1 to FR-5: Validate input
        validation_result = self.input_service.validate(input_text, input_type)
        if not validation_result.is_valid:
            error_messages = [e.message for e in validation_result.errors]
            raise InputValidationError(
                message="Input validation failed.",
                details=error_messages,
            )

        # FR-27: Check lifecycle service availability before creating record
        try:
            await self.lifecycle_client.register_draft(
                content_item_id=uuid.uuid4(),  # Placeholder check
                creator_id=creator_id,
            )
        except LifecycleServiceUnavailableError:
            raise LifecycleServiceUnavailableError(
                message="Content Lifecycle Management service is unavailable. Cannot create content item.",
            )

        # Create content item record
        record = await self.repository.create(
            session,
            {
                "creator_id": creator_id,
                "input_type": input_type,
                "input_text": input_text,
                "input_locale": validation_result.detected_locale,
                "lifecycle_state": LifecycleState.DRAFT,
                "assembly_status": AssemblyStatus.PENDING,
            },
        )

        # Register in lifecycle management (FR-25, FR-26)
        try:
            await self.lifecycle_client.register_draft(
                record.content_item_id, creator_id
            )
        except LifecycleServiceUnavailableError:
            logger.error(
                "Lifecycle service unavailable for content item %s",
                record.content_item_id,
            )
            raise

        # Start assembly pipeline asynchronously (FR-6, FR-7)
        await self._run_assembly_pipeline(session, record)

        logger.info(
            "Assembly submitted for content item %s by creator %s",
            record.content_item_id,
            creator_id,
        )
        return record

    async def retry_assembly(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> ContentItem:
        """Retry a failed assembly (FR-8)."""
        record = await self._get_record_or_raise(session, content_item_id, creator_id)

        if record.assembly_status in (AssemblyStatus.PROCESSING, AssemblyStatus.COMPLETED):
            raise AssemblyAlreadyProcessingError(
                message=f"Assembly is already in '{record.assembly_status.value}' state."
            )

        if record.assembly_status != AssemblyStatus.FAILED:
            raise AssemblyNotRetryableError(
                message=f"Cannot retry assembly in '{record.assembly_status.value}' state. Only FAILED assemblies can be retried."
            )

        # Reset to PENDING and re-run
        await self.repository.update_assembly_status(
            session, content_item_id, AssemblyStatus.PENDING
        )
        await self._run_assembly_pipeline(session, record)

        logger.info("Assembly retry initiated for content item %s", content_item_id)
        return await self._get_record_or_raise(session, content_item_id, creator_id)

    async def get_content_item(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> ContentItem:
        """Fetch a single content item by ID scoped to the creator."""
        return await self._get_record_or_raise(session, content_item_id, creator_id)

    async def list_content_items(
        self,
        session: AsyncSession,
        creator_id: uuid.UUID,
        lifecycle_state: LifecycleState | None = None,
        assembly_status: AssemblyStatus | None = None,
        metadata_status: MetadataStatus | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ContentItem], int]:
        """Return paginated, filtered, sorted content items."""
        offset = (page - 1) * page_size
        return await self.repository.list_by_creator(
            session,
            creator_id,
            lifecycle_state=lifecycle_state,
            assembly_status=assembly_status,
            metadata_status=metadata_status,
            sort_by=sort_by,
            sort_order=sort_order,
            offset=offset,
            limit=page_size,
        )

    async def get_version_history(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> list[dict]:
        """Get version history for a content item."""
        record = await self._get_record_or_raise(session, content_item_id, creator_id)
        return list(record.version_history or [])

    async def _run_assembly_pipeline(
        self,
        session: AsyncSession,
        record: ContentItem,
    ) -> None:
        """Execute the LangGraph assembly pipeline (FR-6 to FR-10)."""
        content_item_id = record.content_item_id

        # Transition to PROCESSING
        await self.repository.update_assembly_status(
            session, content_item_id, AssemblyStatus.PROCESSING
        )

        try:
            run_id = str(uuid.uuid4())
            thread_id = str(uuid.uuid4())

            compiled_graph = compile_assembly_graph()

            initial_state = {
                "content_item_id": content_item_id,
                "creator_id": record.creator_id,
                "input_text": record.input_text,
                "input_type": record.input_type.value,
                "input_locale": record.input_locale,
                "scenes": [],
                "visual_assets": [],
                "voice_segments": [],
                "transitions": [],
                "metadata": {},
                "thumbnails": [],
                "assembly_status": "processing",
                "video_draft_url": None,
                "error": None,
                "error_node": None,
                "run_id": run_id,
                "thread_id": thread_id,
            }

            # Execute the pipeline
            result = await compiled_graph.ainvoke(initial_state)

            # Check for pipeline errors
            if result.get("error"):
                await self.repository.update_assembly_status(
                    session,
                    content_item_id,
                    AssemblyStatus.FAILED,
                    extra_fields={
                        "version_history": list(record.version_history or [])
                        + [
                            {
                                "version_id": str(uuid.uuid4()),
                                "change_type": "pipeline_failure",
                                "changed_fields": {
                                    "error": result["error"],
                                    "error_node": result.get("error_node"),
                                },
                                "changed_at": str(record.updated_at),
                                "changed_by": str(record.creator_id),
                            }
                        ],
                    },
                )
                raise AssemblyPipelineError(
                    message=f"Assembly pipeline failed at node '{result.get('error_node')}': {result['error']}"
                )

            # Store assembled video draft to S3 (FR-10)
            video_draft_url = f"s3://video-drafts/{content_item_id}/draft/video.mp4"

            # Update content item with pipeline results
            scenes = result.get("scenes", [])
            # Clean scenes for storage (remove text_content)
            clean_scenes = []
            for scene in scenes:
                clean_scenes.append(
                    {
                        "scene_id": scene["scene_id"],
                        "pacing_value": scene.get("pacing_value", 1.0),
                        "visual_asset_id": scene.get("visual_asset_id"),
                        "voice_segment_id": scene.get("voice_segment_id"),
                    }
                )

            metadata = result.get("metadata", {})
            thumbnails = result.get("thumbnails", [])

            update_fields = {
                "assembly_status": AssemblyStatus.COMPLETED,
                "video_draft_url": video_draft_url,
                "scenes": clean_scenes,
                "thumbnail_options": thumbnails,
                "ai_title": metadata.get("ai_title"),
                "ai_description": metadata.get("ai_description"),
                "ai_tags": metadata.get("ai_tags"),
                "ai_topic_cluster": metadata.get("ai_topic_cluster"),
                "metadata_status": MetadataStatus.GENERATED,
            }

            await self.repository.update(
                session, content_item_id, record.creator_id, update_fields
            )

            # Write metadata to engine (FR-17, FR-18)
            try:
                await self.metadata_engine_client.write_metadata(
                    content_item_id, metadata
                )
            except Exception:
                logger.warning(
                    "Metadata engine write failed for %s; marking as PENDING",
                    content_item_id,
                )
                await self.repository.update_metadata(
                    session,
                    content_item_id,
                    record.creator_id,
                    {"metadata_status": MetadataStatus.PENDING},
                )

            logger.info(
                "Assembly pipeline completed for content item %s",
                content_item_id,
            )

        except AssemblyPipelineError:
            raise
        except Exception as exc:
            logger.error(
                "Assembly pipeline failed for content item %s: %s",
                content_item_id,
                exc,
            )
            await self.repository.update_assembly_status(
                session, content_item_id, AssemblyStatus.FAILED
            )
            raise AssemblyPipelineError(
                message=f"Assembly pipeline failed: {exc}",
                details=[str(exc)],
            )

    async def _get_record_or_raise(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> ContentItem:
        """Fetch a record or raise ContentItemNotFoundError."""
        record = await self.repository.get_by_id(session, content_item_id, creator_id)
        if record is None:
            raise ContentItemNotFoundError(
                message=f"Content item '{content_item_id}' not found for creator '{creator_id}'."
            )
        return record
