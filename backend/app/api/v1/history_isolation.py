from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.schemas.history_isolation import HistoryIsolationRequest, HistoryIsolationResponse
from app.services.history_pollution_isolation import (
    apply_history_pollution_isolation,
    preview_history_pollution_isolation,
)
from app.services.profile_store import get_profile

router = APIRouter(prefix="/history-isolation", tags=["history_isolation"])


@router.post("/profiles/{profile_id}/preview", response_model=HistoryIsolationResponse)
def preview_history_isolation(profile_id: UUID, payload: HistoryIsolationRequest) -> HistoryIsolationResponse:
    get_profile(profile_id)
    return preview_history_pollution_isolation(profile_id, payload)


@router.post("/profiles/{profile_id}/apply", response_model=HistoryIsolationResponse)
def apply_history_isolation(profile_id: UUID, payload: HistoryIsolationRequest) -> HistoryIsolationResponse:
    get_profile(profile_id)
    return apply_history_pollution_isolation(profile_id, payload)
