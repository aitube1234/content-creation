"""Input ingestion service for script and prompt validation (FR-1 to FR-5)."""

import logging
from dataclasses import dataclass, field

from backend.services.content_creation.config import settings
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    ContentInputType,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.schemas import (
    ValidationErrorDetail,
)

logger = logging.getLogger(__name__)


@dataclass
class InputValidationResult:
    """Result of input content validation."""

    is_valid: bool
    errors: list[ValidationErrorDetail] = field(default_factory=list)
    warnings: list[ValidationErrorDetail] = field(default_factory=list)
    detected_locale: str | None = None


class InputIngestionService:
    """Validates creator input for video draft assembly (FR-1 to FR-5)."""

    def __init__(
        self,
        min_script_words: int | None = None,
        min_topic_words: int | None = None,
        max_input_length: int | None = None,
        expected_locale: str | None = None,
    ) -> None:
        self.min_script_words = min_script_words or getattr(
            settings, "ASSEMBLY_MIN_SCRIPT_WORDS", 100
        )
        self.min_topic_words = min_topic_words or getattr(
            settings, "ASSEMBLY_MIN_TOPIC_WORDS", 20
        )
        self.max_input_length = max_input_length or getattr(
            settings, "ASSEMBLY_MAX_INPUT_LENGTH", 100000
        )
        self.expected_locale = expected_locale or getattr(
            settings, "ASSEMBLY_LOCALE", "fr-FR"
        )

    def validate(
        self,
        input_text: str,
        input_type: ContentInputType,
    ) -> InputValidationResult:
        """Run all validation rules and return the result (FR-1 to FR-5)."""
        errors: list[ValidationErrorDetail] = []
        warnings: list[ValidationErrorDetail] = []

        # FR-1: Validate word count minimums
        errors.extend(self._check_word_count(input_text, input_type))

        # FR-2: Enforce configurable maximum input length
        errors.extend(self._check_max_length(input_text))

        # FR-3: Detect locale
        detected_locale = self._detect_locale(input_text)

        # FR-4: Surface locale mismatch warning (non-blocking)
        if detected_locale and not detected_locale.startswith("fr"):
            warnings.append(
                ValidationErrorDetail(
                    field="input_text",
                    message=f"Detected locale '{detected_locale}' does not match expected locale '{self.expected_locale}'. "
                    "Content will still be processed but voiceover and NLP outputs will be in French.",
                    error_code="LOCALE_MISMATCH",
                )
            )

        return InputValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            detected_locale=detected_locale,
        )

    def _check_word_count(
        self, input_text: str, input_type: ContentInputType
    ) -> list[ValidationErrorDetail]:
        """FR-1: Enforce minimum word count by input type."""
        word_count = len(input_text.split())

        if input_type == ContentInputType.SCRIPT:
            if word_count < self.min_script_words:
                return [
                    ValidationErrorDetail(
                        field="input_text",
                        message=f"Script input must be at least {self.min_script_words} words. Current count: {word_count}.",
                        error_code="SCRIPT_TOO_SHORT",
                    )
                ]
        elif input_type == ContentInputType.TOPIC_PROMPT:
            if word_count < self.min_topic_words:
                return [
                    ValidationErrorDetail(
                        field="input_text",
                        message=f"Topic prompt must be at least {self.min_topic_words} words. Current count: {word_count}.",
                        error_code="TOPIC_PROMPT_TOO_SHORT",
                    )
                ]
        return []

    def _check_max_length(self, input_text: str) -> list[ValidationErrorDetail]:
        """FR-2: Enforce configurable maximum input length."""
        if len(input_text) > self.max_input_length:
            return [
                ValidationErrorDetail(
                    field="input_text",
                    message=f"Input must not exceed {self.max_input_length} characters. Current length: {len(input_text)}.",
                    error_code="INPUT_TOO_LONG",
                )
            ]
        return []

    def _detect_locale(self, input_text: str) -> str | None:
        """FR-3: Detect the locale of the input text."""
        try:
            from langdetect import detect

            detected = detect(input_text)
            logger.debug("Detected locale: %s", detected)
            return detected
        except Exception:
            logger.warning("Locale detection failed; defaulting to None")
            return None
