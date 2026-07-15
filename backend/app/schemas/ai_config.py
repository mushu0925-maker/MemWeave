from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AIConfigResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llm_api_key_configured: bool
    llm_api_key_preview: str | None = None
    llm_base_url: str | None = None
    llm_proxy_url: str | None = None
    llm_model: str
    chat_use_custom_config: bool
    chat_api_key_configured: bool
    chat_api_key_preview: str | None = None
    chat_base_url: str | None = None
    chat_model: str
    chat_effective_base_url: str | None = None
    chat_effective_model: str
    chat_enabled: bool
    persona_use_custom_config: bool
    persona_api_key_configured: bool
    persona_api_key_preview: str | None = None
    persona_base_url: str | None = None
    persona_model: str
    persona_effective_base_url: str | None = None
    persona_effective_model: str
    persona_enabled: bool
    translate_model: str
    evolution_model: str
    llm_timeout_seconds: float
    llm_max_retries: int
    vision_use_custom_config: bool
    vision_api_key_configured: bool
    vision_api_key_preview: str | None = None
    vision_base_url: str | None = None
    vision_model: str
    vision_effective_base_url: str | None = None
    vision_effective_model: str
    asr_use_custom_config: bool
    asr_api_key_configured: bool
    asr_api_key_preview: str | None = None
    asr_base_url: str | None = None
    asr_model: str
    asr_effective_base_url: str | None = None
    asr_effective_model: str
    enable_ai_classification: bool
    enable_vision_ocr: bool
    enable_asr: bool
    llm_enabled: bool
    vision_enabled: bool
    asr_enabled: bool


class AIModelOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    note: str


class AIModelOptionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text_models: list[AIModelOption]
    vision_models: list[AIModelOption]
    asr_models: list[AIModelOption]


AIModelDiscoveryFeature = Literal["global", "chat", "classification", "vision", "asr"]


class AIModelDiscoveryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature: AIModelDiscoveryFeature
    status: Literal["available", "empty", "not_configured", "unavailable"]
    source: Literal["provider", "none"]
    models: list[AIModelOption]
    message: str


class AIConnectionTestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    status: str
    provider: str
    model: str
    message: str
    error: str | None = None


class AIConfigUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llm_api_key: str | None = Field(default=None, max_length=4000)
    llm_base_url: str | None = Field(default=None, max_length=500)
    llm_proxy_url: str | None = Field(default=None, max_length=500)
    llm_model: str | None = Field(default=None, max_length=120)
    chat_use_custom_config: bool | None = None
    chat_api_key: str | None = Field(default=None, max_length=4000)
    chat_base_url: str | None = Field(default=None, max_length=500)
    chat_model: str | None = Field(default=None, max_length=120)
    persona_use_custom_config: bool | None = None
    persona_api_key: str | None = Field(default=None, max_length=4000)
    persona_base_url: str | None = Field(default=None, max_length=500)
    persona_model: str | None = Field(default=None, max_length=120)
    translate_model: str | None = Field(default=None, max_length=120)
    evolution_model: str | None = Field(default=None, max_length=120)
    llm_timeout_seconds: float | None = Field(default=None, ge=5, le=300)
    llm_max_retries: int | None = Field(default=None, ge=0, le=5)
    vision_use_custom_config: bool | None = None
    vision_api_key: str | None = Field(default=None, max_length=4000)
    vision_base_url: str | None = Field(default=None, max_length=500)
    vision_model: str | None = Field(default=None, max_length=120)
    asr_use_custom_config: bool | None = None
    asr_api_key: str | None = Field(default=None, max_length=4000)
    asr_base_url: str | None = Field(default=None, max_length=500)
    asr_model: str | None = Field(default=None, max_length=120)
    enable_ai_classification: bool | None = None
    enable_vision_ocr: bool | None = None
    enable_asr: bool | None = None

    @field_validator(
        "llm_api_key",
        "llm_base_url",
        "llm_proxy_url",
        "llm_model",
        "chat_api_key",
        "chat_base_url",
        "chat_model",
        "persona_api_key",
        "persona_base_url",
        "persona_model",
        "translate_model",
        "evolution_model",
        "vision_api_key",
        "vision_base_url",
        "vision_model",
        "asr_api_key",
        "asr_base_url",
        "asr_model",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("llm_base_url", "chat_base_url", "persona_base_url", "vision_base_url", "asr_base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().rstrip("/")
        if cleaned.startswith(("sk-", "sk_")):
            raise ValueError("Base URL must be an http(s) endpoint, not an API key.")
        if not cleaned.startswith(("http://", "https://")):
            raise ValueError("Base URL must start with http:// or https://.")
        return cleaned

    @field_validator("llm_proxy_url")
    @classmethod
    def validate_proxy_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().rstrip("/")
        if cleaned.startswith(("sk-", "sk_")):
            raise ValueError("Proxy URL must be an http(s) proxy endpoint, not an API key.")
        if not cleaned.startswith(("http://", "https://")):
            raise ValueError("Proxy URL must start with http:// or https://.")
        return cleaned
