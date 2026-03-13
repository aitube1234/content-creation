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
