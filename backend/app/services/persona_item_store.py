from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.schemas.persona_item import PersonaItemCreate, PersonaItemSchema
from app.services.local_database import read_json_file, update_json_file

PERSONA_ITEM_STORE_FILE = "persona_items.json"
VISIBLE_PERSONA_ITEM_STATUSES = {"active", "candidate", "rejected_until_confirmed"}
TRASH_PERSONA_ITEM_STATUS = "deleted"
INVALID_PERSONA_ITEM_EXTRACTION_METHODS = {"local_fallback_after_model_failed"}


def _now() -> datetime:
    return datetime.now(UTC)


def _read_records() -> list[dict[str, Any]]:
    records = read_json_file(PERSONA_ITEM_STORE_FILE, [])
    if isinstance(records, list):
        return records
    return []


def _coerce_records(records: Any) -> list[dict[str, Any]]:
    return records if isinstance(records, list) else []


def _update_records(updater: Any) -> list[dict[str, Any]]:
    return update_json_file(PERSONA_ITEM_STORE_FILE, [], lambda records: updater(_coerce_records(records)))


def _item_from_record(record: dict[str, Any]) -> PersonaItemSchema:
    return PersonaItemSchema.model_validate(record)


def save_persona_item(payload: PersonaItemCreate) -> PersonaItemSchema:
    timestamp = _now()
    item = PersonaItemSchema(
        id=uuid4(),
        profile_id=payload.profile_id,
        source_id=payload.source_id,
        library_group=payload.library_group,
        library_key=payload.library_key,
        signal=payload.signal,
        evidence_quote=payload.evidence_quote,
        evidence_time_range=payload.evidence_time_range,
        confidence=payload.confidence,
        stability=payload.stability,
        subject_scope=payload.subject_scope,
        write_target=payload.write_target,
        risk=payload.risk,
        prompt_snippet=payload.prompt_snippet,
        extraction_method=payload.extraction_method,
        model_name=payload.model_name,
        status=payload.status,
        metadata=payload.metadata,
        created_at=timestamp,
        updated_at=timestamp,
    )
    _update_records(lambda records: [*records, item.model_dump(mode="json")])
    return item


def save_persona_items(payloads: list[PersonaItemCreate]) -> list[PersonaItemSchema]:
    if not payloads:
        return []
    timestamp = _now()
    items = [
        PersonaItemSchema(
            id=uuid4(),
            profile_id=payload.profile_id,
            source_id=payload.source_id,
            library_group=payload.library_group,
            library_key=payload.library_key,
            signal=payload.signal,
            evidence_quote=payload.evidence_quote,
            evidence_time_range=payload.evidence_time_range,
            confidence=payload.confidence,
            stability=payload.stability,
            subject_scope=payload.subject_scope,
            write_target=payload.write_target,
            risk=payload.risk,
            prompt_snippet=payload.prompt_snippet,
            extraction_method=payload.extraction_method,
            model_name=payload.model_name,
            status=payload.status,
            metadata=payload.metadata,
            created_at=timestamp,
            updated_at=timestamp,
        )
        for payload in payloads
    ]
    item_records = [item.model_dump(mode="json") for item in items]
    _update_records(lambda records: [*records, *item_records])
    return items


def hide_persona_items_for_source(source_id: UUID, *, reason: str = "reextract", before: datetime | None = None) -> int:
    timestamp = _now()
    changed = 0

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal changed
        for index, record in enumerate(records):
            if record.get("source_id") != str(source_id):
                continue
            if record.get("status") == "hidden":
                continue
            item = _item_from_record(record)
            if before is not None and item.created_at >= before:
                continue
            metadata = dict(item.metadata)
            metadata["hidden_reason"] = reason
            metadata["hidden_at"] = timestamp.isoformat()
            records[index] = item.model_copy(
                update={
                    "status": "hidden",
                    "metadata": metadata,
                    "updated_at": timestamp,
                }
            ).model_dump(mode="json")
            changed += 1
        return records

    _update_records(mutate)
    return changed


def hide_persona_items_by_extraction_method(*, extraction_method: str, reason: str) -> int:
    timestamp = _now()
    changed = 0

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal changed
        for index, record in enumerate(records):
            if record.get("status") == "hidden":
                continue
            if record.get("extraction_method") != extraction_method:
                continue
            item = _item_from_record(record)
            metadata = dict(item.metadata)
            metadata["hidden_reason"] = reason
            metadata["hidden_at"] = timestamp.isoformat()
            records[index] = item.model_copy(
                update={
                    "status": "hidden",
                    "metadata": metadata,
                    "updated_at": timestamp,
                }
            ).model_dump(mode="json")
            changed += 1
        return records

    _update_records(mutate)
    return changed


def hide_persona_items_by_library_key(*, library_key: str, reason: str) -> int:
    timestamp = _now()
    changed = 0

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal changed
        for index, record in enumerate(records):
            if record.get("status") == "hidden":
                continue
            if record.get("library_key") != library_key:
                continue
            item = _item_from_record(record)
            metadata = dict(item.metadata)
            metadata["hidden_reason"] = reason
            metadata["hidden_at"] = timestamp.isoformat()
            records[index] = item.model_copy(
                update={
                    "status": "hidden",
                    "metadata": metadata,
                    "updated_at": timestamp,
                }
            ).model_dump(mode="json")
            changed += 1
        return records

    _update_records(mutate)
    return changed


