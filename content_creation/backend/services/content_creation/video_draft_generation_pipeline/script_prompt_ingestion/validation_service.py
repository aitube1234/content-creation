"""Input validation service for script prompt ingestion."""

from dataclasses import dataclass, field

from backend.services.content_creation.config import settings
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.models import (
    InputType,
)
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.schemas import (
    ValidationErrorDetail,
)


@dataclass
class ValidationResult:
    """Result of input content validation."""

    is_valid: bool
    errors: list[ValidationErrorDetail] = field(default_factory=list)


class InputValidationService:
    """Validates input content for completeness and format compliance."""

    def __init__(
        self,
        min_length: int | None = None,
        max_length: int | None = None,
    ) -> None:
        self.min_length = min_length if min_length is not None else settings.MIN_CONTENT_LENGTH
        self.max_length = max_length if max_length is not None else settings.MAX_CONTENT_LENGTH

    def validate(
        self,
        content_text: str,
        input_type: InputType | None,
    ) -> ValidationResult:
        """Run all validation rules and return the result."""
        errors: list[ValidationErrorDetail] = []
        errors.extend(self._check_min_length(content_text))
        errors.extend(self._check_max_length(content_text))
        errors.extend(self._check_input_type_required(input_type))
        errors.extend(self._check_structured_prompt_fields(content_text, input_type))
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def _check_min_length(self, content_text: str) -> list[ValidationErrorDetail]:
        """FR-10: Enforce minimum character length."""
        if len(content_text) < self.min_length:
            return [
                ValidationErrorDetail(
                    field="content_text",
                    message=f"Content must be at least {self.min_length} characters. Current length: {len(content_text)}.",
                    error_code="CONTENT_TOO_SHORT",
                )
            ]
        return []

    def _check_max_length(self, content_text: str) -> list[ValidationErrorDetail]:
        """FR-11: Enforce maximum character length."""
        if len(content_text) > self.max_length:
            return [
                ValidationErrorDetail(
                    field="content_text",
                    message=f"Content must not exceed {self.max_length} characters. Current length: {len(content_text)}.",
                    error_code="CONTENT_TOO_LONG",
                )
            ]
        return []

    def _check_input_type_required(
        self, input_type: InputType | None
    ) -> list[ValidationErrorDetail]:
        """FR-12: Input type must be set before submission."""
        if input_type is None:
            return [
                ValidationErrorDetail(
                    field="input_type",
                    message="Input type must be selected before submission.",
                    error_code="INPUT_TYPE_REQUIRED",
                )
            ]
        return []

    def _check_structured_prompt_fields(
        self,
        content_text: str,
        input_type: InputType | None,
    ) -> list[ValidationErrorDetail]:
        """FR-13: Structured prompt must contain at least one populated field."""
        if input_type == InputType.STRUCTURED_PROMPT:
            stripped = content_text.strip()
            if not stripped:
                return [
                    ValidationErrorDetail(
                        field="content_text",
                        message="Structured prompt must contain at least one populated field.",
                        error_code="STRUCTURED_PROMPT_EMPTY",
                    )
                ]
        return []
