import pytest

from app.logging_config import configure_logging


@pytest.fixture(scope="session", autouse=True)
def _session_logging() -> None:
    """Ensure logging is configured for tests (TestClient may or may not run lifespan)."""
    configure_logging()
