from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.schemas.profile import (
    ProfileCreateRequest,
    ProfileSchema,
    ProfileUpdateRequest,
)
from app.services.local_database import cleanup_temp_files, read_json_file, update_json_file
from app.services.chat_store import clear_chat_records
from app.services.persona_item_store import hide_persona_items_for_profile
from app.services.raw_source_store import detach_raw_sources_from_profile
from app.services.skill_version_store import delete_skill_versions
from app.services.uncertainty_store import delete_question_targets, delete_uncertain_items
from app.services.voice_generation_store import delete_voice_generation_records

PROFILE_STORE_FILE = "profiles.json"


def _now() -> datetime:
    return datetime.now(UTC)


def _read_profile_records() -> list[dict[str, Any]]:
    records = read_json_file(PROFILE_STORE_FILE, [])
    if isinstance(records, list):
        return records
    return []


def _coerce_records(records: Any) -> list[dict[str, Any]]:
    return records if isinstance(records, list) else []


def _update_profile_records(updater: Any) -> list[dict[str, Any]]:
    return update_json_file(PROFILE_STORE_FILE, [], lambda records: updater(_coerce_records(records)))


def _profile_from_record(record: dict[str, Any]) -> ProfileSchema:
    return ProfileSchema.model_validate(record)


def create_profile(payload: ProfileCreateRequest) -> ProfileSchema:
    timestamp = _now()
    profile = ProfileSchema(
        id=uuid4(),
        display_name=payload.display_name.strip(),
        relationship=payload.relationship,
        description=payload.description.strip(),
        boundaries=payload.boundaries,
        created_at=timestamp,
        updated_at=timestamp,
    )
    _update_profile_records(lambda records: [*records, profile.model_dump(mode="json")])
    return profile


def update_profile(profile_id: UUID, payload: ProfileUpdateRequest) -> ProfileSchema:
    updated: ProfileSchema | None = None

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal updated
        for index, record in enumerate(records):
            if record.get("id") != str(profile_id):
                continue
            existing = _profile_from_record(record)
            if existing.deleted_at is not None:
                break
            updated = existing.model_copy(
                update={
                    "display_name": payload.display_name.strip() if payload.display_name is not None else existing.display_name,
                    "relationship": payload.relationship if payload.relationship is not None else existing.relationship,
                    "description": payload.description.strip() if payload.description is not None else existing.description,
                    "boundaries": payload.boundaries if payload.boundaries is not None else existing.boundaries,
                    "updated_at": _now(),
                }
            )
            records[index] = updated.model_dump(mode="json")
            break
        return records

    _update_profile_records(mutate)
    if updated is not None:
        return updated
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")


def delete_profile(profile_id: UUID) -> ProfileSchema:
    deleted: ProfileSchema | None = None

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal deleted
        for index, record in enumerate(records):
            if record.get("id") != str(profile_id):
                continue
            deleted = _profile_from_record(record)
            if deleted.deleted_at is None:
                timestamp = _now()
                records[index] = deleted.model_copy(update={"deleted_at": timestamp, "updated_at": timestamp}).model_dump(mode="json")
            break
        return records

    _update_profile_records(mutate)
    if deleted is not None:
        detach_raw_sources_from_profile(profile_id, reason="profile_deleted")
        hide_persona_items_for_profile(profile_id, reason="profile_deleted")
        clear_chat_records(profile_id)
        delete_skill_versions(profile_id)
        delete_uncertain_items(profile_id)
        delete_question_targets(profile_id)
        delete_voice_generation_records(profile_id)
        cleanup_temp_files(
            "profiles.json",
            "raw_sources.json",
            "persona_items.json",
            "chat_records.json",
            "skill_versions.json",
            "uncertain_items.json",
            "question_targets.json",
            "voice_generation_records.json",
        )
        return deleted
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")


def touch_profile(profile_id: UUID) -> None:
    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for index, record in enumerate(records):
            if record.get("id") != str(profile_id):
                continue
            existing = _profile_from_record(record)
            if existing.deleted_at is not None:
                break
            records[index] = existing.model_copy(update={"updated_at": _now()}).model_dump(mode="json")
            break
        return records

    _update_profile_records(mutate)


def get_profile(profile_id: UUID) -> ProfileSchema:
    for record in _read_profile_records():
        if record.get("id") == str(profile_id):
            profile = _profile_from_record(record)
            if profile.deleted_at is None:
                return profile
            break
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")


def list_profiles(*, include_deleted: bool = False) -> list[ProfileSchema]:
    profiles = [
        profile
        for profile in (_profile_from_record(record) for record in _read_profile_records())
        if include_deleted or profile.deleted_at is None
    ]
    return sorted(profiles, key=lambda profile: profile.updated_at, reverse=True)
