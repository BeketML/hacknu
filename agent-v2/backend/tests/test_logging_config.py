import logging

import pytest

from app.logging_config import configure_logging, reset_logging_for_tests


def test_configure_logging_adds_handlers() -> None:
    reset_logging_for_tests()
    configure_logging()
    root = logging.getLogger()
    assert len(root.handlers) >= 1
    n = len(root.handlers)
    configure_logging()
    assert len(root.handlers) == n


def test_configure_logging_respects_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_logging_for_tests()
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    configure_logging()
    root = logging.getLogger()
    assert root.level == logging.WARNING
    reset_logging_for_tests()
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    configure_logging()
