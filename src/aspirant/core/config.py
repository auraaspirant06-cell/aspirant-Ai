"""Typed application settings and safe path resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_project_root() -> Path:
    """Resolve the project root directory from this module's location."""
    return Path(__file__).resolve().parents[3]


class AppSettings(BaseSettings):
    """Central configuration loaded from environment and optional .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    host: str = Field(default="127.0.0.1", alias="ASPIRANT_HOST")
    port: int = Field(default=8420, alias="ASPIRANT_PORT")
    project_root: Path = Field(default_factory=default_project_root)
    data_dir: Path | None = Field(default=None, alias="ASPIRANT_DATA_DIR")
    restricted_mode: bool = Field(default=False, alias="ASPIRANT_RESTRICTED_MODE")
    ram_budget_mb: int = Field(default=320, alias="ASPIRANT_RAM_BUDGET_MB")

    # Provider credentials (read via env; never logged or exposed in API responses)
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1", alias="OPENAI_BASE_URL"
    )
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434", alias="OLLAMA_BASE_URL"
    )
    elevenlabs_api_key: str | None = Field(default=None, alias="ELEVENLABS_API_KEY")

    # Verified Gemini model configuration
    gemini_chat_model: str = Field(default="gemini-4-hydrogen", alias="GEMINI_CHAT_MODEL")
    gemini_reasoning_model: str = Field(
        default="gemini-4-carbon", alias="GEMINI_REASONING_MODEL"
    )
    gemini_live_model: str = Field(default="gemini-3.8-live", alias="GEMINI_LIVE_MODEL")
    gemini_tts_model: str = Field(default="gemini-3.8-flash-tts", alias="GEMINI_TTS_MODEL")
    gemini_image_model: str = Field(
        default="gemini-nano-banana-2.1", alias="GEMINI_IMAGE_MODEL"
    )
    gemini_video_model: str = Field(
        default="gemini-omni-1.2-flash", alias="GEMINI_VIDEO_MODEL"
    )

    # Voice & media defaults
    wake_word: str = Field(
        default="Hey Baby",
        validation_alias=AliasChoices("ASPIRANT_WAKE_WORD", "WAKE_WORD"),
    )
    voice_language: str = Field(
        default="hi-IN",
        validation_alias=AliasChoices("ASPIRANT_VOICE_LANGUAGE", "VOICE_LANGUAGE"),
    )
    voice_gender: Literal["female", "male"] = Field(
        default="female",
        validation_alias=AliasChoices("ASPIRANT_VOICE_GENDER", "VOICE_GENDER"),
    )
    voice_mode: str = Field(
        default="continuous",
        validation_alias=AliasChoices("ASPIRANT_VOICE_MODE", "VOICE_MODE"),
    )
    voice_default_tts: str = Field(default="auto", alias="ASPIRANT_VOICE_DEFAULT_TTS")
    voice_female_en: str = Field(
        default="en-IN-NeerjaNeural", alias="ASPIRANT_VOICE_FEMALE_EN"
    )
    voice_female_hi: str = Field(
        default="hi-IN-SwaraNeural", alias="ASPIRANT_VOICE_FEMALE_HI"
    )
    voice_male_en: str = Field(
        default="en-IN-PrabhatNeural", alias="ASPIRANT_VOICE_MALE_EN"
    )
    voice_male_hi: str = Field(
        default="hi-IN-MadhurNeural", alias="ASPIRANT_VOICE_MALE_HI"
    )
    stt_provider: str = Field(default="auto", alias="ASPIRANT_STT_PROVIDER")
    whisper_model: Literal["tiny", "base", "small"] = Field(
        default="tiny", alias="ASPIRANT_WHISPER_MODEL"
    )
    image_provider: str = Field(default="gemini", alias="ASPIRANT_IMAGE_PROVIDER")
    video_provider: str = Field(
        default="gemini-omni", alias="ASPIRANT_VIDEO_PROVIDER"
    )

    # Interactive 3D Robot, PC Control & Deployment Defaults
    enable_robot: bool = Field(default=True, alias="ENABLE_ROBOT")
    enable_computer_control: bool = Field(default=True, alias="ENABLE_COMPUTER_CONTROL")
    deployment_provider: str = Field(default="azure", alias="DEPLOYMENT_PROVIDER")
    ssh_host: str = Field(default="", alias="SSH_HOST")
    ssh_user: str = Field(default="ubuntu", alias="SSH_USER")
    ssh_key_path: str = Field(default="", alias="SSH_KEY_PATH")

    @field_validator("host")
    @classmethod
    def enforce_loopback_host(cls, value: str) -> str:
        """Restrict internal control server to loopback addresses by default."""
        normalized = value.strip().lower()
        if normalized not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError(
                f"ASPIRANT_HOST must be loopback-only (got {value!r}) for local security."
            )
        return value.strip()

    @property
    def resolved_data_dir(self) -> Path:
        if self.data_dir is None:
            return (self.project_root / "data").resolve()
        if self.data_dir.is_absolute():
            return self.data_dir.resolve()
        return (self.project_root / self.data_dir).resolve()

    @property
    def outputs_dir(self) -> Path:
        return self.resolved_data_dir / "outputs"

    @property
    def browser_profile_dir(self) -> Path:
        return self.resolved_data_dir / "browser_profile"

    @property
    def memory_db_path(self) -> Path:
        return self.resolved_data_dir / "memory.db"

    @property
    def audit_db_path(self) -> Path:
        return self.resolved_data_dir / "audit.db"

    @property
    def vault_path(self) -> Path:
        return self.resolved_data_dir / "vault.enc"

    @property
    def token_path(self) -> Path:
        return self.resolved_data_dir / ".api_token"

    def ensure_directories(self) -> None:
        """Create required local runtime directories."""
        for folder in (
            self.resolved_data_dir,
            self.outputs_dir,
            self.browser_profile_dir,
        ):
            folder.mkdir(parents=True, exist_ok=True)

    def provider_status_summary(self) -> list[dict[str, object]]:
        """Return non-sensitive connection readiness for configured AI providers."""
        return [
            {
                "id": "gemini",
                "name": "Google Gemini",
                "role": "Primary LLM, Multimodal, Live, Image, Video",
                "configured": bool(self.gemini_api_key),
                "mode": "cloud",
            },
            {
                "id": "openai",
                "name": "OpenAI-Compatible",
                "role": "LLM / Whisper / Image fallback",
                "configured": bool(self.openai_api_key or self.groq_api_key),
                "mode": "cloud",
            },
            {
                "id": "ollama",
                "name": "Ollama (Local)",
                "role": "Offline local LLMs (1B-3B recommended on 8 GB RAM)",
                "configured": bool(self.ollama_base_url),
                "mode": "local",
            },
            {
                "id": "edge_tts",
                "name": "Female Neural TTS",
                "role": f"{self.voice_female_en} / {self.voice_female_hi}",
                "configured": True,
                "mode": "hybrid",
            },
        ]
