"""Content creation service entry point."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from backend.services.content_creation.database import engine
from backend.services.content_creation.utils.error_handlers import register_exception_handlers
from backend.services.content_creation.utils.logging_config import configure_logging
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.router import (
    router as script_prompt_router,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.router import (
    router as video_draft_assembly_router,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.router import (
    router as draft_content_item_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle: configure logging, yield, then dispose engine."""
    configure_logging()
    yield
    await engine.dispose()


app = FastAPI(title="Content Creation Service", lifespan=lifespan)

# Register exception handlers
register_exception_handlers(app)

# Register routers
app.include_router(script_prompt_router)
app.include_router(video_draft_assembly_router)
app.include_router(draft_content_item_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "content_creation"}
