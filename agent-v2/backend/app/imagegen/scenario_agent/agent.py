from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal, Union

from google import genai
from google.genai import types

from ..config import get_settings, require_google_key
from ..research_agent.agent import format_research_block, run as research_run

logger = logging.getLogger(__name__)

_gemini_client: genai.Client | None = None


def _get_gemini() -> genai.Client:
    global _gemini_client
    require_google_key()
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=get_settings().google_api_key)
    return _gemini_client


def _encode_image(path: Union[str, Path]) -> types.Part:
    path = Path(path)
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    mime = mime_map.get(path.suffix.lower(), "image/png")
    raw = path.read_bytes()
    return types.Part.from_bytes(data=raw, mime_type=mime)


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()
    return raw


GAP_DETECTION_PROMPT = """You are a research coordinator helping prepare a visual presentation scenario.

Given a presentation brief, identify the KEY FACTUAL TOPICS that:
- Require current, up-to-date information (statistics, recent events, product specs, etc.)
- You may not have accurate knowledge about (cutting-edge tech, niche domains, recent launches)
- Would make the presentation significantly more compelling and accurate if grounded in real data

Return ONLY a valid JSON object (no markdown fences):
{
  "needs_research": true | false,
  "reason": "<one sentence explaining whether research is needed>",
  "queries": [
    "<specific, self-contained search query 1>",
    "<specific, self-contained search query 2>"
  ]
}

Rules:
- Include at most 4 queries to keep things focused.
- Each query must be a complete, standalone question (imagine typing it into a search engine).
- If the brief is entirely self-contained and needs no external facts, set needs_research=false and queries=[].
- DO NOT include general knowledge questions — only narrow factual gaps.
"""


def _detect_gaps(text_context: str, image_count: int, max_queries: int) -> dict:
    settings = get_settings()
    gemini = _get_gemini()
    user_msg = (
        f"Presentation brief:\n{text_context}\n\n"
        f"{'Reference images provided: ' + str(image_count) if image_count else 'No reference images.'}\n\n"
        "Identify factual knowledge gaps that should be researched before writing this scenario."
    )

    response = gemini.models.generate_content(
        model=settings.gemini_text_model,
        contents=[types.Content(role="user", parts=[types.Part.from_text(text=user_msg)])],
        config=types.GenerateContentConfig(
            system_instruction=GAP_DETECTION_PROMPT,
            temperature=settings.scenario_gap_detection_temperature,
            max_output_tokens=settings.scenario_gap_detection_max_tokens,
        ),
    )

    parsed = json.loads(_strip_fences(response.text))
    queries = parsed.get("queries") or []
    if isinstance(queries, list) and len(queries) > max_queries:
        parsed["queries"] = queries[:max_queries]
    return parsed


SCENARIO_PROMPT = """You are a professional visual storytelling director.
Your job is to analyse provided images, text context, and any research findings,
then design a detailed multi-slide visual scenario for a presentation or explainer sequence.

Return ONLY a valid JSON object (no markdown fences) with the following schema:

{
  "title": "<overall scenario title>",
  "slides": [
    {
      "slide_number": 1,
      "title": "<slide title>",
      "layout": "<layout hint: 'hero', 'split-left', 'split-right', 'grid', 'full-bleed', 'text-only'>",
      "visual_description": "<detailed description of what should be depicted visually>",
      "images_to_use": ["<filename or 'generate'>"],
      "text_elements": {
        "headline": "<main headline>",
        "body": "<body copy — use real facts from the research findings where relevant>",
        "caption": "<optional caption>"
      },
      "color_palette": ["#hex1", "#hex2", "#hex3"],
      "transition_to_next": "<'fade' | 'slide-left' | 'slide-right' | 'zoom-in' | 'zoom-out' | 'none'>",
      "transition_rationale": "<one-sentence explanation of why this transition fits>"
    }
  ],
  "overall_style": "<design style summary>",
  "target_audience": "<intended audience>",
  "mood": "<emotional tone>",
  "research_used": true | false
}

Important: When research findings are provided, weave the real data, statistics, and
current facts naturally into the text elements. Do NOT fabricate numbers.
Each slide must build logically on the previous one.
"""


def _generate_scenario(
    text_context: str,
    image_paths: list[Path],
    num_slides: int,
    research_block: str,
) -> dict:
    settings = get_settings()
    gemini = _get_gemini()
    parts: list = []

    for p in image_paths:
        try:
            parts.append(_encode_image(p))
        except Exception as exc:
            logger.warning("Could not load image %s: %s", p, exc)

    sections: list[str] = [
        f"Number of slides requested: {num_slides}",
        f"\nText context / brief:\n{text_context}",
    ]
    if image_paths:
        sections.append(
            f"\nI have provided {len(image_paths)} reference image(s) above. "
            "Reference them by their filenames where appropriate."
        )
    else:
        sections.append("\nNo reference images were provided; use 'generate' for all image slots.")

    if research_block:
        sections.append(f"\n{research_block}")
        sections.append(
            "\nUse the research findings above to ground the presentation in real, "
            "accurate, and current information."
        )

    sections.append("\nNow produce the scenario JSON.")
    parts.append(types.Part.from_text(text="\n".join(sections)))

    response = gemini.models.generate_content(
        model=settings.gemini_text_model,
        contents=[types.Content(role="user", parts=parts)],
        config=types.GenerateContentConfig(
            system_instruction=SCENARIO_PROMPT,
            temperature=settings.scenario_generation_temperature,
            max_output_tokens=settings.scenario_generation_max_tokens,
        ),
    )

    return json.loads(_strip_fences(response.text))


def run(
    text_context: str,
    image_paths: list[Union[str, Path]] | None = None,
    num_slides: int = 4,
    research_depth: Literal["fast", "normal", "deep"] = "normal",
    force_research: bool = False,
    skip_research: bool = False,
) -> dict:
    settings = get_settings()
    image_paths_resolved = [Path(p) for p in (image_paths or [])]
    research_block = ""

    if not skip_research:
        logger.info("Scenario: gap detection")
        if force_research:
            gap_result = {
                "needs_research": True,
                "reason": "Research forced by caller.",
                "queries": [text_context[:300]],
            }
        else:
            try:
                gap_result = _detect_gaps(
                    text_context,
                    len(image_paths_resolved),
                    settings.scenario_max_research_queries,
                )
            except Exception as exc:
                logger.warning("Gap detection failed: %s", exc)
                gap_result = {"needs_research": False, "reason": str(exc), "queries": []}

        queries = gap_result.get("queries", [])
        if gap_result.get("needs_research") and queries:
            logger.info("Scenario: running research (%d queries)", len(queries))
            try:
                research_block = format_research_block(
                    research_run(queries, depth=research_depth)
                )
            except Exception as exc:
                logger.warning("Research failed: %s", exc)
    else:
        logger.info("Scenario: research skipped")

    logger.info("Scenario: generating JSON")
    scenario = _generate_scenario(
        text_context=text_context,
        image_paths=image_paths_resolved,
        num_slides=num_slides,
        research_block=research_block,
    )
    scenario["research_used"] = bool(research_block)
    return scenario
