"""Typed exception hierarchy for draft content item creation."""


class DraftContentItemCreationError(Exception):
    """Base exception for the draft content item creation use case."""

    def __init__(self, message: str = "", details: list | None = None) -> None:
        self.message = message
        self.details = details or []
        super().__init__(self.message)


class DraftContentItemNotFoundError(DraftContentItemCreationError):
    """Raised when a draft content item is not found for the given creator."""


class InvalidLifecycleTransitionError(DraftContentItemCreationError):
    """Raised when a lifecycle state transition is not permitted."""


class DraftNotDeletableError(DraftContentItemCreationError):
    """Raised when a draft content item cannot be deleted due to its lifecycle state."""


class OriginalityCheckTimeoutError(DraftContentItemCreationError):
    """Raised when the originality engine check exceeds the SLA timeout."""


class OriginalityCheckFailedError(DraftContentItemCreationError):
    """Raised when the originality engine check fails."""


class OriginalityEngineUnavailableError(DraftContentItemCreationError):
    """Raised when the Content Originality Engine is unavailable."""


class MetadataNotFoundError(DraftContentItemCreationError):
    """Raised when metadata record is not found for a draft content item."""


class ThumbnailNotFoundError(DraftContentItemCreationError):
    """Raised when a thumbnail record is not found."""


class VersionEntryNotFoundError(DraftContentItemCreationError):
    """Raised when a version history entry is not found."""


class ContributorAccessDeniedError(DraftContentItemCreationError):
    """Raised when a contributor attempts an action restricted to the lead creator."""


class ContentItemImmutableFieldError(DraftContentItemCreationError):
    """Raised when an attempt is made to update an immutable field."""
