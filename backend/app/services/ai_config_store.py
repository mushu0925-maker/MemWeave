from __future__ import annotations

import os
from pathlib import Path

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.schemas.ai_config import AIConfigResponse, AIConfigUpdateRequest, AIModelOption, AIModelOptionsResponse

CONFIG_KEYS = {
    "llm_api_key": "LLM_API_KEY",
    "llm_base_url": "LLM_BASE_URL",
    "llm_proxy_url": "LLM_PROXY_URL",
    "llm_model": "LLM_MODEL",
    "chat_use_custom_config": "CHAT_USE_CUSTOM_CONFIG",
    "chat_api_key": "CHAT_API_KEY",
    "chat_base_url": "CHAT_BASE_URL",
    "chat_model": "CHAT_MODEL",
    "persona_use_custom_config": "PERSONA_USE_CUSTOM_CONFIG",
    "persona_api_key": "PERSONA_API_KEY",
    "persona_base_url": "PERSONA_BASE_URL",
    "persona_model": "PERSONA_MODEL",
    "translate_model": "TRANSLATE_MODEL",
    "evolution_model": "EVOLUTION_MODEL",
    "llm_timeout_seconds": "LLM_TIMEOUT_SECONDS",
    "llm_max_retries": "LLM_MAX_RETRIES",
    "vision_use_custom_config": "VISION_USE_CUSTOM_CONFIG",
    "vision_api_key": "VISION_API_KEY",
    "vision_base_url": "VISION_BASE_URL",
    "vision_model": "VISION_MODEL",
    "asr_use_custom_config": "ASR_USE_CUSTOM_CONFIG",
    "asr_api_key": "ASR_API_KEY",
    "asr_base_url": "ASR_BASE_URL",
    "asr_model": "ASR_MODEL",
    "enable_ai_classification": "ENABLE_AI_CLASSIFICATION",
    "enable_vision_ocr": "ENABLE_VISION_OCR",
    "enable_asr": "ENABLE_ASR",
}


def env_path() -> Path:
    configured = os.getenv("MEMWEAVE_CONFIG_DIR")
    if configured:
        directory = Path(configured)
        directory.mkdir(parents=True, exist_ok=True)
        return directory / ".env"
    return Path(__file__).resolve().parents[2] / ".env"


