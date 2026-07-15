from functools import lru_cache
from typing import Annotated, Literal

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "MemWeave API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"

    frontend_origin: str = "http://localhost:3000"
    cors_origins: Annotated[list[str], Field(default_factory=list)]
    local_frontend_origins: Annotated[
        list[str],
        Field(
            default_factory=lambda: [
                "http://127.0.0.1:3000",
                "http://127.0.0.1:3001",
                "http://127.0.0.1:3002",
                "http://127.0.0.1:3003",
                "http://localhost:3000",
                "http://localhost:3001",
                "http://localhost:3002",
                "http://localhost:3003",
            ]
        ),
    ]

    supabase_url: AnyHttpUrl | None = None
    supabase_service_role_key: str | None = None

    local_data_dir: str = "data"
    local_storage_backend: Literal["json", "sqlite"] = "json"
    local_sqlite_path: str = "data/local_store.sqlite3"

    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_proxy_url: str | None = None
    llm_timeout_seconds: float = 60
    llm_max_retries: int = 0
    llm_model: str = ""
    chat_use_custom_config: bool = False
    chat_api_key: str | None = None
    chat_base_url: str | None = None
    chat_model: str = ""
    persona_use_custom_config: bool = False
    persona_api_key: str | None = None
    persona_base_url: str | None = None
    persona_model: str = ""
    translate_model: str = ""
    evolution_model: str = ""
    vision_use_custom_config: bool = True
    vision_api_key: str | None = None
    vision_base_url: str | None = None
    vision_model: str = ""
    asr_use_custom_config: bool = True
    asr_api_key: str | None = None
    asr_base_url: str | None = None
    asr_model: str = ""
    enable_ai_classification: bool = False
    enable_vision_ocr: bool = False
    enable_asr: bool = False

    enable_voice_generation: bool = False
    voice_generation_provider: str = "indextts2"
    voice_generation_base_url: str | None = None
    voice_generation_timeout_seconds: float = 180
    voice_reference_dir: str = "data/voice_references"
    voice_output_dir: str = "data/voice_outputs"
    voice_video_ffmpeg_path: str = "ffmpeg"
    voice_video_extract_timeout_seconds: float = 120

    @field_validator("supabase_url", mode="before")
    @classmethod
    def empty_optional_url_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    def allowed_origins(self) -> list[str]:
        origins = [self.frontend_origin]
        origins.extend(self.local_frontend_origins)
        origins.extend(self.cors_origins)
        return sorted(set(origin.rstrip("/") for origin in origins if origin))


@lru_cache
def get_settings() -> Settings:
    return Settings()
