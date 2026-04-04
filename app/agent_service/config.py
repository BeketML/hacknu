import os
from dataclasses import dataclass
from pathlib import Path


def _truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes")


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def repo_root() -> Path:
    raw = os.getenv("REPO_ROOT")
    if raw:
        return Path(raw).resolve()
    return _default_repo_root()


def tldraw_mcp_root() -> Path:
    raw = os.getenv("TLDRAW_MCP_ROOT")
    if raw:
        return Path(raw).resolve()
    return repo_root() / "tldraw_service"


def _allowed_bedrock_model_ids(default_model: str) -> frozenset[str]:
    raw = os.getenv("ALLOWED_BEDROCK_MODEL_IDS", "").strip()
    if raw:
        ids = frozenset(x.strip() for x in raw.split(",") if x.strip())
    else:
        ids = frozenset()
    return ids | frozenset([default_model])


@dataclass(frozen=True)
class Settings:
    tldraw_mcp_root: Path
    tldraw_ws_url: str
    tldraw_ui_url: str
    aws_region: str
    bedrock_model_id: str
    bedrock_temperature: float
    require_tldraw_dist: bool
    allowed_bedrock_model_ids: frozenset[str]


def load_settings() -> Settings:
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "eu-central-1"
    default_model = os.getenv("BEDROCK_MODEL_ID", "eu.anthropic.claude-sonnet-4-6")
    return Settings(
        tldraw_mcp_root=tldraw_mcp_root(),
        tldraw_ws_url=os.getenv("TLDRAW_WS_URL", "ws://localhost:4000"),
        tldraw_ui_url=os.getenv("TLDRAW_UI_URL", "http://localhost:3000"),
        aws_region=region,
        bedrock_model_id=default_model,
        bedrock_temperature=float(os.getenv("BEDROCK_TEMPERATURE", "0.3")),
        require_tldraw_dist=_truthy("REQUIRE_TLDRAW_DIST"),
        allowed_bedrock_model_ids=_allowed_bedrock_model_ids(default_model),
    )


def resolve_bedrock_model_id(requested: object, s: Settings) -> str:
    if not isinstance(requested, str):
        return s.bedrock_model_id
    rid = requested.strip()
    if not rid:
        return s.bedrock_model_id
    if rid in s.allowed_bedrock_model_ids:
        return rid
    return s.bedrock_model_id


settings = load_settings()
