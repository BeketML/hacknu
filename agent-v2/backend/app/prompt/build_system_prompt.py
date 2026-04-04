import json
import re

from .get_system_prompt_flags import get_system_prompt_flags
from .intro_section import build_intro_prompt_section
from .response_schema import build_response_schema_dict
from .rules_section import build_rules_prompt_section


def build_system_prompt(prompt: dict, *, with_schema: bool = True) -> str:
    mode_part = prompt.get("mode")
    if not mode_part:
        raise ValueError("A mode part is always required.")

    action_types = mode_part.get("actionTypes") or []
    part_types = mode_part.get("partTypes") or []
    flags = get_system_prompt_flags(action_types, part_types)

    lines = [build_intro_prompt_section(flags), build_rules_prompt_section(flags)]

    if with_schema:
        schema = build_response_schema_dict(mode_part)
        lines.append(
            "## JSON schema\n\n"
            "This is the JSON schema for the events you can return. You must conform to this schema.\n\n"
            f"{json.dumps(schema, indent=2)}\n"
        )

    result = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", result)
