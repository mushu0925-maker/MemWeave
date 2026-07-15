from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Literal

from app.core.config import get_settings
from app.schemas.ai_config import AIModelDiscoveryResponse, AIModelOption


@dataclass(frozen=True)
class AITextResult:
    text: str
    provider: str
    error: str | None = None


@dataclass(frozen=True)
class AIJSONResult:
    payload: dict[str, Any] | None
    provider: str
    error: str | None = None
    raw_text: str = ""


AIRuntimeFeature = Literal["global", "chat", "classification", "vision", "asr"]


@dataclass(frozen=True)
class AIRuntimeConfig:
    feature: AIRuntimeFeature
    api_key: str | None
    base_url: str | None
    proxy_url: str | None
    timeout_seconds: float
    max_retries: int
    model: str
    use_custom_config: bool
    enabled: bool


def _clean_url(value: object) -> str | None:
    return str(value).rstrip("/") if value else None


def _resolve_value(*, use_custom: bool, custom_value: str | None, fallback_value: str | None) -> str | None:
    if use_custom:
        return custom_value or fallback_value
    return fallback_value


def resolve_ai_runtime_config(feature: AIRuntimeFeature, *, model: str | None = None) -> AIRuntimeConfig:
    settings = get_settings()
    use_custom = False
    custom_api_key: str | None = None
    custom_base_url: str | None = None
    custom_model: str | None = None
    feature_enabled = True

    if feature == "chat":
        use_custom = settings.chat_use_custom_config
        custom_api_key = settings.chat_api_key
        custom_base_url = settings.chat_base_url
        custom_model = settings.chat_model
    elif feature == "classification":
        use_custom = settings.persona_use_custom_config
        custom_api_key = settings.persona_api_key
        custom_base_url = settings.persona_base_url
        custom_model = settings.persona_model
        feature_enabled = settings.enable_ai_classification
    elif feature == "vision":
        use_custom = settings.vision_use_custom_config
        custom_api_key = settings.vision_api_key
        custom_base_url = settings.vision_base_url
        custom_model = settings.vision_model
        feature_enabled = settings.enable_vision_ocr
    elif feature == "asr":
        use_custom = settings.asr_use_custom_config
        custom_api_key = settings.asr_api_key
        custom_base_url = settings.asr_base_url
        custom_model = settings.asr_model
        feature_enabled = settings.enable_asr

    api_key = _resolve_value(use_custom=use_custom, custom_value=custom_api_key, fallback_value=settings.llm_api_key)
    base_url = _resolve_value(
        use_custom=use_custom,
        custom_value=_clean_url(custom_base_url),
        fallback_value=_clean_url(settings.llm_base_url),
    )
    resolved_model = (
        model
        or _resolve_value(use_custom=use_custom, custom_value=custom_model, fallback_value=settings.llm_model)
        or ""
    )
    return AIRuntimeConfig(
        feature=feature,
        api_key=api_key,
        base_url=base_url,
        proxy_url=_clean_url(settings.llm_proxy_url),
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        model=resolved_model,
        use_custom_config=use_custom,
        enabled=feature_enabled and bool(api_key and resolved_model),
    )


def _is_timeout_error(error: str | None) -> bool:
    if not error:
        return False
    lowered = error.lower()
    return "timed out" in lowered or "timeout" in lowered or "readtimeout" in lowered


def _friendly_ai_error(error: str | None, *, attempt_count: int = 1) -> str | None:
    if error is None:
        return None
    if _is_timeout_error(error):
        return (
            "模型服务请求超时：后端已保留原始 raw_source，未生成 persona_items。"
            f"已尝试 {attempt_count} 次仍未拿到模型响应；请稍后重试，或在后端 AI 配置中调大 "
            "LLM_TIMEOUT_SECONDS / 更换模型 / 检查代理与模型服务状态。"
        )
    return error


