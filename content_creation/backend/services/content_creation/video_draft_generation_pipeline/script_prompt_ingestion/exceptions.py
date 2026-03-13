"""Typed exception hierarchy for script prompt ingestion."""


class ScriptPromptIngestionError(Exception):
    """Base exception for the script prompt ingestion use case."""

    def __init__(self, message: str = "", details: list | None = None) -> None:
        self.message = message
        self.details = details or []
        super().__init__(self.message)


class InputRecordNotFoundError(ScriptPromptIngestionError):
    """Raised when a record is not found for the given creator."""


class InvalidStateTransitionError(ScriptPromptIngestionError):
    """Raised for disallowed workflow state transitions."""


class InputNotDeletableError(ScriptPromptIngestionError):
    """Raised when attempting to delete a non-Draft record."""


class InputTypeNotChangeableError(ScriptPromptIngestionError):
    """Raised when attempting to change type on a non-Draft record."""


class PipelineUnavailableError(ScriptPromptIngestionError):
    """Raised when the video generation pipeline fails to confirm receipt."""


class DuplicateGenerationRequestError(ScriptPromptIngestionError):
    """Raised when generation is attempted on a GenerationInitiated record."""
