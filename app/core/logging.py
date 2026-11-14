import json
import logging
import sys
from datetime import datetime, timezone
from app.core.context import get_correlation_id


class StructuredJsonFormatter(logging.Formatter):
    """Structured JSON log formatter with correlation ID injection."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "correlation_id": get_correlation_id() or None,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(debug: bool = False) -> None:
    root_logger = logging.getLogger("pawcare")
    root_logger.setLevel(logging.DEBUG if debug else logging.INFO)
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredJsonFormatter())
        root_logger.addHandler(handler)


logger = logging.getLogger("pawcare")
