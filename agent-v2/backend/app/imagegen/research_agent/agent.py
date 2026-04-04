from __future__ import annotations

import logging
from typing import Literal

from openai import OpenAI

from ..config import get_settings

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def _client_or_raise() -> OpenAI:
    global _client
    settings = get_settings()
    if not (settings.perplexity_api_key or "").strip():
        raise ValueError("PERPLEXITY_API_KEY is not set")
    if _client is None:
        _client = OpenAI(
            api_key=settings.perplexity_api_key,
            base_url=settings.perplexity_base_url,
        )
    return _client


SYSTEM_PROMPT = (
    "You are a precise research assistant. "
    "Answer the question factually and concisely, citing up-to-date information. "
    "If the topic has changed recently, prefer the most current data. "
    "Keep your answer focused and no longer than 3–4 short paragraphs unless more detail is requested."
)


def search(
    query: str,
    depth: Literal["fast", "normal", "deep"] = "normal",
    extra_instructions: str = "",
) -> dict:
    settings = get_settings()
    model = settings.perplexity_model_map[depth]
    client = _client_or_raise()
    system = SYSTEM_PROMPT
    if extra_instructions:
        system += f"\n\nAdditional instructions: {extra_instructions}"

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": query},
        ],
    )

    answer = response.choices[0].message.content or ""

    citations: list[str] = []
    try:
        raw = response.model_extra or {}
        citations = raw.get("citations", [])
    except Exception:
        pass

    return {
        "query": query,
        "answer": answer,
        "citations": citations,
        "model": model,
    }


def run(
    queries: list[str],
    depth: Literal["fast", "normal", "deep"] = "normal",
) -> list[dict]:
    settings = get_settings()
    results: list[dict] = []
    for q in queries:
        logger.info("Research query: %s", q[:120])
        try:
            result = search(q, depth=depth)
            results.append(result)
        except Exception as exc:
            logger.warning("Research failed for query: %s", exc)
            results.append(
                {
                    "query": q,
                    "answer": "",
                    "citations": [],
                    "model": settings.perplexity_model_map[depth],
                    "error": str(exc),
                }
            )
    return results


def format_research_block(results: list[dict]) -> str:
    lines = ["=== RESEARCH FINDINGS ===\n"]
    for r in results:
        lines.append(f"Q: {r['query']}")
        if r.get("error"):
            lines.append(f"A: [Research failed: {r['error']}]")
        else:
            lines.append(f"A: {r['answer']}")
            if r.get("citations"):
                lines.append("Sources: " + ", ".join(r["citations"][:3]))
        lines.append("")
    lines.append("=== END OF RESEARCH ===")
    return "\n".join(lines)
