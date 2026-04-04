from __future__ import annotations

import base64
import json
import os
import re
from collections.abc import Iterator
from typing import Any

import boto3

# Cap agent completion length (was 8192; reduced by 4000 for cost/latency).
AGENT_MAX_OUTPUT_TOKENS = 2048


def _parse_data_url(data_url: str) -> tuple[str, bytes]:
    m = re.match(r"^data:([^;]+);base64,(.+)$", data_url, re.DOTALL)
    if not m:
        raise ValueError("Invalid data URL")
    media_type = m.group(1)
    raw = base64.b64decode(m.group(2))
    return media_type, raw


def _to_anthropic_content_blocks(content: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for part in content:
        if part.get("type") == "image":
            img = part.get("image") or ""
            if isinstance(img, str) and img.startswith("data:"):
                head, b64 = img.split(",", 1)
                media_type = head.split(":", 1)[1].split(";", 1)[0]
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
                "content": _to_anthropic_content_blocks(m["content"]),
            }
        )
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": AGENT_MAX_OUTPUT_TOKENS,
        "temperature": 0,
        "system": system_prompt,
        "messages": api_messages,
    }
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
        if payload.get("type") == "content_block_delta":
            delta = payload.get("delta") or {}
            if delta.get("type") == "text_delta":
                t = delta.get("text")
                if t:
                    yield t


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
