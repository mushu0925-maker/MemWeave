from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.services.runtime_module_settings import (
    reset_runtime_module_settings,
    runtime_module_settings_record,
    update_runtime_module_settings,
)

router = APIRouter(prefix="/runtime-modules", tags=["runtime_modules"])


@router.get("/settings")
def read_runtime_module_settings() -> dict[str, Any]:
    return runtime_module_settings_record()


@router.patch("/settings")
def patch_runtime_module_settings(payload: dict[str, Any]) -> dict[str, Any]:
    return update_runtime_module_settings(payload).__dict__


@router.post("/settings/reset")
def reset_runtime_module_settings_endpoint() -> dict[str, Any]:
    return reset_runtime_module_settings().__dict__
