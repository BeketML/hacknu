"""Golden checks for Python prompt parity; pair with `npm run dev` + `uvicorn` for full UI smoke tests."""
import json
from pathlib import Path

from app.prompt.build_messages import build_messages
from app.prompt.build_system_prompt import build_system_prompt
from app.schemas.agent_prompt import AgentPromptModel, validated_prompt_to_dict

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "minimal_working_prompt.json"


def _minimal_prompt() -> dict:
    raw = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    m = AgentPromptModel.model_validate(raw)
    return validated_prompt_to_dict(m)


def test_validate_minimal_prompt():
    _minimal_prompt()


def test_build_system_prompt_contains_schema_and_rules():
    p = _minimal_prompt()
    text = build_system_prompt(p)
    assert "## JSON schema" in text
    assert "## Shapes" in text
    assert "working" in json.dumps(p.get("mode", {}))


def test_build_messages_orders_user_content():
    p = _minimal_prompt()
    msgs = build_messages(p)
    assert len(msgs) >= 1
    assert msgs[-1]["role"] == "user"


def test_golden_system_prompt_snapshot():
    p = _minimal_prompt()
    text = build_system_prompt(p, with_schema=False)
    golden_path = Path(__file__).resolve().parent / "golden" / "system_prompt_no_schema.txt"
    if not golden_path.is_file():
        import pytest

        pytest.skip("Golden file missing; add tests/golden/system_prompt_no_schema.txt after regenerating locally.")
    assert text.strip() == golden_path.read_text(encoding="utf-8").strip()
