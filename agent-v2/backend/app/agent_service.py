from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator
from typing import Any

from .do_close_json import close_and_parse_json
from .llm_stream import (
    stream_anthropic_api,
    stream_bedrock,
    stream_google,
    stream_openai,
)
from .models_config import get_agent_model_definition, is_valid_model_name
from .prompt.build_messages import build_messages
from .prompt.build_system_prompt import build_system_prompt
from .prompt.get_model_name import get_model_name


def _text_stream_for_model(
    provider: str,
    model_id: str,
    system_prompt: str,
    messages: list[dict[str, Any]],
    model_def: dict[str, Any],
) -> Iterator[str]:
    if provider == "bedrock":
        region = os.environ.get("AWS_REGION") or "eu-central-1"
        yield from stream_bedrock(model_id, system_prompt, messages, region)
        return
    if provider == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY") or ""
        yield from stream_anthropic_api(model_id, system_prompt, messages, key)
        return
    if provider == "openai":
        key = os.environ.get("OPENAI_API_KEY") or ""
        yield from stream_openai(model_id, system_prompt, messages, key)
        return
    if provider == "google":
        key = os.environ.get("GOOGLE_API_KEY") or ""
        budget = 256 if model_def.get("thinking") else 0
        yield from stream_google(model_id, system_prompt, messages, key, budget)
        return
    raise ValueError(f"Unknown provider: {provider}")


def stream_agent_actions(prompt: dict[str, Any]) -> Iterator[dict[str, Any]]:
    model_name = get_model_name(prompt)
    if not is_valid_model_name(model_name):
        raise ValueError(f"Model {model_name} is not in AGENT_MODEL_DEFINITIONS")

    model_def = get_agent_model_definition(model_name)
    provider = model_def["provider"]

    base_system = build_system_prompt(prompt)
    system_prompt = (
        base_system
        + "\n\n## Output format (Bedrock)\nRespond with one raw JSON object only, root key \"actions\". Do not use markdown code fences."
        if provider == "bedrock"
        else base_system
    )

    internal_messages: list[dict[str, Any]] = [
        {"role": "system", "content": [{"type": "text", "text": system_prompt}]}
    ]
    internal_messages.extend(build_messages(prompt))

    debug = prompt.get("debug")
    if isinstance(debug, dict):
        if debug.get("logSystemPrompt"):
            wo = build_system_prompt(prompt, with_schema=False)
            print("[DEBUG] System Prompt (without schema):\n", wo)
        if debug.get("logMessages"):
            print("[DEBUG] Messages:\n", json.dumps(build_messages(prompt), indent=2))

    use_assistant_prefill = provider != "bedrock"
    llm_messages: list[dict[str, Any]] = []
    for m in internal_messages:
        if m.get("role") == "system":
            continue
        llm_messages.append(m)
    if use_assistant_prefill:
        llm_messages.append(
            {"role": "assistant", "content": [{"type": "text", "text": '{"actions": [{"_type":'}]}
        )

    # Match AgentService: only Anthropic API + Google seed the JSON buffer; OpenAI uses API prefill but empty buffer.
    seed = ""
    if use_assistant_prefill and provider in ("anthropic", "google"):
        seed = '{"actions": [{"_type":'
    buffer = seed
    cursor = 0
    maybe_incomplete: dict[str, Any] | None = None
    start_time = time.time() * 1000

    text_iter = _text_stream_for_model(
        provider, model_def["id"], system_prompt, llm_messages, model_def
    )

    for text in text_iter:
        buffer += text
        partial_object = close_and_parse_json(buffer)
        if not partial_object:
            continue
        actions = partial_object.get("actions")
        if not isinstance(actions, list) or len(actions) == 0:
            continue

        if len(actions) > cursor:
            prev_idx = cursor - 1
            prev_action = actions[prev_idx] if prev_idx >= 0 else None
            if prev_action:
                yield {
                    **prev_action,
                    "complete": True,
                    "time": int(time.time() * 1000 - start_time),
                }
                maybe_incomplete = None
            cursor += 1

        cur_idx = cursor - 1
        action = actions[cur_idx] if cur_idx >= 0 else None
        if action:
            if not maybe_incomplete:
                start_time = time.time() * 1000
            maybe_incomplete = action
            yield {
                **action,
                "complete": False,
                "time": int(time.time() * 1000 - start_time),
            }

    if maybe_incomplete:
        yield {
            **maybe_incomplete,
            "complete": True,
            "time": int(time.time() * 1000 - start_time),
        }
