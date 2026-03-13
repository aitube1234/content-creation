"""Input lifecycle state machine for workflow state transitions."""

from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.exceptions import (
    InvalidStateTransitionError,
)
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.models import (
    WorkflowState,
)

PERMITTED_TRANSITIONS: dict[WorkflowState, set[WorkflowState]] = {
    WorkflowState.DRAFT: {WorkflowState.SUBMITTED},
    WorkflowState.SUBMITTED: {
        WorkflowState.VALIDATION_FAILED,
        WorkflowState.GENERATION_INITIATED,
    },
    WorkflowState.VALIDATION_FAILED: {WorkflowState.DRAFT},
    WorkflowState.GENERATION_INITIATED: set(),
}


class InputLifecycleStateMachine:
    """Encodes permitted state transitions and guards."""

    @staticmethod
    def transition(current: WorkflowState, target: WorkflowState) -> WorkflowState:
        """Validate and return the target state if the transition is permitted."""
        allowed = PERMITTED_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise InvalidStateTransitionError(
                message=f"Transition from '{current.value}' to '{target.value}' is not permitted.",
                details=[
                    f"Current state: {current.value}",
                    f"Requested state: {target.value}",
                    f"Allowed transitions: {[s.value for s in allowed]}",
                ],
            )
        return target

    @staticmethod
    def can_delete(state: WorkflowState) -> bool:
        """Only Draft records can be deleted."""
        return state == WorkflowState.DRAFT

    @staticmethod
    def can_change_type(state: WorkflowState) -> bool:
        """Only Draft records can have their type changed."""
        return state == WorkflowState.DRAFT

    @staticmethod
    def can_submit(state: WorkflowState) -> bool:
        """Draft and ValidationFailed records can be submitted."""
        return state in {WorkflowState.DRAFT, WorkflowState.VALIDATION_FAILED}
