from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.schemas.skill_version import SkillVersionCreateRequest, SkillVersionSchema
from app.services.local_database import read_json_file, update_json_file

SKILL_VERSION_STORE_FILE = "skill_versions.json"


def _now() -> datetime:
    return datetime.now(UTC)


def _read_records() -> list[dict[str, Any]]:
    records = read_json_file(SKILL_VERSION_STORE_FILE, [])
    if isinstance(records, list):
        return records
    return []


def _coerce_records(records: Any) -> list[dict[str, Any]]:
    return records if isinstance(records, list) else []


def _update_records(updater: Any) -> list[dict[str, Any]]:
    return update_json_file(SKILL_VERSION_STORE_FILE, [], lambda records: updater(_coerce_records(records)))


def _version_from_record(record: dict[str, Any]) -> SkillVersionSchema:
    return SkillVersionSchema.model_validate(record)


def save_skill_version(profile_id: UUID, payload: SkillVersionCreateRequest) -> SkillVersionSchema:
    skill = payload.skill
    if skill.profile_id != profile_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Skill profile_id does not match target profile",
        )

    timestamp = _now()
    title = (payload.title or "").strip() or f"Skill {timestamp.strftime('%Y-%m-%d %H:%M')}"
    version = SkillVersionSchema(
        profile_id=profile_id,
        title=title,
        notes=(payload.notes or "").strip(),
        source_generation_version=skill.version,
        skill_markdown=skill.skill_markdown,
        skill_json=skill,
        evidence_unit_count=len(skill.evidence_units),
        audit_count=len(skill.audit_report),
        question_backlog_count=len(skill.question_backlog),
        created_at=timestamp,
    )
    _update_records(lambda records: [*records, version.model_dump(mode="json")])
    return version


def list_skill_versions(profile_id: UUID, limit: int = 20) -> list[SkillVersionSchema]:
    versions = [
        _version_from_record(record)
        for record in _read_records()
        if record.get("profile_id") == str(profile_id)
    ]
    return sorted(versions, key=lambda version: version.created_at, reverse=True)[:limit]


def list_all_skill_versions() -> list[SkillVersionSchema]:
    versions = [_version_from_record(record) for record in _read_records()]
    return sorted(versions, key=lambda version: version.created_at, reverse=True)


def get_latest_skill_version(profile_id: UUID) -> SkillVersionSchema | None:
    versions = list_skill_versions(profile_id, limit=1)
    return versions[0] if versions else None


def get_skill_version(profile_id: UUID, version_id: UUID) -> SkillVersionSchema:
    for record in _read_records():
        if record.get("id") == str(version_id) and record.get("profile_id") == str(profile_id):
            return _version_from_record(record)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill version not found")


def delete_skill_version(profile_id: UUID, version_id: UUID) -> SkillVersionSchema:
    deleted: SkillVersionSchema | None = None

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal deleted
        kept_records: list[dict[str, Any]] = []
        for record in records:
            if record.get("id") == str(version_id) and record.get("profile_id") == str(profile_id):
                deleted = _version_from_record(record)
                continue
            kept_records.append(record)
        return kept_records

    _update_records(mutate)
    if deleted is not None:
        return deleted
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill version not found")


def delete_skill_versions(profile_id: UUID) -> int:
    removed = 0

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal removed
        kept_records = [record for record in records if record.get("profile_id") != str(profile_id)]
        removed = len(records) - len(kept_records)
        return kept_records

    _update_records(mutate)
    return removed


def delete_skill_versions_by_ids(version_ids: set[UUID]) -> int:
    if not version_ids:
        return 0
    target_ids = {str(version_id) for version_id in version_ids}
    removed = 0

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal removed
        kept_records = [record for record in records if record.get("id") not in target_ids]
        removed = len(records) - len(kept_records)
        return kept_records

    _update_records(mutate)
    return removed


def count_skill_versions(profile_id: UUID) -> int:
    return sum(1 for record in _read_records() if record.get("profile_id") == str(profile_id))
