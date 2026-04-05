from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
from collections.abc import Iterator
from typing import Any

logger = logging.getLogger(__name__)

# Bedrock's hard limit on the **base64 data field** (the `data` string in source.base64).
# Raw image bytes base64-encode at a 4/3 ratio, so the effective raw-byte ceiling is ≈3.75 MB.
_BEDROCK_B64_LIMIT = 5 * 1024 * 1024  # 5 MB  (measured on the base64 string length)
_BEDROCK_RAW_LIMIT = _BEDROCK_B64_LIMIT * 3 // 4  # ≈3.75 MB raw bytes

import boto3

# Cap agent completion length (was 8192; reduced by 4000 for cost/latency).
# Must be large enough to accommodate thinking tokens + actual response.
# Claude extended-thinking models consume thinking tokens from this budget;
# 1024 was too small — the model exhausted the budget during thinking and
# produced no text output at all.
AGENT_MAX_OUTPUT_TOKENS = 20000


def _parse_data_url(data_url: str) -> tuple[str, bytes]:
    m = re.match(r"^data:([^;]+);base64,(.+)$", data_url, re.DOTALL)
    if not m:
        raise ValueError("Invalid data URL")
    media_type = m.group(1)
    raw = base64.b64decode(m.group(2))
    return media_type, raw


def _b64_size(raw: bytes) -> int:
    """Return the length (in bytes) of the base64-encoded form of *raw*."""
    # base64 encodes every 3 bytes as 4 chars, padded to a multiple of 4.
    return (len(raw) + 2) // 3 * 4


def _compress_image_if_needed(raw: bytes, media_type: str) -> tuple[bytes, str]:
    """Recompress / resize *raw* image bytes until their base64 form is ≤ Bedrock's 5 MB limit.

    Bedrock measures the **base64 string length** of the data field, not the raw byte count.
    Returns (possibly compressed bytes, resulting media_type).
    Falls back to the original bytes if Pillow is not installed.
    """
    if _b64_size(raw) <= _BEDROCK_B64_LIMIT:
        return raw, media_type

    try:
        from PIL import Image  # type: ignore
    except ImportError:
        logger.warning(
            "Image base64 is %.1f MB which exceeds Bedrock's 5 MB limit, "
            "but Pillow is not installed so it cannot be compressed. "
            "Install Pillow with: pip install pillow",
            _b64_size(raw) / 1024 / 1024,
        )
        return raw, media_type

    img = Image.open(io.BytesIO(raw))
    # Convert to RGB so we can always save as JPEG regardless of source mode
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    original_b64_mb = _b64_size(raw) / 1024 / 1024
    quality = 85
    scale = 1.0
    out_bytes = raw
    out_media_type = "image/jpeg"

    while _b64_size(out_bytes) > _BEDROCK_B64_LIMIT and (quality >= 40 or scale > 0.25):
        buf = io.BytesIO()
        w, h = img.size
        new_w, new_h = max(int(w * scale), 1), max(int(h * scale), 1)
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        resized.save(buf, format="JPEG", quality=quality, optimize=True)
        out_bytes = buf.getvalue()

        if _b64_size(out_bytes) > _BEDROCK_B64_LIMIT:
            if quality >= 50:
                quality -= 10
            else:
                scale *= 0.75
                quality = 70  # reset quality after each spatial resize step

    logger.info(
        "Compressed image base64 %.1f MB → %.1f MB (quality=%d, scale=%.2f)",
        original_b64_mb,
        _b64_size(out_bytes) / 1024 / 1024,
        quality,
        scale,
    )
    return out_bytes, out_media_type


def _to_anthropic_content_blocks(
    content: list[dict[str, Any]],
    compress_images: bool = False,
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for part in content:
        if part.get("type") == "image":
            img = part.get("image") or ""
            if isinstance(img, str) and img.startswith("data:"):
                head, b64 = img.split(",", 1)
                media_type = head.split(":", 1)[1].split(";", 1)[0]
                if compress_images and len(b64) > _BEDROCK_B64_LIMIT:
                    raw = base64.b64decode(b64)
                    raw, media_type = _compress_image_if_needed(raw, media_type)
                    b64 = base64.b64encode(raw).decode("ascii")
                blocks.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64,
                        },
                    }
                )
        else:
            blocks.append({"type": "text", "text": part.get("text") or ""})
    return blocks


