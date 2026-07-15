from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.schemas.chat import ChatRecord
from app.services.local_database import read_json_file, update_json_file

CHAT_STORE_FILE = "chat_records.json"


def _now() -> datetime:
    return datetime.now(UTC)


def _read_records() -> list[dict[str, Any]]:
    records = read_json_file(CHAT_STORE_FILE, [])
    if isinstance(records, list):
        return records
    return []


def _coerce_records(records: Any) -> list[dict[str, Any]]:
    return records if isinstance(records, list) else []


def _update_records(updater: Any) -> list[dict[str, Any]]:
    return update_json_file(CHAT_STORE_FILE, [], lambda records: updater(_coerce_records(records)))


def _record_from_json(record: dict[str, Any]) -> ChatRecord:
    return ChatRecord.model_validate(record)


def save_chat_record(record: ChatRecord) -> ChatRecord:
    _update_records(lambda records: [*records, record.model_dump(mode="json")])
    return record


def list_chat_records(profile_id: UUID, limit: int = 50) -> list[ChatRecord]:
    records = [
        _record_from_json(record)
        for record in _read_records()
        if record.get("profile_id") == str(profile_id)
    ]
    return sorted(records, key=lambda record: record.created_at, reverse=True)[:limit]


def list_all_chat_records() -> list[ChatRecord]:
    records = [_record_from_json(record) for record in _read_records()]
    return sorted(records, key=lambda record: record.created_at, reverse=True)


def delete_chat_records_by_ids(record_ids: set[UUID]) -> int:
    if not record_ids:
        return 0
    target_ids = {str(record_id) for record_id in record_ids}
    removed = 0

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal removed
        kept_records = [record for record in records if record.get("id") not in target_ids]
        removed = len(records) - len(kept_records)
        return kept_records

    _update_records(mutate)
    return removed


def clear_chat_records(profile_id: UUID) -> int:
    removed = 0

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal removed
        kept_records = [record for record in records if record.get("profile_id") != str(profile_id)]
        removed = len(records) - len(kept_records)
        return kept_records

    _update_records(mutate)
    return removed


def new_chat_record(
    *,
    profile_id: UUID,
    chat_mode: str,
    user_message: str,
    assistant_message: str,
    model_call_status: str,
    model_call_reason: str,
    provider: str,
    model_name: str | None,
    used_persona_item_ids: list[UUID],
    used_raw_source_ids: list[UUID],
) -> ChatRecord:
    return ChatRecord(
        profile_id=profile_id,
        chat_mode=chat_mode,  # type: ignore[arg-type]
        user_message=user_message,
        assistant_message=assistant_message,
        model_call_status=model_call_status,  # type: ignore[arg-type]
        model_call_reason=model_call_reason,
        provider=provider,
        model_name=model_name,
        used_persona_item_ids=used_persona_item_ids,
        used_raw_source_ids=used_raw_source_ids,
        created_at=_now(),
    )
