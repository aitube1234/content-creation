"""Global FastAPI exception handlers."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Register all typed exception handlers on the FastAPI app."""
    from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.exceptions import (
        DuplicateGenerationRequestError,
        InputNotDeletableError,
        InputRecordNotFoundError,
        InputTypeNotChangeableError,
        InvalidStateTransitionError,
        PipelineUnavailableError,
        ScriptPromptIngestionError,
    )
    from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.exceptions import (
        AIVideoDraftAssemblyError,
        AssemblyAlreadyProcessingError,
        AssemblyNotRetryableError,
        AssemblyPipelineError,
        ContentItemNotFoundError,
        InputValidationError,
        LifecycleServiceUnavailableError,
        MetadataEngineWriteError,
        MetadataGenerationError,
        MicrophonePermissionError,
        SceneNotFoundError,
        ThumbnailGenerationError,
    )

    @app.exception_handler(InputRecordNotFoundError)
    async def input_not_found_handler(
        request: Request, exc: InputRecordNotFoundError
    ) -> JSONResponse:
        logger.warning("Input record not found: %s", exc.message)
        return JSONResponse(
            status_code=404,
            content={
                "error_code": "INPUT_RECORD_NOT_FOUND",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(InvalidStateTransitionError)
    async def invalid_state_handler(
        request: Request, exc: InvalidStateTransitionError
    ) -> JSONResponse:
        logger.warning("Invalid state transition: %s", exc.message)
        return JSONResponse(
            status_code=409,
            content={
                "error_code": "INVALID_STATE_TRANSITION",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(InputNotDeletableError)
    async def not_deletable_handler(
        request: Request, exc: InputNotDeletableError
    ) -> JSONResponse:
        logger.warning("Input not deletable: %s", exc.message)
        return JSONResponse(
            status_code=409,
            content={
                "error_code": "INPUT_NOT_DELETABLE",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(InputTypeNotChangeableError)
    async def type_not_changeable_handler(
        request: Request, exc: InputTypeNotChangeableError
    ) -> JSONResponse:
        logger.warning("Input type not changeable: %s", exc.message)
        return JSONResponse(
            status_code=409,
            content={
                "error_code": "INPUT_TYPE_NOT_CHANGEABLE",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(PipelineUnavailableError)
    async def pipeline_unavailable_handler(
        request: Request, exc: PipelineUnavailableError
    ) -> JSONResponse:
        logger.error("Pipeline unavailable: %s", exc.message)
        return JSONResponse(
            status_code=502,
            content={
                "error_code": "PIPELINE_UNAVAILABLE",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(DuplicateGenerationRequestError)
    async def duplicate_generation_handler(
        request: Request, exc: DuplicateGenerationRequestError
    ) -> JSONResponse:
        logger.warning("Duplicate generation request: %s", exc.message)
        return JSONResponse(
            status_code=409,
            content={
                "error_code": "DUPLICATE_GENERATION_REQUEST",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(ScriptPromptIngestionError)
    async def generic_ingestion_handler(
        request: Request, exc: ScriptPromptIngestionError
    ) -> JSONResponse:
        logger.error("Script prompt ingestion error: %s", exc.message)
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "SCRIPT_PROMPT_INGESTION_ERROR",
                "message": exc.message,
                "details": exc.details,
            },
        )

    # --- AI Video Draft Assembly exception handlers ---

    @app.exception_handler(ContentItemNotFoundError)
    async def content_item_not_found_handler(
        request: Request, exc: ContentItemNotFoundError
    ) -> JSONResponse:
        logger.warning("Content item not found: %s", exc.message)
        return JSONResponse(
            status_code=404,
            content={
                "error_code": "CONTENT_ITEM_NOT_FOUND",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(InputValidationError)
    async def input_validation_handler(
        request: Request, exc: InputValidationError
    ) -> JSONResponse:
        logger.warning("Input validation failed: %s", exc.message)
        return JSONResponse(
            status_code=422,
            content={
                "error_code": "INPUT_VALIDATION_ERROR",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(SceneNotFoundError)
    async def scene_not_found_handler(
        request: Request, exc: SceneNotFoundError
    ) -> JSONResponse:
        logger.warning("Scene not found: %s", exc.message)
        return JSONResponse(
            status_code=404,
            content={
                "error_code": "SCENE_NOT_FOUND",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(AssemblyPipelineError)
    async def assembly_pipeline_handler(
        request: Request, exc: AssemblyPipelineError
    ) -> JSONResponse:
        logger.error("Assembly pipeline error: %s", exc.message)
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "ASSEMBLY_PIPELINE_ERROR",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(AssemblyAlreadyProcessingError)
    async def assembly_already_processing_handler(
        request: Request, exc: AssemblyAlreadyProcessingError
    ) -> JSONResponse:
        logger.warning("Assembly already processing: %s", exc.message)
        return JSONResponse(
            status_code=409,
            content={
                "error_code": "ASSEMBLY_ALREADY_PROCESSING",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(AssemblyNotRetryableError)
    async def assembly_not_retryable_handler(
        request: Request, exc: AssemblyNotRetryableError
    ) -> JSONResponse:
        logger.warning("Assembly not retryable: %s", exc.message)
        return JSONResponse(
            status_code=409,
            content={
                "error_code": "ASSEMBLY_NOT_RETRYABLE",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(MetadataGenerationError)
    async def metadata_generation_handler(
        request: Request, exc: MetadataGenerationError
    ) -> JSONResponse:
        logger.error("Metadata generation error: %s", exc.message)
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "METADATA_GENERATION_ERROR",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(MetadataEngineWriteError)
    async def metadata_engine_write_handler(
        request: Request, exc: MetadataEngineWriteError
    ) -> JSONResponse:
        logger.error("Metadata engine write error: %s", exc.message)
        return JSONResponse(
            status_code=502,
            content={
                "error_code": "METADATA_ENGINE_WRITE_ERROR",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(ThumbnailGenerationError)
    async def thumbnail_generation_handler(
        request: Request, exc: ThumbnailGenerationError
    ) -> JSONResponse:
        logger.error("Thumbnail generation error: %s", exc.message)
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "THUMBNAIL_GENERATION_ERROR",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(LifecycleServiceUnavailableError)
    async def lifecycle_unavailable_handler(
        request: Request, exc: LifecycleServiceUnavailableError
    ) -> JSONResponse:
        logger.error("Lifecycle service unavailable: %s", exc.message)
        return JSONResponse(
            status_code=502,
            content={
                "error_code": "LIFECYCLE_SERVICE_UNAVAILABLE",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(MicrophonePermissionError)
    async def microphone_permission_handler(
        request: Request, exc: MicrophonePermissionError
    ) -> JSONResponse:
        logger.warning("Microphone permission error: %s", exc.message)
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "MICROPHONE_PERMISSION_ERROR",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(AIVideoDraftAssemblyError)
    async def generic_assembly_handler(
        request: Request, exc: AIVideoDraftAssemblyError
    ) -> JSONResponse:
        logger.error("AI video draft assembly error: %s", exc.message)
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "AI_VIDEO_DRAFT_ASSEMBLY_ERROR",
                "message": exc.message,
                "details": exc.details,
            },
        )

    # --- Draft Content Item Creation exception handlers ---

    from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.exceptions import (
        ContentItemImmutableFieldError,
        ContributorAccessDeniedError,
        DraftContentItemCreationError,
        DraftContentItemNotFoundError,
        DraftNotDeletableError,
        InvalidLifecycleTransitionError,
        MetadataNotFoundError,
        OriginalityCheckTimeoutError,
        OriginalityEngineUnavailableError,
        ThumbnailNotFoundError,
        VersionEntryNotFoundError,
    )

    @app.exception_handler(DraftContentItemNotFoundError)
    async def draft_not_found_handler(
        request: Request, exc: DraftContentItemNotFoundError
    ) -> JSONResponse:
        logger.warning("Draft content item not found: %s", exc.message)
        return JSONResponse(
            status_code=404,
            content={
                "error_code": "DRAFT_CONTENT_ITEM_NOT_FOUND",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(InvalidLifecycleTransitionError)
    async def invalid_lifecycle_transition_handler(
        request: Request, exc: InvalidLifecycleTransitionError
    ) -> JSONResponse:
        logger.warning("Invalid lifecycle transition: %s", exc.message)
        return JSONResponse(
            status_code=409,
            content={
                "error_code": "INVALID_LIFECYCLE_TRANSITION",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(DraftNotDeletableError)
    async def draft_not_deletable_handler(
        request: Request, exc: DraftNotDeletableError
    ) -> JSONResponse:
        logger.warning("Draft not deletable: %s", exc.message)
        return JSONResponse(
            status_code=409,
            content={
                "error_code": "DRAFT_NOT_DELETABLE",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(ContributorAccessDeniedError)
    async def contributor_access_denied_handler(
        request: Request, exc: ContributorAccessDeniedError
    ) -> JSONResponse:
        logger.warning("Contributor access denied: %s", exc.message)
        return JSONResponse(
            status_code=403,
            content={
                "error_code": "CONTRIBUTOR_ACCESS_DENIED",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(ContentItemImmutableFieldError)
    async def immutable_field_handler(
        request: Request, exc: ContentItemImmutableFieldError
    ) -> JSONResponse:
        logger.warning("Immutable field update attempted: %s", exc.message)
        return JSONResponse(
            status_code=409,
            content={
                "error_code": "CONTENT_ITEM_IMMUTABLE_FIELD",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(OriginalityCheckTimeoutError)
    async def originality_timeout_handler(
        request: Request, exc: OriginalityCheckTimeoutError
    ) -> JSONResponse:
        logger.warning("Originality check timeout: %s", exc.message)
        return JSONResponse(
            status_code=504,
            content={
                "error_code": "ORIGINALITY_CHECK_TIMEOUT",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(OriginalityEngineUnavailableError)
    async def originality_unavailable_handler(
        request: Request, exc: OriginalityEngineUnavailableError
    ) -> JSONResponse:
        logger.error("Originality engine unavailable: %s", exc.message)
        return JSONResponse(
            status_code=502,
            content={
                "error_code": "ORIGINALITY_ENGINE_UNAVAILABLE",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(MetadataNotFoundError)
    async def metadata_not_found_handler(
        request: Request, exc: MetadataNotFoundError
    ) -> JSONResponse:
        logger.warning("Metadata not found: %s", exc.message)
        return JSONResponse(
            status_code=404,
            content={
                "error_code": "METADATA_NOT_FOUND",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(ThumbnailNotFoundError)
    async def thumbnail_not_found_handler(
        request: Request, exc: ThumbnailNotFoundError
    ) -> JSONResponse:
        logger.warning("Thumbnail not found: %s", exc.message)
        return JSONResponse(
            status_code=404,
            content={
                "error_code": "THUMBNAIL_NOT_FOUND",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(VersionEntryNotFoundError)
    async def version_entry_not_found_handler(
        request: Request, exc: VersionEntryNotFoundError
    ) -> JSONResponse:
        logger.warning("Version entry not found: %s", exc.message)
        return JSONResponse(
            status_code=404,
            content={
                "error_code": "VERSION_ENTRY_NOT_FOUND",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(DraftContentItemCreationError)
    async def generic_draft_creation_handler(
        request: Request, exc: DraftContentItemCreationError
    ) -> JSONResponse:
        logger.error("Draft content item creation error: %s", exc.message)
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "DRAFT_CONTENT_ITEM_CREATION_ERROR",
                "message": exc.message,
                "details": exc.details,
            },
        )
