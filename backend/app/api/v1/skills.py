from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.schemas.skill_generation import SkillGenerationResponse
from app.schemas.skill_version import SkillVersionCreateRequest, SkillVersionListResponse, SkillVersionSchema
from app.services.profile_store import get_profile
from app.services.skill_version_store import delete_skill_version, get_skill_version, list_skill_versions, save_skill_version
from app.workflows.skill_generation_workflow import generate_skill_for_profile

router = APIRouter(prefix="/skills", tags=["skills"])


@router.post("/generate", response_model=SkillGenerationResponse)
def generate_skill(
    profile_id: UUID = Query(...),
    include_audit_units: bool = Query(default=False),
) -> SkillGenerationResponse:
    return generate_skill_for_profile(profile_id, include_audit_units=include_audit_units)


@router.get("/profiles/{profile_id}/versions", response_model=SkillVersionListResponse)
def read_profile_skill_versions(profile_id: UUID) -> SkillVersionListResponse:
    get_profile(profile_id)
    return SkillVersionListResponse(versions=list_skill_versions(profile_id))


@router.post("/profiles/{profile_id}/versions", response_model=SkillVersionSchema)
def create_profile_skill_version(profile_id: UUID, payload: SkillVersionCreateRequest) -> SkillVersionSchema:
    get_profile(profile_id)
    return save_skill_version(profile_id, payload)


@router.get("/profiles/{profile_id}/versions/{version_id}", response_model=SkillVersionSchema)
def read_skill_version(profile_id: UUID, version_id: UUID) -> SkillVersionSchema:
    get_profile(profile_id)
    return get_skill_version(profile_id, version_id)


@router.delete("/profiles/{profile_id}/versions/{version_id}", response_model=SkillVersionSchema)
def delete_profile_skill_version(profile_id: UUID, version_id: UUID) -> SkillVersionSchema:
    get_profile(profile_id)
    return delete_skill_version(profile_id, version_id)