def _key_preview(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _clean_url(value: str | None) -> str | None:
    return str(value).rstrip("/") if value else None


def _effective_value(*, use_custom: bool, custom_value: str | None, fallback_value: str | None) -> str | None:
    if use_custom:
        return custom_value or fallback_value
    return fallback_value


def read_ai_config() -> AIConfigResponse:
    settings = get_settings()
    has_key = bool(settings.llm_api_key)
    global_base_url = _clean_url(settings.llm_base_url)
    chat_effective_key = _effective_value(
        use_custom=settings.chat_use_custom_config,
        custom_value=settings.chat_api_key,
        fallback_value=settings.llm_api_key,
    )
    chat_effective_base_url = _effective_value(
        use_custom=settings.chat_use_custom_config,
        custom_value=_clean_url(settings.chat_base_url),
        fallback_value=global_base_url,
    )
    chat_effective_model = (
        _effective_value(
            use_custom=settings.chat_use_custom_config,
            custom_value=settings.chat_model,
            fallback_value=settings.llm_model,
        )
        or settings.llm_model
    )
    persona_effective_key = _effective_value(
        use_custom=settings.persona_use_custom_config,
        custom_value=settings.persona_api_key,
        fallback_value=settings.llm_api_key,
    )
    persona_effective_base_url = _effective_value(
        use_custom=settings.persona_use_custom_config,
        custom_value=_clean_url(settings.persona_base_url),
        fallback_value=global_base_url,
    )
    persona_effective_model = (
        _effective_value(
            use_custom=settings.persona_use_custom_config,
            custom_value=settings.persona_model,
            fallback_value=settings.llm_model,
        )
        or settings.llm_model
    )
    vision_effective_key = _effective_value(
        use_custom=settings.vision_use_custom_config,
        custom_value=settings.vision_api_key,
        fallback_value=settings.llm_api_key,
    )
    vision_effective_base_url = _effective_value(
        use_custom=settings.vision_use_custom_config,
        custom_value=_clean_url(settings.vision_base_url),
        fallback_value=global_base_url,
    )
    vision_effective_model = (
        _effective_value(
            use_custom=settings.vision_use_custom_config,
            custom_value=settings.vision_model,
            fallback_value=settings.llm_model,
        )
        or settings.llm_model
    )
    asr_effective_key = _effective_value(
        use_custom=settings.asr_use_custom_config,
        custom_value=settings.asr_api_key,
        fallback_value=settings.llm_api_key,
    )
    asr_effective_base_url = _effective_value(
        use_custom=settings.asr_use_custom_config,
        custom_value=_clean_url(settings.asr_base_url),
        fallback_value=global_base_url,
    )
    asr_effective_model = (
        _effective_value(
            use_custom=settings.asr_use_custom_config,
            custom_value=settings.asr_model,
            fallback_value=settings.llm_model,
        )
        or settings.llm_model
    )
    translate_model = settings.translate_model or settings.llm_model
    evolution_model = settings.evolution_model or settings.llm_model
    return AIConfigResponse(
        llm_api_key_configured=has_key,
        llm_api_key_preview=_key_preview(settings.llm_api_key),
        llm_base_url=global_base_url,
        llm_proxy_url=_clean_url(settings.llm_proxy_url),
        llm_model=settings.llm_model,
        chat_use_custom_config=settings.chat_use_custom_config,
        chat_api_key_configured=bool(settings.chat_api_key),
        chat_api_key_preview=_key_preview(settings.chat_api_key),
        chat_base_url=_clean_url(settings.chat_base_url),
        chat_model=settings.chat_model,
        chat_effective_base_url=chat_effective_base_url,
        chat_effective_model=chat_effective_model,
        chat_enabled=bool(chat_effective_key and chat_effective_model),
        persona_use_custom_config=settings.persona_use_custom_config,
        persona_api_key_configured=bool(settings.persona_api_key),
        persona_api_key_preview=_key_preview(settings.persona_api_key),
        persona_base_url=_clean_url(settings.persona_base_url),
        persona_model=settings.persona_model,
        persona_effective_base_url=persona_effective_base_url,
        persona_effective_model=persona_effective_model,
        persona_enabled=settings.enable_ai_classification and bool(persona_effective_key and persona_effective_model),
        translate_model=translate_model,
        evolution_model=evolution_model,
        llm_timeout_seconds=settings.llm_timeout_seconds,
        llm_max_retries=settings.llm_max_retries,
        vision_use_custom_config=settings.vision_use_custom_config,
        vision_api_key_configured=bool(settings.vision_api_key),
        vision_api_key_preview=_key_preview(settings.vision_api_key),
        vision_base_url=_clean_url(settings.vision_base_url),
        vision_model=settings.vision_model,
        vision_effective_base_url=vision_effective_base_url,
        vision_effective_model=vision_effective_model,
        asr_use_custom_config=settings.asr_use_custom_config,
        asr_api_key_configured=bool(settings.asr_api_key),
        asr_api_key_preview=_key_preview(settings.asr_api_key),
        asr_base_url=_clean_url(settings.asr_base_url),
        asr_model=settings.asr_model,
        asr_effective_base_url=asr_effective_base_url,
        asr_effective_model=asr_effective_model,
        enable_ai_classification=settings.enable_ai_classification,
        enable_vision_ocr=settings.enable_vision_ocr,
        enable_asr=settings.enable_asr,
        llm_enabled=has_key,
        vision_enabled=settings.enable_vision_ocr and bool(vision_effective_key and vision_effective_model),
        asr_enabled=settings.enable_asr and bool(asr_effective_key and asr_effective_model),
    )


def read_model_options() -> AIModelOptionsResponse:
    return AIModelOptionsResponse(
        text_models=[
            AIModelOption(id="deepseek-v4-flash", label="deepseek-v4-flash", note="DeepSeek 当前推荐低成本文本模型，适合资料分类、翻译和 skill 进化。"),
            AIModelOption(id="deepseek-v4-pro", label="deepseek-v4-pro", note="DeepSeek 更强文本模型，适合高质量总结和复杂资料归纳。"),
            AIModelOption(id="gpt-4o-mini", label="gpt-4o-mini", note="通用默认模型，适合资料分类、翻译和低成本测试。"),
            AIModelOption(id="gpt-4o", label="gpt-4o", note="更强的通用模型，适合复杂资料分类和高质量生成。"),
            AIModelOption(id="gpt-4.1-mini", label="gpt-4.1-mini", note="适合较长文本处理和结构化提取。"),
            AIModelOption(id="deepseek-chat", label="deepseek-chat", note="DeepSeek 旧别名，当前仍兼容，计划于 2026-07-24 废弃。"),
            AIModelOption(id="deepseek-reasoner", label="deepseek-reasoner", note="DeepSeek 旧推理别名，当前仍兼容，计划于 2026-07-24 废弃。"),
        ],
        vision_models=[
            AIModelOption(id="gpt-4o-mini", label="gpt-4o-mini", note="默认视觉/OCR 模型，适合图片记忆和截图文字识别。"),
            AIModelOption(id="gpt-4o", label="gpt-4o", note="更强视觉理解，适合复杂照片、手写内容和多图线索。"),
            AIModelOption(id="gpt-4.1-mini", label="gpt-4.1-mini", note="可用于兼容视觉输入的 OpenAI-compatible 服务。"),
        ],
        asr_models=[
            AIModelOption(id="whisper-1", label="whisper-1", note="默认语音转写模型。"),
            AIModelOption(id="gpt-4o-mini-transcribe", label="gpt-4o-mini-transcribe", note="新式转写模型名称，取决于服务商兼容性。"),
            AIModelOption(id="gpt-4o-transcribe", label="gpt-4o-transcribe", note="更高质量转写模型名称，取决于服务商兼容性。"),
        ],
    )


def _read_env_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def _format_env_line(key: str, value: str | None) -> str:
    if not value:
        return f"{key}="
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'{key}="{escaped}"'


def _reject_multiline_env_value(value: str | None) -> str | None:
    if value is None:
        return None
    if "\r" in value or "\n" in value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="AI config values cannot contain line breaks.",
        )
    return value


