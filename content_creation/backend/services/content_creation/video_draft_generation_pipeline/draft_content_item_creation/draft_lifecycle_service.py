"""Service for draft content item lifecycle transitions."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    LifecycleState,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.enums import (
    ReportStatus,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.exceptions import (
    ContributorAccessDeniedError,
    DraftContentItemNotFoundError,
    InvalidLifecycleTransitionError,
    OriginalityCheckTimeoutError,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.models import (
    DraftContentItem,
    OriginalityReport,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.originality_check_service import (
    OriginalityCheckService,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.repository import (
    DraftContentItemRepository,
    OriginalityReportRepository,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.thumbnail_service import (
    ThumbnailService,
)

logger = logging.getLogger(__name__)


class DraftLifecycleService:
    """Manages lifecycle state transitions for draft content items."""

    def __init__(
        self,
        draft_repository: DraftContentItemRepository | None = None,
        report_repository: OriginalityReportRepository | None = None,
        originality_service: OriginalityCheckService | None = None,
        thumbnail_service: ThumbnailService | None = None,
    ) -> None:
        self.draft_repository = draft_repository or DraftContentItemRepository()
        self.report_repository = report_repository or OriginalityReportRepository()
        self.originality_service = originality_service or OriginalityCheckService()
        self.thumbnail_service = thumbnail_service or ThumbnailService()

    async def initiate_pre_publish_transition(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> tuple[str, OriginalityReport | None]:
        """Initiate Draft-to-Pre-Publish transition.

        Only the lead creator can initiate this transition.
        Triggers originality check. Returns (status, report).
        Status is one of: 'checking_originality', 'awaiting_confirmation', 'timeout'.
        """
        draft = await self._get_and_verify_lead_creator(session, content_item_id, creator_id)

        if draft.lifecycle_state != LifecycleState.DRAFT:
            raise InvalidLifecycleTransitionError(
                message=f"Cannot transition from '{draft.lifecycle_state.value}' to Pre-Publish. Only Draft items can transition.",
            )

        # Auto-select default thumbnail if none selected
        await self.thumbnail_service.auto_select_default(session, content_item_id, creator_id)

        # Trigger originality check
        try:
            report = await self.originality_service.initiate_check(
                session, content_item_id, creator_id,
            )
            return "awaiting_confirmation", report
        except OriginalityCheckTimeoutError:
            return "timeout", None
        except Exception:
            logger.warning(
                "Originality check failed for content item %s, returning checking_originality status",
                content_item_id,
            )
            return "checking_originality", None

    async def confirm_pre_publish(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> DraftContentItem:
        """Confirm Pre-Publish transition after reviewing originality report.

        Completes the lifecycle state change regardless of duplicate_risk_score (advisory only).
        """
        draft = await self._get_and_verify_lead_creator(session, content_item_id, creator_id)

        if draft.lifecycle_state != LifecycleState.DRAFT:
            raise InvalidLifecycleTransitionError(
                message=f"Cannot confirm Pre-Publish from '{draft.lifecycle_state.value}' state.",
            )

        # Check that originality report exists (completed status)
        report = await self.report_repository.get_by_content_item_id(
            session, content_item_id,
        )
        if report is None or report.report_status != ReportStatus.COMPLETED:
            raise InvalidLifecycleTransitionError(
                message="Cannot confirm Pre-Publish without a completed originality report. Please wait for the report or retry the check.",
            )

        # Transition to Pre-Publish
        updated = await self.draft_repository.update(
            session,
            content_item_id,
            {"lifecycle_state": LifecycleState.PRE_PUBLISH},
        )

        logger.info(
            "Draft content item %s transitioned to Pre-Publish by creator %s",
            content_item_id,
            creator_id,
        )
        return updated  # type: ignore[return-value]

    async def retry_originality(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> tuple[str, OriginalityReport | None]:
        """Retry originality check after timeout. Draft remains in Draft state."""
        await self._get_and_verify_lead_creator(session, content_item_id, creator_id)

        try:
            report = await self.originality_service.retry_check(
                session, content_item_id, creator_id,
            )
            return "awaiting_confirmation", report
        except OriginalityCheckTimeoutError:
            return "timeout", None
        except Exception:
            return "checking_originality", None

    async def _get_and_verify_lead_creator(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> DraftContentItem:
        """Fetch draft and verify requester is the lead creator."""
        draft = await self.draft_repository.get_by_id(session, content_item_id)
        if draft is None:
            raise DraftContentItemNotFoundError(
                message=f"Draft content item '{content_item_id}' not found.",
            )
        if draft.lead_creator_account_id != creator_id:
            raise ContributorAccessDeniedError(
                message="Only the lead creator can perform lifecycle transitions.",
            )
        return draft