def hide_persona_items_by_ids(
    item_ids: set[UUID],
    *,
    reason: str,
    extra_metadata_by_id: dict[UUID, dict[str, Any]] | None = None,
) -> int:
    if not item_ids:
        return 0
    target_ids = {str(item_id) for item_id in item_ids}
    timestamp = _now()
    changed = 0

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal changed
        for index, record in enumerate(records):
            if record.get("id") not in target_ids:
                continue
            if record.get("status") == "hidden":
                continue
            item = _item_from_record(record)
            metadata = dict(item.metadata)
            metadata["hidden_reason"] = reason
            metadata["hidden_at"] = timestamp.isoformat()
            if extra_metadata_by_id:
                metadata.update(extra_metadata_by_id.get(item.id, {}))
            records[index] = item.model_copy(
                update={
                    "status": "hidden",
                    "metadata": metadata,
                    "updated_at": timestamp,
                }
            ).model_dump(mode="json")
            changed += 1
        return records

    _update_records(mutate)
    return changed


def hide_persona_items_for_profile(profile_id: UUID, *, reason: str) -> int:
    timestamp = _now()
    changed = 0

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal changed
        for index, record in enumerate(records):
            if record.get("profile_id") != str(profile_id):
                continue
            if record.get("status") == "hidden":
                continue
            item = _item_from_record(record)
            metadata = dict(item.metadata)
            metadata["hidden_reason"] = reason
            metadata["hidden_at"] = timestamp.isoformat()
            metadata["archived_profile_id"] = str(profile_id)
            records[index] = item.model_copy(
                update={
                    "status": "hidden",
                    "metadata": metadata,
                    "updated_at": timestamp,
                }
            ).model_dump(mode="json")
            changed += 1
        return records

    _update_records(mutate)
    return changed


def list_persona_items(profile_id: UUID | None = None, *, include_hidden: bool = False) -> list[PersonaItemSchema]:
    items: list[PersonaItemSchema] = []
    for record in _read_records():
        if profile_id is not None and record.get("profile_id") != str(profile_id):
            continue
        item = _item_from_record(record)
        if not include_hidden and item.status not in VISIBLE_PERSONA_ITEM_STATUSES:
            continue
        if not include_hidden and item.extraction_method in INVALID_PERSONA_ITEM_EXTRACTION_METHODS:
            continue
        items.append(item)
    return sorted(items, key=lambda item: item.created_at, reverse=True)


def count_persona_items(profile_id: UUID) -> int:
    return sum(1 for item in list_persona_items(profile_id))


def list_deleted_persona_items(profile_id: UUID | None = None) -> list[PersonaItemSchema]:
    items: list[PersonaItemSchema] = []
    for record in _read_records():
        if profile_id is not None and record.get("profile_id") != str(profile_id):
            continue
        item = _item_from_record(record)
        if item.status == TRASH_PERSONA_ITEM_STATUS:
            items.append(item)
    return sorted(items, key=lambda item: item.updated_at, reverse=True)


def move_persona_item_to_trash(item_id: UUID) -> PersonaItemSchema:
    timestamp = _now()
    updated: PersonaItemSchema | None = None

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal updated
        for index, record in enumerate(records):
            if record.get("id") != str(item_id):
                continue
            item = _item_from_record(record)
            if item.status == TRASH_PERSONA_ITEM_STATUS:
                updated = item
                break
            metadata = dict(item.metadata)
            metadata["deleted_at"] = timestamp.isoformat()
            metadata["previous_status"] = item.status
            updated = item.model_copy(
                update={
                    "status": TRASH_PERSONA_ITEM_STATUS,
                    "metadata": metadata,
                    "updated_at": timestamp,
                }
            )
            records[index] = updated.model_dump(mode="json")
            break
        return records

    _update_records(mutate)
    if updated is not None:
        return updated
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona item not found")


def restore_persona_item(item_id: UUID) -> PersonaItemSchema:
    timestamp = _now()
    updated: PersonaItemSchema | None = None

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal updated
        for index, record in enumerate(records):
            if record.get("id") != str(item_id):
                continue
            item = _item_from_record(record)
            if item.status != TRASH_PERSONA_ITEM_STATUS:
                updated = item
                break
            metadata = dict(item.metadata)
            previous_status = metadata.pop("previous_status", "candidate")
            metadata.pop("deleted_at", None)
            if previous_status not in VISIBLE_PERSONA_ITEM_STATUSES and previous_status not in {"hidden", "forgotten"}:
                previous_status = "candidate"
            updated = item.model_copy(
                update={
                    "status": previous_status,
                    "metadata": metadata,
                    "updated_at": timestamp,
                }
            )
            records[index] = updated.model_dump(mode="json")
            break
        return records

    _update_records(mutate)
    if updated is not None:
        return updated
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona item not found")


def purge_persona_item(item_id: UUID) -> PersonaItemSchema:
    deleted: PersonaItemSchema | None = None

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal deleted
        kept_records: list[dict[str, Any]] = []
        for record in records:
            if record.get("id") == str(item_id):
                deleted = _item_from_record(record)
                continue
            kept_records.append(record)
        return kept_records

    _update_records(mutate)
    if deleted is not None:
        return deleted
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona item not found")
