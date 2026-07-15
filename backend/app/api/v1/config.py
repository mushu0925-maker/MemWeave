from __future__ import annotations

from fastapi import APIRouter

from app.schemas.ai_config import (
    AIConfigResponse,
    AIConfigUpdateRequest,
    AIConnectionTestResponse,
    AIModelDiscoveryFeature,
    AIModelDiscoveryResponse,
    AIModelOptionsResponse,
)
from app.services.ai_diagnostics import test_ai_connection
from app.services.ai_config_store import read_ai_config, read_model_options, update_ai_config
from app.services.ai_gateway import discover_models

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/ai", response_model=AIConfigResponse)
def read_ai_runtime_config() -> AIConfigResponse:
    return read_ai_config()


@router.patch("/ai", response_model=AIConfigResponse)
def update_ai_runtime_config(payload: AIConfigUpdateRequest) -> AIConfigResponse:
    return update_ai_config(payload)


@router.get("/ai/models", response_model=AIModelOptionsResponse)
def read_ai_model_options() -> AIModelOptionsResponse:
    return read_model_options()


@router.get("/ai/models/discover", response_model=AIModelDiscoveryResponse)
def discover_ai_models(feature: AIModelDiscoveryFeature = "global") -> AIModelDiscoveryResponse:
    return discover_models(feature)


@router.post("/ai/test", response_model=AIConnectionTestResponse)
def test_ai_runtime_connection() -> AIConnectionTestResponse:
    return test_ai_connection()
