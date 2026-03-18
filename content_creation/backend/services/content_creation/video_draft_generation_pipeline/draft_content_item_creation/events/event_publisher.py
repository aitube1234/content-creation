"""AG-UI Protocol event publisher for draft content item creation."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class EventPublisher:
    """Emits AG-UI Protocol typed events via astream_events() v2 API.

    All events carry run_id and thread_id correlation identifiers
    aligned to the LangGraph session.
    """

    def __init__(self, run_id: str | None = None, thread_id: str | None = None) -> None:
        self.run_id = run_id or str(uuid.uuid4())
        self.thread_id = thread_id or str(uuid.uuid4())

    def _build_event(self, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
        """Build a typed event dict with correlation identifiers."""
        return {
            "event": event_type,
            "data": data,
            "run_id": self.run_id,
            "thread_id": self.thread_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def emit_draft_created(
        self, content_item_id: uuid.UUID, creator_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Emit event for draft content item creation completion."""
        event = self._build_event(
            "draft_content_item.created",
            {
                "content_item_id": str(content_item_id),
                "creator_id": str(creator_id),
            },
        )
        logger.info("Event emitted: %s for %s", event["event"], content_item_id)
        return event

    async def emit_metadata_pending(
        self, content_item_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Emit event for metadata pending state."""
        event = self._build_event(
            "draft_content_item.metadata_pending",
            {"content_item_id": str(content_item_id)},
        )
        logger.info("Event emitted: %s for %s", event["event"], content_item_id)
        return event

    async def emit_thumbnail_reduced_notice(
        self, content_item_id: uuid.UUID, count: int,
    ) -> dict[str, Any]:
        """Emit event for reduced thumbnail count notification."""
        event = self._build_event(
            "draft_content_item.thumbnail_reduced",
            {
                "content_item_id": str(content_item_id),
                "available_count": count,
            },
        )
        logger.warning("Event emitted: %s for %s (count=%d)", event["event"], content_item_id, count)
        return event

    async def emit_originality_check_status(
        self, content_item_id: uuid.UUID, status: str,
    ) -> dict[str, Any]:
        """Emit event for originality check status update."""
        event = self._build_event(
            "draft_content_item.originality_check_status",
            {
                "content_item_id": str(content_item_id),
                "status": status,
            },
        )
        logger.info("Event emitted: %s for %s (status=%s)", event["event"], content_item_id, status)
        return event

    async def emit_originality_check_timeout(
        self, content_item_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Emit event for originality check timeout notification."""
        event = self._build_event(
            "draft_content_item.originality_check_timeout",
            {"content_item_id": str(content_item_id)},
        )
        logger.warning("Event emitted: %s for %s", event["event"], content_item_id)
        return event

    async def emit_auto_thumbnail_selected(
        self, content_item_id: uuid.UUID, thumbnail_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Emit event for auto-thumbnail selection notification."""
        event = self._build_event(
            "draft_content_item.auto_thumbnail_selected",
            {
                "content_item_id": str(content_item_id),
                "thumbnail_id": str(thumbnail_id),
            },
        )
        logger.info("Event emitted: %s for %s", event["event"], content_item_id)
        return event
