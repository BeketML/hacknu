import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_single_missing_body_field() -> None:
    r = client.post("/api/image-gen/single", json={})
    assert r.status_code == 422


def test_deck_missing_brief() -> None:
    r = client.post("/api/image-gen/deck", json={})
    assert r.status_code == 422


def test_artifact_invalid_job_id() -> None:
    r = client.get("/api/image-gen/jobs/not-a-uuid/slide_01.png")
    assert r.status_code == 400


def test_artifact_path_traversal_rejected() -> None:
    jid = str(uuid.uuid4())
    r = client.get(f"/api/image-gen/jobs/{jid}/../secrets")
    assert r.status_code == 400


def test_artifact_missing_file() -> None:
    jid = str(uuid.uuid4())
    r = client.get(f"/api/image-gen/jobs/{jid}/slide_01.png")
    assert r.status_code == 404


@pytest.mark.skipif(
    not __import__("os").environ.get("GOOGLE_API_KEY", "").strip(),
    reason="GOOGLE_API_KEY not set",
)
def test_single_live_smoke() -> None:
    r = client.post(
        "/api/image-gen/single",
        json={"prompt": "minimal abstract gradient wallpaper, soft colors"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "job_id" in data
    assert data.get("artifact_urls")
