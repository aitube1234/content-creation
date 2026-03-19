"""SSE streaming endpoint handler for AG-UI Protocol."""

import json
import logging
import uuid
from collections.abc import AsyncGenerator

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    AssemblyStatus,
)

logger = logging.getLogger(__name__)


async def generate_assembly_events(
    content_item_id: uuid.UUID,
    assembly_status: AssemblyStatus,
    run_id: str | None = None,
    thread_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Generate SSE events for assembly status streaming.

    Emits typed JSON events with run_id/thread_id correlation for
    AG-UI Protocol compliance.

    Event types:
    - assembly_status: Current pipeline status (PENDING/PROCESSING/COMPLETED/FAILED)
    - transcoding_progress: Progress of cloud media transcoding
    """
    effective_run_id = run_id or str(uuid.uuid4())
    effective_thread_id = thread_id or str(uuid.uuid4())

    # Emit initial status event
    event = {
        "event_type": "assembly_status",
        "content_item_id": str(content_item_id),
        "run_id": effective_run_id,
        "thread_id": effective_thread_id,
        "assembly_status": assembly_status.value,
        "message": f"Assembly is {assembly_status.value}.",
    }
    yield f"data: {json.dumps(event)}\n\n"

    # Emit status-specific events
    if assembly_status == AssemblyStatus.PROCESSING:
        # Emit progress events for processing state
        progress_steps = [
            (0.1, "Generating visuals..."),
            (0.3, "Generating voiceover..."),
            (0.5, "Sequencing scenes..."),
            (0.7, "Generating transitions..."),
            (0.8, "Generating metadata..."),
            (0.9, "Generating thumbnails..."),
            (1.0, "Assembly complete."),
        ]
        for progress, message in progress_steps:
            progress_event = {
                "event_type": "transcoding_progress",
                "content_item_id": str(content_item_id),
                "run_id": effective_run_id,
                "thread_id": effective_thread_id,
                "progress": progress,
                "message": message,
            }
            yield f"data: {json.dumps(progress_event)}\n\n"

    elif assembly_status == AssemblyStatus.COMPLETED:
        completion_event = {
            "event_type": "assembly_status",
            "content_item_id": str(content_item_id),
            "run_id": effective_run_id,
            "thread_id": effective_thread_id,
            "assembly_status": "completed",
            "message": "Video draft assembly completed successfully.",
        }
        yield f"data: {json.dumps(completion_event)}\n\n"

    elif assembly_status == AssemblyStatus.FAILED:
        failure_event = {
            "event_type": "assembly_status",
            "content_item_id": str(content_item_id),
            "run_id": effective_run_id,
            "thread_id": effective_thread_id,
            "assembly_status": "failed",
            "message": "Video draft assembly failed. You can retry the assembly.",
        }
        yield f"data: {json.dumps(failure_event)}\n\n"
