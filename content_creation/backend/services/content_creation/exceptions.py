"""Base exceptions for the content creation service."""


class ContentCreationError(Exception):
    """Base exception for the content creation service."""

    def __init__(self, message: str = "", details: list | None = None) -> None:
        self.message = message
        self.details = details or []
        super().__init__(self.message)
