from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .config import get_settings
from .pipeline import run_deck_job, run_single_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/image-gen", tags=["image-gen"])

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)


class SingleBody(BaseModel):
    prompt: str = Field(..., min_length=1)
    board_id: str | None = None
    reference_data_urls: list[str] | None = None


class DeckBody(BaseModel):
    brief: str = Field(..., min_length=1)
    num_slides: int = Field(default=4, ge=1, le=12)
    board_id: str | None = None
    reference_data_urls: list[str] | None = None
    skip_research: bool = False
    research_depth: Literal["fast", "normal", "deep"] = "normal"
    include_scenario: bool = False


class JobResponse(BaseModel):
    job_id: str
    artifact_paths: list[str]
    artifact_urls: list[str]


class DeckJobResponse(JobResponse):
    scenario: dict | None = None


def _artifact_file(job_id: str, rel_path: str) -> Path:
    if not _UUID_RE.match(job_id):
        raise HTTPException(status_code=400, detail="invalid job_id")
    if ".." in rel_path or rel_path.startswith(("/\\", "\\", "/")):
        raise HTTPException(status_code=400, detail="invalid path")
    base = get_settings().artifacts_dir.resolve()
    job_root = (base / job_id).resolve()
    try:
        full = (job_root / rel_path).resolve()
        full.relative_to(job_root)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid path") from e
    if not full.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return full


@router.post("/single", response_model=JobResponse)
def post_single(body: SingleBody) -> JobResponse:
    try:
        job_id, paths = run_single_job(
            body.prompt.strip(),
            board_id=body.board_id,
            reference_data_urls=body.reference_data_urls,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        logger.exception("single image-gen failed")
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        logger.exception("single image-gen failed")
        raise HTTPException(status_code=500, detail=str(e)) from e
    urls = [job_artifact_url(job_id, p) for p in paths]
    return JobResponse(job_id=job_id, artifact_paths=paths, artifact_urls=urls)


@router.post("/deck", response_model=DeckJobResponse)
def post_deck(body: DeckBody) -> DeckJobResponse:
    try:
        job_id, paths, scenario = run_deck_job(
            body.brief.strip(),
            body.num_slides,
            board_id=body.board_id,
            reference_data_urls=body.reference_data_urls,
            skip_research=body.skip_research,
            research_depth=body.research_depth,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        logger.exception("deck image-gen failed")
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        logger.exception("deck image-gen failed")
        raise HTTPException(status_code=500, detail=str(e)) from e
    urls = [job_artifact_url(job_id, p) for p in paths]
    return DeckJobResponse(
        job_id=job_id,
        artifact_paths=paths,
        artifact_urls=urls,
        scenario=scenario if body.include_scenario else None,
    )


@router.get("/jobs/{job_id}/{file_path:path}")
def get_job_artifact(job_id: str, file_path: str) -> FileResponse:
    path = _artifact_file(job_id, file_path)
    suffix = path.suffix.lower()
    media = (
        "application/json"
        if suffix == ".json"
        else "image/png"
        if suffix == ".png"
        else "application/octet-stream"
    )
    return FileResponse(path, media_type=media, filename=path.name)


def job_artifact_url(job_id: str, rel_path: str) -> str:
    enc = rel_path.replace("\\", "/")
    return f"/api/image-gen/jobs/{job_id}/{enc}"
