from __future__ import annotations

import base64
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Literal

from .config import get_settings, require_google_key
from .scenario_agent.agent import run as scenario_run
from .visual_agent.agent import generate_one_slide_bytes, run as visual_run

logger = logging.getLogger(__name__)

MAX_SLIDES = 12
MAX_TEXT_LEN = 50_000
MAX_REFERENCE_IMAGES = 8


def _job_dir(job_id: str) -> Path:
    base = get_settings().artifacts_dir
    base.mkdir(parents=True, exist_ok=True)
    d = base / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def decode_data_urls_to_dir(data_urls: list[str], dest: Path) -> dict[str, Path]:
    dest.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    for i, url in enumerate(data_urls[:MAX_REFERENCE_IMAGES]):
        if not isinstance(url, str) or not url.startswith("data:"):
            continue
        m = re.match(r"^data:([^;]+);base64,(.+)$", url, re.DOTALL)
        if not m:
            continue
        mime = (m.group(1) or "").lower()
        raw = base64.b64decode(m.group(2))
        if "png" in mime:
            ext = ".png"
        elif "jpeg" in mime or "jpg" in mime:
            ext = ".jpg"
        elif "webp" in mime:
            ext = ".webp"
        else:
            ext = ".png"
        name = f"ref_{i}{ext}"
        p = dest / name
        p.write_bytes(raw)
        out[name] = p
    return out


def synthetic_single_scenario(prompt: str, ref_filenames: list[str]) -> dict:
    imgs = ref_filenames if ref_filenames else ["generate"]
    return {
        "overall_style": "modern, clean, professional",
        "mood": "inspiring",
        "slides": [
            {
                "slide_number": 1,
                "title": "Generated image",
                "layout": "hero",
                "visual_description": prompt,
                "images_to_use": imgs,
                "text_elements": {"headline": "", "body": "", "caption": ""},
                "color_palette": [],
            }
        ],
    }


def run_single_job(
    prompt: str,
    *,
    board_id: str | None = None,
    reference_data_urls: list[str] | None = None,
) -> tuple[str, list[str]]:
    require_google_key()
    if len(prompt) > MAX_TEXT_LEN:
        raise ValueError("prompt too long")
    job_id = str(uuid.uuid4())
    out_dir = _job_dir(job_id)
    refs_dir = out_dir / "refs"
    input_map = decode_data_urls_to_dir(reference_data_urls or [], refs_dir)
    input_paths = {k: str(v) for k, v in input_map.items()}
    scenario = synthetic_single_scenario(prompt, list(input_map.keys()))
    slide = scenario["slides"][0]
    img_bytes = generate_one_slide_bytes(
        slide,
        board_id=board_id,
        input_images=input_paths,
        extra_texts=None,
        scenario_defaults=scenario,
    )
    if not img_bytes:
        raise RuntimeError("Image generation failed (no bytes from model)")
    rel = "slide_01.png"
    (out_dir / rel).write_bytes(img_bytes)
    return job_id, [rel]


def run_deck_job(
    brief: str,
    num_slides: int,
    *,
    board_id: str | None = None,
    reference_data_urls: list[str] | None = None,
    skip_research: bool = False,
    research_depth: Literal["fast", "normal", "deep"] = "normal",
) -> tuple[str, list[str], dict]:
    require_google_key()
    if len(brief) > MAX_TEXT_LEN:
        raise ValueError("brief too long")
    n = max(1, min(num_slides, MAX_SLIDES))
    job_id = str(uuid.uuid4())
    out_dir = _job_dir(job_id)
    refs_dir = out_dir / "refs"
    input_map = decode_data_urls_to_dir(reference_data_urls or [], refs_dir)
    image_paths = list(input_map.values())

    scenario = scenario_run(
        text_context=brief,
        image_paths=image_paths,
        num_slides=n,
        research_depth=research_depth,
        skip_research=skip_research,
    )
    (out_dir / "scenario.json").write_text(
        json.dumps(scenario, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    slides_dir = out_dir / "slides"
    input_paths = {k: str(v) for k, v in input_map.items()}
    paths = visual_run(
        scenario=scenario,
        board_id=board_id,
        input_images=input_paths,
        extra_texts=None,
        output_dir=slides_dir,
    )
    rels = [f"slides/{p.name}" for p in paths]
    if not rels:
        raise RuntimeError("Deck generation produced no slides")
    return job_id, rels, scenario