def _openai_client(config: AIRuntimeConfig) -> Any | None:
    # LLM、视觉和 ASR 共用 OpenAI-compatible 配置；没有 Key 时上层走本地降级路径。
    settings = get_settings()
    if not config.api_key:
        return None

    import httpx
    from openai import OpenAI

    client_kwargs: dict[str, Any] = {
        "api_key": config.api_key,
        "timeout": config.timeout_seconds,
        "max_retries": config.max_retries,
    }
    if config.base_url:
        client_kwargs["base_url"] = config.base_url
    if config.proxy_url:
        client_kwargs.pop("timeout", None)
        client_kwargs["http_client"] = httpx.Client(
            proxy=config.proxy_url,
            timeout=config.timeout_seconds,
        )
    return OpenAI(**client_kwargs)


def _model_discovery_failure_message(exc: Exception) -> str:
    error_name = type(exc).__name__.lower()
    if "timeout" in error_name:
        return "The provider model list request timed out."
    if "authentication" in error_name or "permission" in error_name:
        return "The provider rejected the saved API credentials."
    if "connection" in error_name or "network" in error_name or "apierror" in error_name:
        return "The provider model list is currently unavailable."
    return "The provider model list could not be read."


def discover_models(feature: AIRuntimeFeature) -> AIModelDiscoveryResponse:
    """Read OpenAI-compatible model identifiers without exposing configured credentials."""
    runtime = resolve_ai_runtime_config(feature)
    if not runtime.api_key:
        return AIModelDiscoveryResponse(
            feature=feature,
            status="not_configured",
            source="none",
            models=[],
            message="No saved API key is available for this feature.",
        )

    client = _openai_client(runtime)
    if client is None:
        return AIModelDiscoveryResponse(
            feature=feature,
            status="not_configured",
            source="none",
            models=[],
            message="No saved API key is available for this feature.",
        )

    try:
        response = client.models.list()
    except Exception as exc:
        return AIModelDiscoveryResponse(
            feature=feature,
            status="unavailable",
            source="none",
            models=[],
            message=_model_discovery_failure_message(exc),
        )

    raw_models = getattr(response, "data", response)
    if isinstance(raw_models, dict):
        raw_models = raw_models.get("data", [])

    model_ids: set[str] = set()
    for raw_model in raw_models if isinstance(raw_models, (list, tuple)) else []:
        model_id = raw_model.get("id") if isinstance(raw_model, dict) else getattr(raw_model, "id", None)
        if isinstance(model_id, str) and model_id.strip():
            model_ids.add(model_id.strip())

    models = [
        AIModelOption(
            id=model_id,
            label=model_id,
            note="Provider-discovered identifier. Verify feature support with a real request.",
        )
        for model_id in sorted(model_ids, key=str.casefold)
    ]
    if not models:
        return AIModelDiscoveryResponse(
            feature=feature,
            status="empty",
            source="provider",
            models=[],
            message="The provider returned no model identifiers.",
        )
    return AIModelDiscoveryResponse(
        feature=feature,
        status="available",
        source="provider",
        models=models,
        message="Provider model identifiers were discovered.",
    )


