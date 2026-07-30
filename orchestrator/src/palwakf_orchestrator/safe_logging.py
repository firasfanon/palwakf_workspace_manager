from __future__ import annotations

import logging
import re

REDACTIONS = (
    re.compile(r"\bBearer\s+[A-Za-z0-9._~-]+", re.IGNORECASE),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"(?i)\b(api[_-]?key|token|password|secret)\b(\s*[:=]\s*)[^\s,;]+"),
)


def redact(value: object) -> str:
    text = str(value)
    for pattern in REDACTIONS:
        if pattern.groups:
            text = pattern.sub(r"\1\2[REDACTED]", text)
        else:
            text = pattern.sub("[REDACTED]", text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {key: redact(value) for key, value in record.args.items()}
            else:
                record.args = tuple(redact(value) for value in record.args)
        return True


def configure_safe_logging() -> None:
    redacting_filter = RedactingFilter()
    for logger_name in ("", "uvicorn", "uvicorn.access", "uvicorn.error", "mcp"):
        logger = logging.getLogger(logger_name)
        logger.addFilter(redacting_filter)
        for handler in logger.handlers:
            handler.addFilter(redacting_filter)
