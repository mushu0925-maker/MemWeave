from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.services.ai_gateway import AIRuntimeConfig, discover_models


def runtime(api_key: str | None) -> AIRuntimeConfig:
    return AIRuntimeConfig(
        feature="vision",
        api_key=api_key,
        base_url="https://provider.example/v1",
        proxy_url=None,
        timeout_seconds=15,
        max_retries=0,
        model="configured-model",
        use_custom_config=True,
        enabled=True,
    )


def run() -> None:
    secret = "super-secret-provider-key"
    client = SimpleNamespace(
        models=SimpleNamespace(
            list=lambda: SimpleNamespace(
                data=[
                    SimpleNamespace(id="vision-pro"),
                    SimpleNamespace(id="alpha"),
                    SimpleNamespace(id="vision-pro"),
                    SimpleNamespace(id=None),
                ]
            )
        )
    )
    with patch("app.services.ai_gateway.resolve_ai_runtime_config", return_value=runtime(secret)), patch(
        "app.services.ai_gateway._openai_client", return_value=client
    ):
        result = discover_models("vision")
    assert result.status == "available"
    assert [item.id for item in result.models] == ["alpha", "vision-pro"]
    assert secret not in result.model_dump_json()

    with patch("app.services.ai_gateway.resolve_ai_runtime_config", return_value=runtime(None)):
        no_key_result = discover_models("vision")
    assert no_key_result.status == "not_configured"
    assert no_key_result.models == []

    failing_client = SimpleNamespace(models=SimpleNamespace(list=lambda: (_ for _ in ()).throw(RuntimeError(secret))))
    with patch("app.services.ai_gateway.resolve_ai_runtime_config", return_value=runtime(secret)), patch(
        "app.services.ai_gateway._openai_client", return_value=failing_client
    ):
        error_result = discover_models("vision")
    assert error_result.status == "unavailable"
    assert secret not in error_result.model_dump_json()

    print("model discovery smoke passed")


if __name__ == "__main__":
    run()