def chat_text(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    temperature: float = 0.2,
    feature: AIRuntimeFeature = "chat",
) -> AITextResult | None:
    runtime = resolve_ai_runtime_config(feature, model=model)
    if not runtime.enabled:
        if not runtime.api_key:
            return None
        return AITextResult(text="", provider=f"{feature}_not_configured", error=f"{feature}_model_missing")
    client = _openai_client(runtime)
    if client is None:
        return None

    try:
        request: dict[str, Any] = {
            "model": runtime.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        response = client.chat.completions.create(**request)
    except Exception as exc:
        return AITextResult(text="", provider=f"openai_compatible_error:{feature}", error=str(exc))

    content = response.choices[0].message.content or ""
    return AITextResult(text=content.strip(), provider=f"openai_compatible:{feature}")


def chat_json_result(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    retry_on_timeout: int = 1,
    feature: AIRuntimeFeature = "classification",
) -> AIJSONResult:
    result: AITextResult | None = None
    attempts = max(1, retry_on_timeout + 1)
    for attempt in range(attempts):
        result = chat_text(system_prompt, user_prompt, model=model, temperature=0, feature=feature)
        if result is None or not _is_timeout_error(result.error):
            break
        if attempt < attempts - 1:
            time.sleep(0.8)
    if result is None:
        return AIJSONResult(
            payload=None,
            provider="not_configured",
            error="llm_client_unavailable_or_api_key_missing",
        )
    if result.error:
        return AIJSONResult(
            payload=None,
            provider=result.provider,
            error=_friendly_ai_error(result.error, attempt_count=attempts if _is_timeout_error(result.error) else 1),
            raw_text=result.text,
        )
    if not result.text:
        return AIJSONResult(
            payload=None,
            provider=result.provider,
            error="empty_model_response",
            raw_text=result.text,
        )

    candidate = result.text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", candidate, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1).strip()

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        return AIJSONResult(
            payload=None,
            provider=result.provider,
            error=f"invalid_json_response: {exc.msg}",
            raw_text=result.text[:2000],
        )
    if not isinstance(parsed, dict):
        return AIJSONResult(
            payload=None,
            provider=result.provider,
            error="invalid_json_root_not_object",
            raw_text=result.text[:2000],
        )
    return AIJSONResult(payload=parsed, provider=result.provider, raw_text=result.text[:2000])


def chat_json(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    feature: AIRuntimeFeature = "classification",
) -> dict[str, Any] | None:
    result = chat_json_result(system_prompt, user_prompt, model=model, feature=feature)
    if result.error:
        return None
    return result.payload


def describe_image(data: bytes, content_type: str, filename: str | None, notes: str) -> AITextResult:
    settings = get_settings()
    # 图片上传和图片识别是两件事；只有视觉模型可用时才读取图中内容。
    settings = get_settings()
    runtime = resolve_ai_runtime_config("vision")
    if not settings.enable_vision_ocr:
        return AITextResult(text="", provider="vision_disabled", error="enable_vision_ocr_false")
    if not runtime.model:
        return AITextResult(text="", provider="vision_not_configured", error="vision_model_missing")
    client = _openai_client(runtime)
    if client is None:
        return AITextResult(text="", provider="vision_not_configured", error="vision_api_key_missing")

    mime = content_type if content_type.startswith("image/") else "image/png"
    image_url = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
    prompt = (
        "请分析这张图片中与记忆人格蒸馏有关的信息。重点不是专业工作流，而是："
        "可见文字/OCR、人物关系线索、情绪氛围、说话方式证据、口头禅、关心行为、"
        "生活习惯、时间地点和不能确定的地方。"
        "只输出能从图片或备注中看见/推断的证据，不要编造。"
        f"\n\n文件名仅作格式参考：{filename or 'untitled'}"
        f"\n上传备注：{notes or '无'}"
    )

    try:
        response = client.chat.completions.create(
            model=runtime.model,
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": "你是记忆资料分析器，负责从图片中抽取可用于人格风格蒸馏的证据。",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                },
            ],
        )
    except Exception as exc:
        return AITextResult(text="", provider="vision_model_error", error=str(exc))

    content = response.choices[0].message.content or ""
    return AITextResult(text=content.strip(), provider=f"vision:{runtime.model}")


def transcribe_audio(data: bytes, filename: str | None, content_type: str) -> AITextResult | None:
    settings = get_settings()
    runtime = resolve_ai_runtime_config("asr")
    if not settings.enable_asr:
        return None
    if not runtime.model:
        return None
    client = _openai_client(runtime)
    if client is None:
        return None

    audio_file = BytesIO(data)
    audio_file.name = filename or "audio.wav"
    try:
        response = client.audio.transcriptions.create(
            model=runtime.model,
            file=audio_file,
        )
    except Exception as exc:
        return AITextResult(text="", provider="asr_model_error", error=str(exc))

    text = getattr(response, "text", None)
    if text is None and isinstance(response, str):
        text = response
    return AITextResult(text=(text or "").strip(), provider=f"asr:{runtime.model}")
