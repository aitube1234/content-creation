"""Unit tests for InputLifecycleStateMachine."""

import pytest

from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.exceptions import (
    InvalidStateTransitionError,
)
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.models import (
    WorkflowState,
)
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.state_machine import (
    InputLifecycleStateMachine,
)


@pytest.fixture
def state_machine() -> InputLifecycleStateMachine:
    return InputLifecycleStateMachine()


class TestPermittedTransitions:
    """Test all four permitted transitions succeed."""

    def test_draft_to_submitted(self, state_machine: InputLifecycleStateMachine):
        result = state_machine.transition(WorkflowState.DRAFT, WorkflowState.SUBMITTED)
        assert result == WorkflowState.SUBMITTED

    def test_submitted_to_validation_failed(self, state_machine: InputLifecycleStateMachine):
        result = state_machine.transition(WorkflowState.SUBMITTED, WorkflowState.VALIDATION_FAILED)
        assert result == WorkflowState.VALIDATION_FAILED

    def test_submitted_to_generation_initiated(self, state_machine: InputLifecycleStateMachine):
        result = state_machine.transition(WorkflowState.SUBMITTED, WorkflowState.GENERATION_INITIATED)
        assert result == WorkflowState.GENERATION_INITIATED

    def test_validation_failed_to_draft(self, state_machine: InputLifecycleStateMachine):
        result = state_machine.transition(WorkflowState.VALIDATION_FAILED, WorkflowState.DRAFT)
        assert result == WorkflowState.DRAFT


class TestDisallowedTransitions:
    """Test that disallowed transitions raise InvalidStateTransitionError."""

    @pytest.mark.parametrize(
        "current,target",
        [
            (WorkflowState.DRAFT, WorkflowState.VALIDATION_FAILED),
            (WorkflowState.DRAFT, WorkflowState.GENERATION_INITIATED),
            (WorkflowState.DRAFT, WorkflowState.DRAFT),
            (WorkflowState.SUBMITTED, WorkflowState.DRAFT),
            (WorkflowState.SUBMITTED, WorkflowState.SUBMITTED),
            (WorkflowState.VALIDATION_FAILED, WorkflowState.SUBMITTED),
            (WorkflowState.VALIDATION_FAILED, WorkflowState.GENERATION_INITIATED),
            (WorkflowState.VALIDATION_FAILED, WorkflowState.VALIDATION_FAILED),
            (WorkflowState.GENERATION_INITIATED, WorkflowState.DRAFT),
            (WorkflowState.GENERATION_INITIATED, WorkflowState.SUBMITTED),
            (WorkflowState.GENERATION_INITIATED, WorkflowState.VALIDATION_FAILED),
            (WorkflowState.GENERATION_INITIATED, WorkflowState.GENERATION_INITIATED),
        ],
    )
    def test_disallowed_transition_raises(
        self,
        state_machine: InputLifecycleStateMachine,
        current: WorkflowState,
        target: WorkflowState,
    ):
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            state_machine.transition(current, target)
        assert current.value in exc_info.value.message
        assert target.value in exc_info.value.message


class TestGuards:
    """Test can_delete, can_change_type, can_submit guard methods."""

    def test_can_delete_draft(self, state_machine: InputLifecycleStateMachine):
        assert state_machine.can_delete(WorkflowState.DRAFT) is True

    @pytest.mark.parametrize(
        "state",
        [WorkflowState.SUBMITTED, WorkflowState.VALIDATION_FAILED, WorkflowState.GENERATION_INITIATED],
    )
    def test_cannot_delete_non_draft(self, state_machine: InputLifecycleStateMachine, state: WorkflowState):
        assert state_machine.can_delete(state) is False

    def test_can_change_type_draft(self, state_machine: InputLifecycleStateMachine):
        assert state_machine.can_change_type(WorkflowState.DRAFT) is True

    @pytest.mark.parametrize(
        "state",
        [WorkflowState.SUBMITTED, WorkflowState.VALIDATION_FAILED, WorkflowState.GENERATION_INITIATED],
    )
    def test_cannot_change_type_non_draft(self, state_machine: InputLifecycleStateMachine, state: WorkflowState):
        assert state_machine.can_change_type(state) is False

    def test_can_submit_draft(self, state_machine: InputLifecycleStateMachine):
        assert state_machine.can_submit(WorkflowState.DRAFT) is True

    def test_can_submit_validation_failed(self, state_machine: InputLifecycleStateMachine):
        assert state_machine.can_submit(WorkflowState.VALIDATION_FAILED) is True

    @pytest.mark.parametrize(
        "state",
        [WorkflowState.SUBMITTED, WorkflowState.GENERATION_INITIATED],
    )
    def test_cannot_submit_other_states(self, state_machine: InputLifecycleStateMachine, state: WorkflowState):
        assert state_machine.can_submit(state) is False