def _merge_adjacent_roles(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for m in messages:
        role = m.get("role")
        content = m.get("content") or []
        if merged and merged[-1].get("role") == role:
            merged[-1]["content"] = list(merged[-1]["content"]) + list(content)
        else:
            merged.append({"role": role, "content": list(content)})
    return merged


def stream_bedrock(
    model_id: str,
    system_prompt: str,
    messages: list[dict[str, Any]],
    region: str,
    thinking_budget: int = 0,
) -> Iterator[str]:
    client = boto3.client(
        "bedrock-runtime",
        region_name=region,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        aws_session_token=os.environ.get("AWS_SESSION_TOKEN"),
    )
    api_messages: list[dict[str, Any]] = []
    for m in _merge_adjacent_roles(messages):
        if m.get("role") not in ("user", "assistant"):
            continue
        api_messages.append(
            {
                "role": m["role"],
                "content": _to_anthropic_content_blocks(m["content"], compress_images=True),
            }
        )
    body: dict[str, Any] = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": AGENT_MAX_OUTPUT_TOKENS,
        "system": system_prompt,
        "messages": api_messages,
    }
    if thinking_budget > 0:
        # Extended thinking requires temperature=1 and a budget_tokens field.
        body["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}
        body["temperature"] = 1
    else:
        body["temperature"] = 0
    response = client.invoke_model_with_response_stream(
        modelId=model_id,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )
    stream = response.get("body")
    if stream is None:
        return
    for event in stream:
        chunk = event.get("chunk")
        if not chunk:
            continue
        payload = json.loads(chunk.get("bytes", b"{}").decode("utf8"))
        event_type = payload.get("type")
        if event_type == "content_block_delta":
            delta = payload.get("delta") or {}
            delta_type = delta.get("type")
            if delta_type == "text_delta":
                t = delta.get("text")
                if t:
                    yield t
            # thinking_delta → silently skip (thinking tokens, not output)
            elif delta_type == "thinking_delta":
                pass
        elif event_type == "message_delta":
            # Log stop reason to aid debugging
            stop_reason = (payload.get("delta") or {}).get("stop_reason")
            if stop_reason and stop_reason != "end_turn":
                logger.warning("Bedrock stream ended with stop_reason=%s", stop_reason)


def stream_anthropic_api(
    model_id: str,
    system_prompt: str,
    messages: list[dict[str, Any]],
    api_key: str,
) -> Iterator[str]:
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    api_messages: list[dict[str, Any]] = []
    for m in _merge_adjacent_roles(messages):
        if m.get("role") not in ("user", "assistant"):
            continue
        api_messages.append(
            {
                "role": m["role"],
                "content": _to_anthropic_content_blocks(m["content"]),
            }
        )
    with client.messages.stream(
        model=model_id,
        max_tokens=AGENT_MAX_OUTPUT_TOKENS,
        temperature=0,
        system=system_prompt,
        messages=api_messages,
    ) as stream:
        for text in stream.text_stream:
            if text:
                yield text


def stream_openai(
    model_id: str,
    system_prompt: str,
    messages: list[dict[str, Any]],
    api_key: str,
) -> Iterator[str]:
    from openai import OpenAI

    oai = OpenAI(api_key=api_key)
    oai_messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    for m in _merge_adjacent_roles(messages):
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        parts = m.get("content") or []
        if len(parts) == 1 and parts[0].get("type") == "text":
            oai_messages.append({"role": role, "content": parts[0].get("text") or ""})
        else:
            content_parts: list[dict[str, Any]] = []
            for p in parts:
                if p.get("type") == "text":
                    content_parts.append(
                        {"type": "text", "text": p.get("text") or ""},
                    )
                elif p.get("type") == "image":
                    img = p.get("image") or ""
                    if isinstance(img, str) and img.startswith("data:"):
                        media_type, raw = _parse_data_url(img)
                        b64 = base64.b64encode(raw).decode("ascii")
                        content_parts.append(
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{b64}",
                                },
                            }
                        )
            oai_messages.append({"role": role, "content": content_parts})
    stream = oai.chat.completions.create(
        model=model_id,
        messages=oai_messages,
        max_tokens=AGENT_MAX_OUTPUT_TOKENS,
        temperature=0,
        stream=True,
    )
    for chunk in stream:
        ch = chunk.choices[0].delta.content
        if ch:
            yield ch


def stream_google(
    model_id: str,
    system_prompt: str,
    messages: list[dict[str, Any]],
    api_key: str,
    thinking_budget: int,
) -> Iterator[str]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    merged = _merge_adjacent_roles(messages)
    contents: list[types.Content] = []
    for m in merged:
        role = m.get("role")
        if role == "assistant":
            grole = "model"
        elif role == "user":
            grole = "user"
        else:
            continue
        parts_out: list[types.Part] = []
        for p in m.get("content") or []:
            if p.get("type") == "text":
                parts_out.append(types.Part(text=p.get("text") or ""))
            elif p.get("type") == "image":
                img = p.get("image") or ""
                if isinstance(img, str) and img.startswith("data:"):
                    media_type, raw = _parse_data_url(img)
                    parts_out.append(
                        types.Part.from_bytes(data=raw, mime_type=media_type),
                    )
        contents.append(types.Content(role=grole, parts=parts_out))
    cfg_kwargs: dict[str, Any] = {
        "max_output_tokens": AGENT_MAX_OUTPUT_TOKENS,
        "temperature": 0,
        "system_instruction": system_prompt,
    }
    if thinking_budget > 0:
        try:
            cfg_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=thinking_budget)
        except Exception:
            pass
    config = types.GenerateContentConfig(**cfg_kwargs)
    for chunk in client.models.generate_content_stream(
        model=model_id,
        contents=contents,
        config=config,
    ):
        if chunk.text:
            yield chunk.text
