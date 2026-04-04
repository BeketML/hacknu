from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PACKAGE_ROOT = Path(__file__).resolve().parent
_BACKEND_ROOT = _PACKAGE_ROOT.parent.parent

_ENV_FILE_PATHS: list[str] = []
for _env_candidate in (_BACKEND_ROOT / ".env", _BACKEND_ROOT.parent.parent / ".env"):
    if _env_candidate.is_file():
        _ENV_FILE_PATHS.append(str(_env_candidate))

_SETTINGS_KWARGS: dict = {
    "env_file_encoding": "utf-8",
    "case_sensitive": False,
    "extra": "ignore",
}
if _ENV_FILE_PATHS:
    _SETTINGS_KWARGS["env_file"] = _ENV_FILE_PATHS


class ImageGenSettings(BaseSettings):
    model_config = SettingsConfigDict(**_SETTINGS_KWARGS)

    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    perplexity_api_key: str = Field(default="", alias="PERPLEXITY_API_KEY")

    gemini_text_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_TEXT_MODEL")
    gemini_image_model: str = Field(
        default="gemini-2.5-flash-image", alias="GEMINI_IMAGE_MODEL"
    )
    imagen_model: str = Field(default="imagen-4.0-fast-generate-001", alias="IMAGEN_MODEL")

    perplexity_base_url: str = Field(
        default="https://api.perplexity.ai", alias="PERPLEXITY_BASE_URL"
    )
    perplexity_model_fast: str = Field(default="sonar", alias="PERPLEXITY_MODEL_FAST")
    perplexity_model_normal: str = Field(default="sonar-pro", alias="PERPLEXITY_MODEL_NORMAL")
    perplexity_model_deep: str = Field(
        default="sonar-reasoning-pro", alias="PERPLEXITY_MODEL_DEEP"
    )

    scenario_default_num_slides: int = Field(default=4, alias="SCENARIO_DEFAULT_NUM_SLIDES")
    scenario_gap_detection_temperature: float = Field(
        default=0.3, alias="SCENARIO_GAP_DETECTION_TEMPERATURE"
    )
    scenario_gap_detection_max_tokens: int = Field(
        default=1024, alias="SCENARIO_GAP_DETECTION_MAX_TOKENS"
    )
    scenario_generation_temperature: float = Field(
        default=0.7, alias="SCENARIO_GENERATION_TEMPERATURE"
    )
    scenario_generation_max_tokens: int = Field(
        default=4096, alias="SCENARIO_GENERATION_MAX_TOKENS"
    )
    scenario_max_research_queries: int = Field(default=4, alias="SCENARIO_MAX_RESEARCH_QUERIES")
    scenario_default_research_depth: Literal["fast", "normal", "deep"] = Field(
        default="normal", alias="SCENARIO_DEFAULT_RESEARCH_DEPTH"
    )

    visual_generation_temperature: float = Field(
        default=1.0, alias="VISUAL_GENERATION_TEMPERATURE"
    )
    visual_default_aspect_ratio: str = Field(default="16:9", alias="VISUAL_DEFAULT_ASPECT_RATIO")

    context_dir: Path = Field(default=_PACKAGE_ROOT / "context", alias="IMAGEGEN_CONTEXT_DIR")
    artifacts_dir: Path = Field(
        default=_BACKEND_ROOT / "data" / "imagegen_artifacts",
        alias="IMAGEGEN_ARTIFACTS_DIR",
    )

    image_extensions: frozenset[str] = Field(
        default=frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}),
        alias="IMAGE_EXTENSIONS",
        exclude=True,
    )

    @property
    def static_context_dir(self) -> Path:
        return self.context_dir / "static"

    @property
    def temporary_context_dir(self) -> Path:
        return self.context_dir / "temporary"

    @property
    def perplexity_model_map(self) -> dict[str, str]:
        return {
            "fast": self.perplexity_model_fast,
            "normal": self.perplexity_model_normal,
            "deep": self.perplexity_model_deep,
        }


@lru_cache
def get_settings() -> ImageGenSettings:
    return ImageGenSettings()


def require_google_key() -> ImageGenSettings:
    s = get_settings()
    if not (s.google_api_key or "").strip():
        raise ValueError("GOOGLE_API_KEY is required for image generation")
    return s
