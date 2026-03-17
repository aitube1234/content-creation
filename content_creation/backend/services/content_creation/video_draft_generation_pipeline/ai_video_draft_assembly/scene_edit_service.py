"""Scene-level editing service (FR-11 to FR-16)."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.exceptions import (
    ContentItemNotFoundError,
    MicrophonePermissionError,
    SceneNotFoundError,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    ContentItem,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.repository import (
    ContentItemRepository,
)

logger = logging.getLogger(__name__)


class SceneEditService:
    """Manages scene-level editing operations (FR-11 to FR-16)."""

    def __init__(
        self,
        repository: ContentItemRepository | None = None,
    ) -> None:
        self.repository = repository or ContentItemRepository()

    async def update_pacing(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
        scene_id: str,
        pacing_value: float,
    ) -> ContentItem:
        """Adjust pacing for a specific scene (FR-12).

        Updates scene duration based on pacing_value. Appends version history entry.
        """
        record = await self._get_record_or_raise(session, content_item_id, creator_id)
        scenes = list(record.scenes or [])
        scene, scene_idx = self._find_scene(scenes, scene_id, content_item_id)

        old_pacing = scene.get("pacing_value", 1.0)
        scene["pacing_value"] = pacing_value
        scenes[scene_idx] = scene

        await self.repository.update_scenes(session, content_item_id, creator_id, scenes)
        await self._append_version_entry(
            session,
            content_item_id,
            creator_id,
            "pacing_adjustment",
            {"scene_id": scene_id, "old_pacing": old_pacing, "new_pacing": pacing_value},
        )

        logger.info(
            "Updated pacing for scene %s in content item %s: %s -> %s",
            scene_id, content_item_id, old_pacing, pacing_value,
        )
        return await self._get_record_or_raise(session, content_item_id, creator_id)

    async def swap_visual(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
        scene_id: str,
        visual_asset_id: str,
    ) -> ContentItem:
        """Swap the visual asset for a specific scene (FR-13).

        Replaces the AI-selected visual for the scene. Appends version history entry.
        """
        record = await self._get_record_or_raise(session, content_item_id, creator_id)
        scenes = list(record.scenes or [])
        scene, scene_idx = self._find_scene(scenes, scene_id, content_item_id)

        old_visual = scene.get("visual_asset_id")
        scene["visual_asset_id"] = visual_asset_id
        scenes[scene_idx] = scene

        await self.repository.update_scenes(session, content_item_id, creator_id, scenes)
        await self._append_version_entry(
            session,
            content_item_id,
            creator_id,
            "visual_swap",
            {"scene_id": scene_id, "old_visual": old_visual, "new_visual": visual_asset_id},
        )

        logger.info(
            "Swapped visual for scene %s in content item %s",
            scene_id, content_item_id,
        )
        return await self._get_record_or_raise(session, content_item_id, creator_id)

    async def re_record_voice(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
        scene_id: str,
        voice_segment_url: str,
        has_microphone_access: bool = True,
    ) -> ContentItem:
        """Re-record voice for a specific scene (FR-14, FR-15).

        Accepts a creator-recorded voice segment URL. Replaces the AI-generated
        voice_segment_id. Appends version history entry.
        """
        # FR-15: Check microphone permission
        if not has_microphone_access:
            raise MicrophonePermissionError(
                message="Microphone access is required for voice re-recording. "
                "Please grant microphone permissions in your browser settings.",
                details=["microphone_permission_denied"],
            )

        record = await self._get_record_or_raise(session, content_item_id, creator_id)
        scenes = list(record.scenes or [])
        scene, scene_idx = self._find_scene(scenes, scene_id, content_item_id)

        old_voice = scene.get("voice_segment_id")
        new_voice_id = str(uuid.uuid4())
        scene["voice_segment_id"] = new_voice_id
        scenes[scene_idx] = scene

        await self.repository.update_scenes(session, content_item_id, creator_id, scenes)
        await self._append_version_entry(
            session,
            content_item_id,
            creator_id,
            "voice_re_recording",
            {
                "scene_id": scene_id,
                "old_voice": old_voice,
                "new_voice": new_voice_id,
                "voice_segment_url": voice_segment_url,
            },
        )

        logger.info(
            "Re-recorded voice for scene %s in content item %s",
            scene_id, content_item_id,
        )
        return await self._get_record_or_raise(session, content_item_id, creator_id)

    def _find_scene(
        self, scenes: list[dict], scene_id: str, content_item_id: uuid.UUID
    ) -> tuple[dict, int]:
        """Find a scene by scene_id. Raises SceneNotFoundError if not found (FR-11)."""
        for idx, scene in enumerate(scenes):
            if scene.get("scene_id") == scene_id:
                return scene, idx
        raise SceneNotFoundError(
            message=f"Scene '{scene_id}' not found in content item '{content_item_id}'."
        )

    async def _append_version_entry(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
        change_type: str,
        changed_fields: dict,
    ) -> None:
        """Append a version entry to the content item's version history (FR-16)."""
        entry = {
            "version_id": str(uuid.uuid4()),
            "change_type": change_type,
            "changed_fields": changed_fields,
            "changed_at": datetime.now(timezone.utc).isoformat(),
            "changed_by": str(creator_id),
        }
        await self.repository.append_version_history(
            session, content_item_id, creator_id, entry
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
