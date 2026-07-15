from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status as http_status

from app.schemas.clarification import (
    QuestionTargetCreate,
    QuestionTargetSchema,
    QuestionTargetStatus,
    UncertainItemCreate,
    UncertainItemSchema,
    UncertainItemStatus,
)
from app.services.local_database import read_json_file, update_json_file

UNCERTAIN_ITEM_STORE_FILE = "uncertain_items.json"
QUESTION_TARGET_STORE_FILE = "question_targets.json"
OPEN_UNCERTAIN_STATUSES = {"open"}
OPEN_QUESTION_STATUSES = {"open"}


def _now() -> datetime:
    return datetime.now(UTC)


def _read_uncertain_records() -> list[dict[str, Any]]:
    records = read_json_file(UNCERTAIN_ITEM_STORE_FILE, [])
    if isinstance(records, list):
        return records
    return []


def _read_question_records() -> list[dict[str, Any]]:
    records = read_json_file(QUESTION_TARGET_STORE_FILE, [])
    if isinstance(records, list):
        return records
    return []


def _coerce_records(records: Any) -> list[dict[str, Any]]:
    return records if isinstance(records, list) else []


def _update_uncertain_records(updater: Any) -> list[dict[str, Any]]:
    return update_json_file(UNCERTAIN_ITEM_STORE_FILE, [], lambda records: updater(_coerce_records(records)))


def _update_question_records(updater: Any) -> list[dict[str, Any]]:
    return update_json_file(QUESTION_TARGET_STORE_FILE, [], lambda records: updater(_coerce_records(records)))


def _uncertain_from_record(record: dict[str, Any]) -> UncertainItemSchema:
    return UncertainItemSchema.model_validate(record)


def _question_from_record(record: dict[str, Any]) -> QuestionTargetSchema:
    return QuestionTargetSchema.model_validate(record)


def _source_key(value: UUID | None) -> str:
    return str(value) if value is not None else ""


def _uncertain_dedupe_key(payload: UncertainItemCreate) -> tuple[str, str, str, str, str]:
    return (
        str(payload.profile_id),
        _source_key(payload.source_id),
        payload.library_group,
        payload.library_key,
        payload.claim.strip(),
    )


def _question_dedupe_key(payload: QuestionTargetCreate) -> tuple[str, str, str, str, str]:
    return (
        str(payload.profile_id),
        _source_key(payload.source_id),
        payload.target_group,
        payload.target_library_key,
        payload.question.strip(),
    )


def save_uncertain_item(payload: UncertainItemCreate) -> UncertainItemSchema:
    """保存不确定项；同一 source/库/claim 重复进入时复用已有记录。"""

    target_key = _uncertain_dedupe_key(payload)
    timestamp = _now()
    item: UncertainItemSchema | None = None

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal item
        for record in records:
            existing = _uncertain_from_record(record)
            existing_key = (
                str(existing.profile_id),
                _source_key(existing.source_id),
                existing.library_group,
                existing.library_key,
                existing.claim.strip(),
            )
            if existing_key == target_key:
                item = existing
                return records
        item = UncertainItemSchema(
            id=uuid4(),
            profile_id=payload.profile_id,
            source_id=payload.source_id,
            persona_item_id=payload.persona_item_id,
            library_group=payload.library_group,
            library_key=payload.library_key,
            claim=payload.claim,
            why_uncertain=payload.why_uncertain,
            risk_type=payload.risk_type,
            suggested_question=payload.suggested_question,
            confirmation_options=payload.confirmation_options,
            confidence=payload.confidence,
            status=payload.status,
            metadata=payload.metadata,
            created_at=timestamp,
            updated_at=timestamp,
        )
        records.append(item.model_dump(mode="json"))
        return records

    _update_uncertain_records(mutate)
    if item is None:
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Uncertain item save failed")
    return item


def save_question_target(payload: QuestionTargetCreate) -> QuestionTargetSchema:
    """保存待追问目标；同一 source/库/question 重复进入时复用已有记录。"""

    target_key = _question_dedupe_key(payload)
    timestamp = _now()
    item: QuestionTargetSchema | None = None

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal item
        for record in records:
            existing = _question_from_record(record)
            existing_key = (
                str(existing.profile_id),
                _source_key(existing.source_id),
                existing.target_group,
                existing.target_library_key,
                existing.question.strip(),
            )
            if existing_key == target_key:
                item = existing
                return records
        item = QuestionTargetSchema(
            id=uuid4(),
            profile_id=payload.profile_id,
            source_id=payload.source_id,
            uncertain_item_id=payload.uncertain_item_id,
            target_group=payload.target_group,
            target_library_key=payload.target_library_key,
            reason=payload.reason,
            question=payload.question,
            example_answer=payload.example_answer,
            priority=payload.priority,
            expected_evidence_type=payload.expected_evidence_type,
            status=payload.status,
            metadata=payload.metadata,
            created_at=timestamp,
            updated_at=timestamp,
        )
        records.append(item.model_dump(mode="json"))
        return records

    _update_question_records(mutate)
    if item is None:
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Question target save failed")
    return item


