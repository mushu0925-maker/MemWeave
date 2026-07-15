from __future__ import annotations

from app.core.config import get_settings
from app.schemas.ai_config import AIConnectionTestResponse
from app.services.ai_gateway import chat_text


def test_ai_connection() -> AIConnectionTestResponse:
    settings = get_settings()
    model = settings.llm_model
    if not settings.llm_api_key:
        return AIConnectionTestResponse(
            ok=False,
            status="skipped",
            provider="not_configured",
            model=model,
            message="API key is not configured.",
            error="llm_api_key_missing",
        )

    result = chat_text(
        "You are an API connectivity checker. Reply with exactly: ok",
        "Reply with exactly: ok",
        model=model,
        temperature=0,
        feature="global",
    )
    if result is None:
        return AIConnectionTestResponse(
            ok=False,
            status="skipped",
            provider="not_configured",
            model=model,
            message="LLM client is unavailable.",
            error="llm_client_unavailable",
        )
    if result.error:
        return AIConnectionTestResponse(
            ok=False,
            status="failed",
            provider=result.provider,
            model=model,
            message="Model request failed.",
            error=result.error[:1000],
        )

    return AIConnectionTestResponse(
        ok=True,
        status="success",
        provider=result.provider,
        model=model,
        message=(result.text or "ok")[:200],
        error=None,
    )
