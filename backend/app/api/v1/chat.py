from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.schemas.chat import ChatClearResponse, ChatRecord, ChatRequest, ChatResponse
from app.services.chat_store import clear_chat_records, list_chat_records
from app.services.persona_chat import chat_with_profile
from app.services.profile_store import get_profile

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/profiles/{profile_id}/messages", response_model=list[ChatRecord])
def read_profile_chat_messages(profile_id: UUID) -> list[ChatRecord]:
    get_profile(profile_id)
    return list_chat_records(profile_id)


@router.delete("/profiles/{profile_id}/messages", response_model=ChatClearResponse)
def clear_profile_chat_messages(profile_id: UUID) -> ChatClearResponse:
    get_profile(profile_id)
    return ChatClearResponse(profile_id=profile_id, deleted_count=clear_chat_records(profile_id))


@router.post("/profiles/{profile_id}", response_model=ChatResponse)
def create_profile_chat_message(profile_id: UUID, payload: ChatRequest) -> ChatResponse:
    return chat_with_profile(profile_id, payload)
