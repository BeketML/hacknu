import json
from functools import lru_cache
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "schemas"


@lru_cache
def _load_schema(mode_type: str) -> dict:
    path = _DATA_DIR / f"{mode_type}.json"
    if not path.is_file():
        fallback = _DATA_DIR / "working.json"
        if fallback.is_file():
            return json.loads(fallback.read_text(encoding="utf8"))
        raise FileNotFoundError(
            f"Response schema not found for mode {mode_type!r}. Run: npm run export-response-schemas in web/"
        )
    return json.loads(path.read_text(encoding="utf8"))


def build_response_schema_dict(mode_part: dict) -> dict:
    mode_type = mode_part.get("modeType") or "working"
    return _load_schema(mode_type)
