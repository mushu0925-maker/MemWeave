from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.schemas.profile import (
    ProfileCreateRequest,
    ProfileDetailResponse,
    ProfileSchema,
    ProfileUpdateRequest,
)
from app.schemas.profile_status import ProfileStatusResponse
from app.services.persona_item_store import count_persona_items
from app.services.profile_status_service import build_profile_status
from app.services.profile_store import create_profile, delete_profile, get_profile, list_profiles, update_profile
from app.services.raw_source_store import count_raw_sources
from app.services.uncertainty_store import count_question_targets, count_uncertain_items

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.post("", response_model=ProfileSchema)
def create_memory_profile(payload: ProfileCreateRequest) -> ProfileSchema:
    return create_profile(payload)


@router.get("", response_model=list[ProfileSchema])
def read_memory_profiles() -> list[ProfileSchema]:
    return list_profiles()


@router.get("/{profile_id}", response_model=ProfileDetailResponse)
def read_memory_profile(profile_id: UUID) -> ProfileDetailResponse:
    profile = get_profile(profile_id)
    return ProfileDetailResponse(
        profile=profile,
        raw_source_count=count_raw_sources(profile_id),
        persona_item_count=count_persona_items(profile_id),
        uncertain_item_count=count_uncertain_items(profile_id),
        question_target_count=count_question_targets(profile_id),
    )


@router.get("/{profile_id}/status", response_model=ProfileStatusResponse)
def read_memory_profile_status(profile_id: UUID) -> ProfileStatusResponse:
    get_profile(profile_id)
    return build_profile_status(profile_id)


@router.patch("/{profile_id}", response_model=ProfileSchema)
def update_memory_profile(profile_id: UUID, payload: ProfileUpdateRequest) -> ProfileSchema:
    return update_profile(profile_id, payload)


@router.delete("/{profile_id}", response_model=ProfileSchema)
def delete_memory_profile(profile_id: UUID) -> ProfileSchema:
    return delete_profile(profile_id)
