"""Unit tests for InputValidationService."""

import pytest

from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.models import (
    InputType,
)
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.validation_service import (
    InputValidationService,
)


@pytest.fixture
def validation_service() -> InputValidationService:
    return InputValidationService(min_length=10, max_length=100)


class TestInputValidationService:
    """Tests for all validation rules."""

    def test_content_below_minimum_length(self, validation_service: InputValidationService):
        """FR-10: Content below minimum character length returns invalid."""
        result = validation_service.validate("short", InputType.WRITTEN_SCRIPT)
        assert not result.is_valid
        assert any(e.error_code == "CONTENT_TOO_SHORT" for e in result.errors)

    def test_content_above_maximum_length(self, validation_service: InputValidationService):
        """FR-11: Content above maximum character length returns invalid."""
        long_content = "x" * 101
        result = validation_service.validate(long_content, InputType.WRITTEN_SCRIPT)
        assert not result.is_valid
        errors = [e for e in result.errors if e.error_code == "CONTENT_TOO_LONG"]
        assert len(errors) == 1
        assert "101" in errors[0].message

    def test_input_type_required_before_submission(self, validation_service: InputValidationService):
        """FR-12: Submission without input_type returns invalid."""
        result = validation_service.validate("This is valid content text.", None)
        assert not result.is_valid
        assert any(e.error_code == "INPUT_TYPE_REQUIRED" for e in result.errors)

    def test_structured_prompt_empty_fields(self, validation_service: InputValidationService):
        """FR-13: Structured prompt with no populated fields returns invalid."""
        result = validation_service.validate("   ", InputType.STRUCTURED_PROMPT)
        assert not result.is_valid
        assert any(e.error_code == "STRUCTURED_PROMPT_EMPTY" for e in result.errors)

    def test_valid_content_returns_valid(self, validation_service: InputValidationService):
        """Valid content with all required fields returns valid."""
        result = validation_service.validate(
            "This is perfectly valid content for testing.",
            InputType.WRITTEN_SCRIPT,
        )
        assert result.is_valid
        assert len(result.errors) == 0

    def test_boundary_at_minimum_length(self, validation_service: InputValidationService):
        """Content exactly at minimum length is valid."""
        result = validation_service.validate("a" * 10, InputType.TOPIC_OUTLINE)
        assert result.is_valid

    def test_boundary_at_maximum_length(self, validation_service: InputValidationService):
        """Content exactly at maximum length is valid."""
        result = validation_service.validate("a" * 100, InputType.TOPIC_OUTLINE)
        assert result.is_valid

    def test_structured_prompt_with_content_is_valid(self, validation_service: InputValidationService):
        """Structured prompt with populated content is valid."""
        result = validation_service.validate(
            "Topic: AI\nStyle: Documentary",
            InputType.STRUCTURED_PROMPT,
        )
        assert result.is_valid

    def test_multiple_validation_errors(self, validation_service: InputValidationService):
        """Multiple rules can fail simultaneously."""
        result = validation_service.validate("short", None)
        assert not result.is_valid
        error_codes = {e.error_code for e in result.errors}
        assert "CONTENT_TOO_SHORT" in error_codes
        assert "INPUT_TYPE_REQUIRED" in error_codes