def list_uncertain_items(
    profile_id: UUID | None = None,
    *,
    include_closed: bool = False,
) -> list[UncertainItemSchema]:
    items: list[UncertainItemSchema] = []
    for record in _read_uncertain_records():
        if profile_id is not None and record.get("profile_id") != str(profile_id):
            continue
        item = _uncertain_from_record(record)
        if not include_closed and item.status not in OPEN_UNCERTAIN_STATUSES:
            continue
        items.append(item)
    return sorted(items, key=lambda item: item.created_at, reverse=True)


def list_question_targets(
    profile_id: UUID | None = None,
    *,
    include_closed: bool = False,
) -> list[QuestionTargetSchema]:
    items: list[QuestionTargetSchema] = []
    for record in _read_question_records():
        if profile_id is not None and record.get("profile_id") != str(profile_id):
            continue
        item = _question_from_record(record)
        if not include_closed and item.status not in OPEN_QUESTION_STATUSES:
            continue
        items.append(item)
    return sorted(items, key=lambda item: item.priority, reverse=True)


def count_uncertain_items(profile_id: UUID, *, include_closed: bool = False) -> int:
    return len(list_uncertain_items(profile_id, include_closed=include_closed))


def count_question_targets(profile_id: UUID, *, include_closed: bool = False) -> int:
    return len(list_question_targets(profile_id, include_closed=include_closed))


def list_question_targets_for_uncertain_item(
    uncertain_item_id: UUID,
    *,
    include_closed: bool = False,
) -> list[QuestionTargetSchema]:
    items: list[QuestionTargetSchema] = []
    for record in _read_question_records():
        if record.get("uncertain_item_id") != str(uncertain_item_id):
            continue
        item = _question_from_record(record)
        if not include_closed and item.status not in OPEN_QUESTION_STATUSES:
            continue
        items.append(item)
    return sorted(items, key=lambda item: item.priority, reverse=True)


def get_uncertain_item(item_id: UUID) -> UncertainItemSchema:
    for record in _read_uncertain_records():
        if record.get("id") == str(item_id):
            return _uncertain_from_record(record)
    raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Uncertain item not found")


def get_question_target(question_id: UUID) -> QuestionTargetSchema:
    for record in _read_question_records():
        if record.get("id") == str(question_id):
            return _question_from_record(record)
    raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Question target not found")


def update_uncertain_item(
    item_id: UUID,
    *,
    status: UncertainItemStatus | None = None,
    metadata_updates: dict[str, Any] | None = None,
) -> UncertainItemSchema:
    updated: UncertainItemSchema | None = None

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal updated
        for index, record in enumerate(records):
            if record.get("id") != str(item_id):
                continue
            item = _uncertain_from_record(record)
            metadata = {**item.metadata, **(metadata_updates or {})}
            updated = item.model_copy(
                update={
                    "status": status or item.status,
                    "metadata": metadata,
                    "updated_at": _now(),
                }
            )
            records[index] = updated.model_dump(mode="json")
            break
        return records

    _update_uncertain_records(mutate)
    if updated is not None:
        return updated
    raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Uncertain item not found")


def update_question_target(
    question_id: UUID,
    *,
    status: QuestionTargetStatus | None = None,
    metadata_updates: dict[str, Any] | None = None,
) -> QuestionTargetSchema:
    updated: QuestionTargetSchema | None = None

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal updated
        for index, record in enumerate(records):
            if record.get("id") != str(question_id):
                continue
            item = _question_from_record(record)
            metadata = {**item.metadata, **(metadata_updates or {})}
            updated = item.model_copy(
                update={
                    "status": status or item.status,
                    "metadata": metadata,
                    "updated_at": _now(),
                }
            )
            records[index] = updated.model_dump(mode="json")
            break
        return records

    _update_question_records(mutate)
    if updated is not None:
        return updated
    raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Question target not found")


def delete_uncertain_items(profile_id: UUID) -> int:
    removed = 0

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal removed
        kept_records = [record for record in records if record.get("profile_id") != str(profile_id)]
        removed = len(records) - len(kept_records)
        return kept_records

    _update_uncertain_records(mutate)
    return removed


def delete_uncertain_items_by_ids(item_ids: set[UUID]) -> int:
    if not item_ids:
        return 0
    target_ids = {str(item_id) for item_id in item_ids}
    removed = 0

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal removed
        kept_records = [record for record in records if record.get("id") not in target_ids]
        removed = len(records) - len(kept_records)
        return kept_records

    _update_uncertain_records(mutate)
    return removed


def delete_question_targets(profile_id: UUID) -> int:
    removed = 0

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal removed
        kept_records = [record for record in records if record.get("profile_id") != str(profile_id)]
        removed = len(records) - len(kept_records)
        return kept_records

    _update_question_records(mutate)
    return removed


def delete_question_targets_by_ids(question_ids: set[UUID]) -> int:
    if not question_ids:
        return 0
    target_ids = {str(question_id) for question_id in question_ids}
    removed = 0

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal removed
        kept_records = [record for record in records if record.get("id") not in target_ids]
        removed = len(records) - len(kept_records)
        return kept_records

    _update_question_records(mutate)
    return removed
