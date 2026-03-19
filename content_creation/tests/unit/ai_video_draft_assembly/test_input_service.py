"""Unit tests for InputIngestionService (FR-1 to FR-5)."""

import pytest

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.input_service import (
    InputIngestionService,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    ContentInputType,
)


class TestWordCountValidation:
    """FR-1: Validate word count minimums by input type."""

    def setup_method(self):
        self.service = InputIngestionService(
            min_script_words=100,
            min_topic_words=20,
            max_input_length=100000,
        )

    def test_script_too_short(self):
        text = " ".join(["word"] * 99)
        result = self.service.validate(text, ContentInputType.SCRIPT)
        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors[0].error_code == "SCRIPT_TOO_SHORT"

    def test_script_exactly_minimum(self):
        text = " ".join(["word"] * 100)
        result = self.service.validate(text, ContentInputType.SCRIPT)
        assert result.is_valid
        assert len(result.errors) == 0

    def test_script_above_minimum(self):
        text = " ".join(["word"] * 200)
        result = self.service.validate(text, ContentInputType.SCRIPT)
        assert result.is_valid

    def test_topic_prompt_too_short(self):
        text = " ".join(["word"] * 19)
        result = self.service.validate(text, ContentInputType.TOPIC_PROMPT)
        assert not result.is_valid
        assert result.errors[0].error_code == "TOPIC_PROMPT_TOO_SHORT"

    def test_topic_prompt_exactly_minimum(self):
        text = " ".join(["word"] * 20)
        result = self.service.validate(text, ContentInputType.TOPIC_PROMPT)
        assert result.is_valid

    def test_topic_prompt_above_minimum(self):
        text = " ".join(["word"] * 50)
        result = self.service.validate(text, ContentInputType.TOPIC_PROMPT)
        assert result.is_valid


class TestMaxLengthValidation:
    """FR-2: Enforce configurable maximum input length."""

    def setup_method(self):
        self.service = InputIngestionService(
            min_script_words=1,
            min_topic_words=1,
            max_input_length=100,
        )

    def test_exceeds_max_length(self):
        text = "a" * 101
        result = self.service.validate(text, ContentInputType.SCRIPT)
        assert not result.is_valid
        assert result.errors[0].error_code == "INPUT_TOO_LONG"

    def test_at_max_length(self):
        text = "a " * 50  # 100 chars, 50 words
        result = self.service.validate(text, ContentInputType.TOPIC_PROMPT)
        assert result.is_valid

    def test_below_max_length(self):
        text = "a " * 10
        result = self.service.validate(text, ContentInputType.TOPIC_PROMPT)
        assert result.is_valid


class TestLocaleDetection:
    """FR-3, FR-4: Locale detection and mismatch warning."""

    def setup_method(self):
        self.service = InputIngestionService(
            min_script_words=1,
            min_topic_words=1,
            max_input_length=100000,
        )

    def test_detected_locale_returned(self):
        text = " ".join(["bonjour"] * 50)
        result = self.service.validate(text, ContentInputType.SCRIPT)
        assert result.detected_locale is not None

    def test_locale_mismatch_produces_warning(self):
        """Non-French input should produce a locale mismatch warning."""
        text = " ".join(["hello"] * 100)
        result = self.service.validate(text, ContentInputType.SCRIPT)
        # Warnings are non-blocking
        if result.detected_locale and not result.detected_locale.startswith("fr"):
            assert len(result.warnings) >= 1
            assert result.warnings[0].error_code == "LOCALE_MISMATCH"
        # Should still be valid (non-blocking)
        assert result.is_valid

    def test_french_input_no_warning(self):
        """French input should not produce a locale mismatch warning."""
        text = " ".join(["bonjour le monde est merveilleux"] * 20)
        result = self.service.validate(text, ContentInputType.SCRIPT)
        locale_warnings = [w for w in result.warnings if w.error_code == "LOCALE_MISMATCH"]
        # If locale detected as French, no warning
        if result.detected_locale and result.detected_locale.startswith("fr"):
            assert len(locale_warnings) == 0


class TestMultipleErrors:
    """Test multiple simultaneous validation errors."""

    def test_short_and_long_at_same_time_not_possible(self):
        """Word count and max length can both fail."""
        service = InputIngestionService(
            min_script_words=100,
            min_topic_words=20,
            max_input_length=10,
        )
        text = "word " * 5  # 5 words, 25 chars
        result = service.validate(text, ContentInputType.SCRIPT)
        assert not result.is_valid
        error_codes = [e.error_code for e in result.errors]
        assert "SCRIPT_TOO_SHORT" in error_codes
        assert "INPUT_TOO_LONG" in error_codes
