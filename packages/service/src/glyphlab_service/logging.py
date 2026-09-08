"""Never log authorization, tokens, filenames or image bytes. Only IDs/sizes/codes.
Uvicorn access logs are disabled; route templates replace user-supplied path values.
"""

import json
import logging
import re
from contextvars import ContextVar
from datetime import UTC, datetime

request_id = ContextVar("request_id", default="")
SENSITIVE = re.compile(r"authorization|token|secret|filename", re.IGNORECASE)
TOKEN = re.compile(r"glp_[A-Za-z0-9_-]+")


def redact(value):
    if isinstance(value, dict):
        return {
            k: "[redacted]" if SENSITIVE.search(str(k)) else redact(v) for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return type(value)(redact(v) for v in value)
    if isinstance(value, bytes):
        return "[redacted]"
    if isinstance(value, str):
        return TOKEN.sub("[redacted]", value)
    return value


class RedactionFilter(logging.Filter):
    def filter(self, record):
        record.args = redact(record.args)
        record.msg = redact(record.msg)
        return True


class JSONFormatter(logging.Formatter):
    def format(self, record):
        RedactionFilter().filter(record)
        data = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id.get(),
        }
        for key in ["project_id", "job_id", "error_code"]:
            if hasattr(record, key):
                data[key] = redact(getattr(record, key))
        return json.dumps(data, ensure_ascii=False)


def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger("glyphlab_service")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
