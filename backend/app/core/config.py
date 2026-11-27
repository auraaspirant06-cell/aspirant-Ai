"""Ecosystem configuration loaded from environment variables."""

from __future__ import annotations

import os
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = ROOT_DIR / "data"


class EcosystemSettings(BaseSettings):
    """Typed runtime settings for the Aspirant AI backend and services."""

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Aspirant AI Ecosystem"
    app_version: str = "2.0.0"
    environment: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Database: PostgreSQL in production, SQLite fallback in local dev/test
    database_url: str = Field(
        default_factory=lambda: (
            os.getenv("DATABASE_URL")
            or f"sqlite+aiosqlite:///{(DEFAULT_DATA_DIR / 'aspirant_ecosystem.db').as_posix()}"
        )
    )
    database_echo: bool = False

    # Redis & Celery
    redis_url: str = Field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    celery_broker_url: str = Field(
        default_factory=lambda: os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    )
    celery_result_backend: str = Field(
        default_factory=lambda: os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
    )
    celery_task_always_eager: bool = True

    # Security: JWT + Encryption at rest + HTTPS + Rate Limiting
    jwt_secret_key: str = Field(
        default_factory=lambda: os.getenv("ASPIRANT_JWT_SECRET") or secrets.token_urlsafe(48)
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    encryption_master_key: str = Field(
        default_factory=lambda: os.getenv("ASPIRANT_ENCRYPTION_KEY") or ""
    )
    enforce_https: bool = False
    allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "app://aspirant-nova",
        ]
    )
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60

    # AI Providers & Vector Databases
    gemini_api_key: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    openai_api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_base_url: str = Field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )
    ollama_base_url: str = Field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    )
    primary_chat_model: str = Field(default_factory=lambda: os.getenv("GEMINI_CHAT_MODEL", "gemini-4-argon"))
    fast_chat_model: str = "gemini-3.8-flash"
    deep_research_model: str = Field(default_factory=lambda: os.getenv("GEMINI_REASONING_MODEL", "gemini-4-carbon"))
    live_voice_model: str = Field(default_factory=lambda: os.getenv("GEMINI_LIVE_MODEL", "gemini-3.8-live"))
    tts_model: str = Field(default_factory=lambda: os.getenv("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts"))
    image_model: str = Field(default_factory=lambda: os.getenv("GEMINI_IMAGE_MODEL", "gemini-nano-banana-2.1"))
    video_model: str = Field(default_factory=lambda: os.getenv("GEMINI_VIDEO_MODEL", "gemini-omni-1.2-flash"))

    # Voice, Robot & Guarded Deployment Settings
    default_wake_word: str = Field(
        default_factory=lambda: os.getenv("WAKE_WORD") or os.getenv("ASPIRANT_WAKE_WORD") or "Hey Baby"
    )
    voice_language: str = Field(default_factory=lambda: os.getenv("VOICE_LANGUAGE", "hi-IN"))
    voice_gender: str = Field(default_factory=lambda: os.getenv("VOICE_GENDER", "female"))
    voice_mode: str = Field(default_factory=lambda: os.getenv("VOICE_MODE", "continuous"))
    enable_robot: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_ROBOT", "true").lower() not in {"0", "false", "no"}
    )
    enable_computer_control: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_COMPUTER_CONTROL", "true").lower() not in {"0", "false", "no"}
    )
    deployment_provider: str = Field(default_factory=lambda: os.getenv("DEPLOYMENT_PROVIDER", "azure"))
    ssh_host: str = Field(default_factory=lambda: os.getenv("SSH_HOST", ""))
    ssh_user: str = Field(default_factory=lambda: os.getenv("SSH_USER", "ubuntu"))
    ssh_key_path: str = Field(default_factory=lambda: os.getenv("SSH_KEY_PATH", ""))

    vector_backend: Literal["auto", "qdrant", "chroma", "memory"] = "auto"
    qdrant_url: str = Field(default_factory=lambda: os.getenv("QDRANT_URL", ""))
    qdrant_api_key: str = Field(default_factory=lambda: os.getenv("QDRANT_API_KEY", ""))
    chroma_persist_dir: str = Field(
        default_factory=lambda: str(DEFAULT_DATA_DIR / "chroma_store")
    )
    chroma_host: str = Field(default_factory=lambda: os.getenv("CHROMA_HOST", ""))


@lru_cache(maxsize=1)
def get_settings() -> EcosystemSettings:
    """Return cached singleton settings."""
    DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return EcosystemSettings()
