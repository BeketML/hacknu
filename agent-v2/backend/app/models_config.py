from typing import Literal, NotRequired, TypedDict


class AgentModelDefinition(TypedDict):
    name: str
    id: str
    provider: Literal["openai", "anthropic", "google", "bedrock"]
    thinking: NotRequired[bool]


AGENT_MODEL_DEFINITIONS: dict[str, AgentModelDefinition] = {
    "claude-sonnet-4-5": {
        "name": "claude-sonnet-4-5",
        "id": "eu.anthropic.claude-sonnet-4-6",
        "provider": "bedrock",
    },
    "claude-opus-4-5": {
        "name": "claude-opus-4-5",
        "id": "eu.anthropic.claude-opus-4-20250514-v1:0",
        "provider": "bedrock",
    },
    "gemini-3-pro-preview": {
        "name": "gemini-3-pro-preview",
        "id": "gemini-3-pro-preview",
        "provider": "google",
        "thinking": True,
    },
    "gemini-3-flash-preview": {
        "name": "gemini-3-flash-preview",
        "id": "gemini-3-flash-preview",
        "provider": "google",
    },
    "gpt-5.2-2025-12-11": {
        "name": "gpt-5.2-2025-12-11",
        "id": "gpt-5.2-2025-12-11",
        "provider": "openai",
    },
}

DEFAULT_MODEL_NAME = "claude-sonnet-4-5"


def is_valid_model_name(value: str | None) -> bool:
    return bool(value and value in AGENT_MODEL_DEFINITIONS)


def get_agent_model_definition(model_name: str) -> AgentModelDefinition:
    definition = AGENT_MODEL_DEFINITIONS.get(model_name)
    if not definition:
        raise ValueError(f"Model {model_name} not found")
    return definition
