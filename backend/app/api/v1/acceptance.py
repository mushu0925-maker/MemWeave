from __future__ import annotations

from fastapi import APIRouter

from app.schemas.acceptance import AcceptanceRunRequest, AcceptanceRunResponse
from app.services.acceptance_runner import run_acceptance

router = APIRouter(prefix="/acceptance", tags=["acceptance"])


@router.post("/e2e/run", response_model=AcceptanceRunResponse)
def run_e2e_acceptance(payload: AcceptanceRunRequest) -> AcceptanceRunResponse:
    return run_acceptance(payload)
