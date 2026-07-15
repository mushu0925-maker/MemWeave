from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter

from app.services.profile_store import get_profile
from app.services.runtime_gate import (
    get_runtime_gate_settings,
    reset_runtime_gate_settings,
    update_runtime_gate_settings,
)
from app.services.runtime_persona_items import build_runtime_gate_diagnostics

router = APIRouter(prefix="/runtime-gate", tags=["runtime_gate"])


@router.get("/settings")
def read_runtime_gate_settings() -> dict[str, Any]:
    return get_runtime_gate_settings().__dict__


@router.patch("/settings")
def patch_runtime_gate_settings(payload: dict[str, Any]) -> dict[str, Any]:
    return update_runtime_gate_settings(payload).__dict__


@router.post("/settings/reset")
def reset_runtime_gate_settings_endpoint() -> dict[str, Any]:
    return reset_runtime_gate_settings().__dict__


@router.get("/profiles/{profile_id}/diagnostics")
def read_runtime_gate_profile_diagnostics(profile_id: UUID) -> dict[str, object]:
    get_profile(profile_id)
    return build_runtime_gate_diagnostics(profile_id)
