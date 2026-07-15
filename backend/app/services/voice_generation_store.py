from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.config import get_settings
from app.schemas.voice_generation import VoiceGenerationRecord
from app.services.local_database import read_json_file, update_json_file

VOICE_GENERATION_STORE_FILE = "voice_generation_records.json"


def _now() -> datetime:
    return datetime.now(UTC)


def _read_records() -> list[dict[str, Any]]:
    records = read_json_file(VOICE_GENERATION_STORE_FILE, [])
    if isinstance(records, list):
        return records
    return []


def _coerce_records(records: Any) -> list[dict[str, Any]]:
    return records if isinstance(records, list) else []


def _update_records(updater: Any) -> list[dict[str, Any]]:
    return update_json_file(VOICE_GENERATION_STORE_FILE, [], lambda records: updater(_coerce_records(records)))


def _record_from_json(record: dict[str, Any]) -> VoiceGenerationRecord:
    return VoiceGenerationRecord.model_validate(record)


def save_voice_generation_record(record: VoiceGenerationRecord) -> VoiceGenerationRecord:
    _update_records(lambda records: [*records, record.model_dump(mode="json")])
    return record


def new_voice_generation_record(
    *,
    profile_id: UUID,
    reference_raw_source_id: UUID,
    chat_record_id: UUID | None,
    reply_text: str,
    model: str,
    provider: str,
    status: str,
    consent_confirmed: bool,
    output_file_path: str | None = None,
    output_mime_type: str | None = None,
    duration_seconds: float | None = None,
    error: str = "",
    metadata: dict[str, str | int | float | bool | None] | None = None,
) -> VoiceGenerationRecord:
    return VoiceGenerationRecord(
        profile_id=profile_id,
        reference_raw_source_id=reference_raw_source_id,
        chat_record_id=chat_record_id,
        reply_text=reply_text,
        model=model,
        provider=provider,
        status=status,  # type: ignore[arg-type]
        consent_confirmed=consent_confirmed,
        output_file_path=output_file_path,
        output_mime_type=output_mime_type,
        duration_seconds=duration_seconds,
        error=error,
        metadata=metadata or {},
        created_at=_now(),
    )


def list_voice_generation_records(profile_id: UUID, limit: int = 50) -> list[VoiceGenerationRecord]:
    records = [
        _record_from_json(record)
        for record in _read_records()
        if record.get("profile_id") == str(profile_id)
    ]
    return sorted(records, key=lambda record: record.created_at, reverse=True)[:limit]


def _configured_path(value: str) -> Path:
    configured = Path(value)
    if configured.is_absolute():
        return configured
    return Path(__file__).resolve().parents[2] / configured


def _delete_generated_output(record: VoiceGenerationRecord) -> None:
    if not record.output_file_path:
        return
    output_root = _configured_path(get_settings().voice_output_dir).resolve()
    output_path = Path(record.output_file_path).resolve()
    if not output_path.is_relative_to(output_root):
        return
    with suppress(OSError):
        if output_path.is_file():
            output_path.unlink()
    with suppress(OSError):
        parent = output_path.parent
        if parent != output_root and parent.is_relative_to(output_root) and not any(parent.iterdir()):
            parent.rmdir()


def delete_voice_generation_records(profile_id: UUID) -> int:
    deleted: list[VoiceGenerationRecord] = []

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        kept: list[dict[str, Any]] = []
        for record in records:
            if record.get("profile_id") == str(profile_id):
                deleted.append(_record_from_json(record))
                continue
            kept.append(record)
        return kept

    _update_records(mutate)
    for record in deleted:
        _delete_generated_output(record)
    return len(deleted)
