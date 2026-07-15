from __future__ import annotations

from fastapi import APIRouter

from app.schemas.distillation_plugin import (
    DistillationPluginPolicy,
    DistillationPluginPolicyUpdate,
    DistillationPluginRegistryResponse,
)
from app.services.distillation_plugin_store import (
    get_current_distillation_policy,
    list_distillation_plugins,
    reset_current_distillation_policy,
    update_current_distillation_policy,
)

router = APIRouter(prefix="/distillation-plugins", tags=["distillation_plugins"])


@router.get("", response_model=DistillationPluginRegistryResponse)
def read_distillation_plugins() -> DistillationPluginRegistryResponse:
    return list_distillation_plugins()


@router.get("/current", response_model=DistillationPluginPolicy)
def read_current_distillation_plugin() -> DistillationPluginPolicy:
    return get_current_distillation_policy()


@router.patch("/current", response_model=DistillationPluginPolicy)
def patch_current_distillation_plugin(payload: DistillationPluginPolicyUpdate) -> DistillationPluginPolicy:
    return update_current_distillation_policy(payload)


@router.post("/current/reset", response_model=DistillationPluginPolicy)
def reset_current_distillation_plugin() -> DistillationPluginPolicy:
    return reset_current_distillation_policy()
