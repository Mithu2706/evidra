"""Application configuration.

All secrets (API keys, signing keys) are read from environment variables and
never leave the backend. See `.env.example` at the repository root.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_ROOT.parent / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Core -----------------------------------------------------------------
    environment: Literal["development", "test", "production"] = Field(
        "development", alias="EVIDRA_ENV"
    )
    database_url: str = Field(
        f"sqlite:///{BACKEND_ROOT / 'data' / 'evidra.db'}", alias="EVIDRA_DATABASE_URL"
    )
    storage_dir: Path = Field(BACKEND_ROOT / "data" / "storage", alias="EVIDRA_STORAGE_DIR")
    secret_key: str = Field("dev-only-change-me", alias="EVIDRA_SECRET_KEY")
    token_ttl_hours: int = Field(12, alias="EVIDRA_TOKEN_TTL_HOURS")
    auto_seed: bool = Field(True, alias="EVIDRA_AUTO_SEED")
    cors_origins: str = Field(
        "http://localhost:5173,http://127.0.0.1:5173", alias="EVIDRA_CORS_ORIGINS"
    )

    # --- AI analysis ----------------------------------------------------------
    # "heuristic": deterministic, offline rule-based analyzer (no model calls).
    # "anthropic": Claude via the Anthropic API (requires ANTHROPIC_API_KEY).
    ai_engine: Literal["heuristic", "anthropic"] = Field("heuristic", alias="EVIDRA_AI_ENGINE")
    anthropic_api_key: str | None = Field(None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field("claude-opus-5-5", alias="EVIDRA_ANTHROPIC_MODEL")
    anthropic_effort: Literal["low", "medium", "high", "xhigh", "max"] = Field(
        "high", alias="EVIDRA_ANTHROPIC_EFFORT"
    )
    anthropic_fallbacks: bool = Field(True, alias="EVIDRA_ANTHROPIC_FALLBACKS")

    # --- Ingestion ------------------------------------------------------------
    ocr_engine: Literal["auto", "rapidocr", "tesseract", "none"] = Field(
        "auto", alias="EVIDRA_OCR_ENGINE"
    )
    libreoffice_path: str | None = Field(None, alias="EVIDRA_LIBREOFFICE_PATH")
    render_width_px: int = Field(1600, alias="EVIDRA_RENDER_WIDTH_PX")
    processing_workers: int = Field(2, alias="EVIDRA_PROCESSING_WORKERS")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    if settings.database_url.startswith("sqlite:///"):
        Path(settings.database_url.removeprefix("sqlite:///")).parent.mkdir(
            parents=True, exist_ok=True
        )
    return settings
