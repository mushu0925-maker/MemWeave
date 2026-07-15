from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas.system_self_check import SystemSelfCheckResponse
from app.services.system_self_check import build_system_self_check

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/self-check", response_model=SystemSelfCheckResponse)
def read_system_self_check(request: Request) -> SystemSelfCheckResponse:
    available_paths = {
        getattr(route, "path", "")
        for route in request.app.routes
        if getattr(route, "path", "")
    }
    return build_system_self_check(available_paths=available_paths)
