"""Central logging setup for the agent-v2 backend.

Environment variables (all optional except as noted):

- LOG_LEVEL: root level, default INFO (e.g. DEBUG, WARNING).
- LOG_FILE: if set, append RotatingFileHandler to this path (in addition to stderr).
- LOG_FILE_MAX_BYTES: max size before rotate, default 10_485_760 (10 MiB).
- LOG_FILE_BACKUP_COUNT: default 5.
- UVICORN_LOG_LEVEL: default INFO (uvicorn + uvicorn.error loggers).
- UVICORN_ACCESS_LOG_LEVEL: default INFO (set WARNING to reduce noise).
- IMAGEGEN_LOG_LEVEL: if set, overrides level for loggers under app.imagegen only.

Example::

    LOG_LEVEL=DEBUG uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler

_configured = False


class _UtcFormatter(logging.Formatter):
    converter = time.gmtime


def _parse_level(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip().upper()
    if not raw:
        return default
    return getattr(logging, raw, default)


def configure_logging() -> None:
    """Configure root logging once (stderr; optional file). Idempotent."""
    global _configured
    if _configured:
        return
    _configured = True

    level = _parse_level("LOG_LEVEL", logging.INFO)
    fmt = "%(asctime)sZ %(levelname)s [%(name)s] %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S"
    formatter = _UtcFormatter(fmt, datefmt=datefmt)

    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(formatter)
    root.addHandler(handler)

    log_file = (os.environ.get("LOG_FILE") or "").strip()
    if log_file:
        max_bytes = int(os.environ.get("LOG_FILE_MAX_BYTES") or "10485760")
        backup = int(os.environ.get("LOG_FILE_BACKUP_COUNT") or "5")
        fh = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup, encoding="utf-8"
        )
        fh.setLevel(level)
        fh.setFormatter(formatter)
        root.addHandler(fh)

    uv_level = _parse_level("UVICORN_LOG_LEVEL", logging.INFO)
    access_level = _parse_level("UVICORN_ACCESS_LOG_LEVEL", logging.INFO)
    logging.getLogger("uvicorn").setLevel(uv_level)
    logging.getLogger("uvicorn.error").setLevel(uv_level)
    logging.getLogger("uvicorn.access").setLevel(access_level)

    ig = (os.environ.get("IMAGEGEN_LOG_LEVEL") or "").strip().upper()
    if ig:
        ig_level = getattr(logging, ig, logging.INFO)
        logging.getLogger("app.imagegen").setLevel(ig_level)


def reset_logging_for_tests() -> None:
    """Clear root handlers and allow configure_logging() to run again (tests only)."""
    global _configured
    _configured = False
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
        h.close()
    root.setLevel(logging.WARNING)
