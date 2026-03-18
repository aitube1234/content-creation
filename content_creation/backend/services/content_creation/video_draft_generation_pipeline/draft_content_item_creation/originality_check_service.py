"""Service for originality checking on draft content items."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.enums import (
    ReportStatus,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.exceptions import (
    DraftContentItemNotFoundError,
    OriginalityCheckTimeoutError,
    OriginalityEngineUnavailableError,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.integrations.originality_engine_client import (
    OriginalityEngineClient,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.models import (
    OriginalityReport,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.repository import (
    DraftContentItemRepository,
    OriginalityReportRepository,
)

logger = logging.getLogger(__name__)


class OriginalityCheckService:
    """Invokes originality engine, manages timeout/retry, stores reports."""

    def __init__(
        self,
        draft_repository: DraftContentItemRepository | None = None,
        report_repository: OriginalityReportRepository | None = None,
        engine_client: OriginalityEngineClient | None = None,
    ) -> None:
        self.draft_repository = draft_repository or DraftContentItemRepository()
        self.report_repository = report_repository or OriginalityReportRepository()
        self.engine_client = engine_client or OriginalityEngineClient()

    async def initiate_check(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_account_id: uuid.UUID,
    ) -> OriginalityReport:
        """Invoke originality check and store the report.

        Returns the report on success. Stores a timeout/failed report on error.
        The report is advisory only — it does not block the transition.
        """
        draft = await self.draft_repository.get_by_id(session, content_item_id, creator_account_id)
        if draft is None:
            raise DraftContentItemNotFoundError(
                message=f"Draft content item '{content_item_id}' not found for creator '{creator_account_id}'.",
            )

        try:
            result = await self.engine_client.check_originality(
                content_item_id, creator_account_id,
            )

            report = await self.report_repository.create(
                session,
                {
                    "content_item_id": content_item_id,
                    "creator_account_id": creator_account_id,
                    "duplicate_risk_score": result.get("duplicate_risk_score", 0),
                    "similar_content_items": result.get("similar_content_items"),
                    "differentiation_recommendations": result.get("differentiation_recommendations"),
                    "report_status": ReportStatus.COMPLETED,
                },
            )

            # Link report to draft
            await self.draft_repository.update(
                session,
                content_item_id,
                {"originality_report_id": report.originality_report_id},
            )

            logger.info("Originality check completed for content item %s", content_item_id)
            return report

        except OriginalityCheckTimeoutError:
            report = await self.report_repository.create(
                session,
                {
                    "content_item_id": content_item_id,
                    "creator_account_id": creator_account_id,
                    "report_status": ReportStatus.TIMEOUT,
                },
            )
            logger.warning("Originality check timed out for content item %s", content_item_id)
            raise

        except OriginalityEngineUnavailableError:
            report = await self.report_repository.create(
                session,
                {
                    "content_item_id": content_item_id,
                    "creator_account_id": creator_account_id,
                    "report_status": ReportStatus.FAILED,
                },
            )
            logger.error("Originality engine unavailable for content item %s", content_item_id)
            raise

    async def retry_check(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_account_id: uuid.UUID,
    ) -> OriginalityReport:
        """Retry the originality check after a timeout or failure."""
        return await self.initiate_check(session, content_item_id, creator_account_id)

    async def get_report(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
    ) -> OriginalityReport | None:
        """Retrieve the latest originality report for a content item."""
        return await self.report_repository.get_by_content_item_id(
            session, content_item_id,
        )
