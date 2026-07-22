import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    _optional_fields = ("trace_id", "method", "path", "status_code", "duration_ms")

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for field_name in self._optional_fields:
            if hasattr(record, field_name):
                payload[field_name] = getattr(record, field_name)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())
    if any(
        getattr(handler, "office_ai_json", False) for handler in root_logger.handlers
    ):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.office_ai_json = True  # type: ignore[attr-defined]
    root_logger.addHandler(handler)