def _config_value(raw_value: object) -> str | None:
    if isinstance(raw_value, bool):
        return "true" if raw_value else "false"
    if isinstance(raw_value, (int, float)):
        return str(raw_value)
    if isinstance(raw_value, str):
        value = raw_value.strip()
        return _reject_multiline_env_value(value or None)
    return None


def _write_env_values(values: dict[str, str | None]) -> None:
    path = env_path()
    lines = _read_env_lines(path)
    seen: set[str] = set()
    next_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            next_lines.append(line)
            continue

        key = line.split("=", 1)[0].strip()
        if key in values:
            if values[key] is not None:
                next_lines.append(_format_env_line(key, values[key]))
            seen.add(key)
        else:
            next_lines.append(line)

    if next_lines and next_lines[-1].strip():
        next_lines.append("")
    for key, value in values.items():
        if key not in seen and value is not None:
            next_lines.append(_format_env_line(key, value))

    path.write_text("\n".join(next_lines).rstrip() + "\n", encoding="utf-8")


def _apply_process_environment(values: dict[str, str | None]) -> None:
    for key, value in values.items():
        if value:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)


def update_ai_config(payload: AIConfigUpdateRequest) -> AIConfigResponse:
    updates: dict[str, str | None] = {}
    for field_name, env_key in CONFIG_KEYS.items():
        if field_name not in payload.model_fields_set:
            continue
        raw_value = getattr(payload, field_name)
        updates[env_key] = _config_value(raw_value)

    if updates:
        _write_env_values(updates)
        _apply_process_environment(updates)
        get_settings.cache_clear()

    return read_ai_config()
