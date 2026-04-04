from .prompt_sections import build_system_prompt_base

# Backward-compatible alias: full base system prompt without UI/WS lines.
SYSTEM_PROMPT = build_system_prompt_base()

_DEFAULT_CANVAS_PLACEHOLDER = (
    "(No client-provided canvas snapshot; use get_snapshot to read the board before editing.)"
)

_USER_TEMPLATE = """
<conversation_memory>
{conversation_history}
</conversation_memory>

<canvas_context>
{canvas_context}
</canvas_context>

<user_query>
User Query: {user_query}
</user_query>

Based on the conversational memory, the canvas context above, and the user query, execute the necessary MCP tool calls.
If the canvas context indicates no client snapshot, rely on get_snapshot to infer layout before placing elements.
Use explicit positions from the canvas context when provided; otherwise derive placement after get_snapshot.
"""


def build_user_prompt(
    conversation_history: str,
    user_query: str,
    canvas_context: str | None = None,
) -> str:
    block = (canvas_context or "").strip()
    if not block:
        block = _DEFAULT_CANVAS_PLACEHOLDER
    return _normalize_user_prompt(
        _USER_TEMPLATE.format(
            conversation_history=conversation_history,
            canvas_context=block,
            user_query=user_query,
        )
    )


def _normalize_user_prompt(text: str) -> str:
    lines = [ln.rstrip() for ln in text.strip().splitlines()]
    return "\n".join(lines).strip() + "\n"


# Legacy template for callers that still use .format manually (avoid if possible).
USER_PROMPT = _USER_TEMPLATE
