from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.schemas.memory_completion import MemoryCompletionRequest, MemoryCompletionResponse
from app.services.memory_completion_service import complete_event_memory

router = APIRouter(prefix="/memory-completion", tags=["memory_completion"])


@router.post("/event", response_model=MemoryCompletionResponse)
def complete_event_memory_endpoint(payload: MemoryCompletionRequest) -> MemoryCompletionResponse:
    try:
        return complete_event_memory(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
