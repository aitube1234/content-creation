"""Structured JSON logging configuration."""

import json
import logging
import sys
from datetime import datetime, timezone

from backend.services.content_creation.config import settings


class JSONFormatter(logging.Formatter):
    """Formats log records as JSON for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": settings.SERVICE_NAME,
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        for field in ("input_record_id", "creator_id", "workflow_state"):
            value = getattr(record, field, None)
            if value is not None:
                log_entry[field] = str(value)
        return json.dumps(log_entry)


def configure_logging() -> None:
    """Configure structured JSON logging for the service."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root_logger.handlers.clear()
    root_logger.addHandler(handler)
