"""Typed exception hierarchy for AI video draft assembly."""


class AIVideoDraftAssemblyError(Exception):
    """Base exception for the AI video draft assembly use case."""

    def __init__(self, message: str = "", details: list | None = None) -> None:
        self.message = message
        self.details = details or []
        super().__init__(self.message)


class ContentItemNotFoundError(AIVideoDraftAssemblyError):
    """Raised when a content item is not found for the given creator."""


class AssemblyPipelineError(AIVideoDraftAssemblyError):
    """Raised when the AI assembly pipeline encounters an error."""


class InputValidationError(AIVideoDraftAssemblyError):
    """Raised when input validation fails."""


class LocaleMismatchWarning(AIVideoDraftAssemblyError):
    """Raised when detected locale does not match fr-FR."""


class SceneNotFoundError(AIVideoDraftAssemblyError):
    """Raised when a scene_id is not found in the content item."""


class MetadataGenerationError(AIVideoDraftAssemblyError):
    """Raised when AI metadata generation fails."""


class ThumbnailGenerationError(AIVideoDraftAssemblyError):
    """Raised when AI thumbnail generation fails."""


class LifecycleServiceUnavailableError(AIVideoDraftAssemblyError):
    """Raised when Content Lifecycle Management service is unavailable."""


class MetadataEngineWriteError(AIVideoDraftAssemblyError):
    """Raised when writing to the Content Metadata Engine fails."""


class MicrophonePermissionError(AIVideoDraftAssemblyError):
    """Raised when microphone access is not available for voice re-recording."""


class AssemblyAlreadyProcessingError(AIVideoDraftAssemblyError):
    """Raised when assembly is already in PROCESSING or COMPLETED state."""


class AssemblyNotRetryableError(AIVideoDraftAssemblyError):
    """Raised when assembly cannot be retried from current status."""
