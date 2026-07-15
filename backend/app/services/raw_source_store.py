from __future__ import annotations

import hashlib
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.schemas.raw_source import RawSourceCreate, RawSourceSchema
from app.services.local_database import data_dir, read_json_file, update_json_file
from app.services.persona_item_store import hide_persona_items_for_source
from app.services.source_segment_store import (
    delete_segments_for_raw_source,
    ensure_source_segments_for_raw_source,
    refresh_default_source_segments_for_raw_source,
)

RAW_SOURCE_STORE_FILE = "raw_sources.json"


def _now() -> datetime:
    return datetime.now(UTC)


def _read_records() -> list[dict[str, Any]]:
    records = read_json_file(RAW_SOURCE_STORE_FILE, [])
    if isinstance(records, list):
        return records
    return []


def _coerce_records(records: Any) -> list[dict[str, Any]]:
    return records if isinstance(records, list) else []


def _update_records(updater: Any) -> list[dict[str, Any]]:
    return update_json_file(RAW_SOURCE_STORE_FILE, [], lambda records: updater(_coerce_records(records)))


def _source_from_record(record: dict[str, Any]) -> RawSourceSchema:
    return RawSourceSchema.model_validate(record)


def _source_hash(payload: RawSourceCreate) -> str:
    digest = hashlib.sha256()
    digest.update(payload.source_type.encode("utf-8"))
    digest.update(b"\0")
    digest.update(payload.original_text.encode("utf-8"))
    digest.update(b"\0")
    digest.update(payload.extracted_text.encode("utf-8"))
    return digest.hexdigest()


def save_raw_source(payload: RawSourceCreate) -> RawSourceSchema:
    raw_source = RawSourceSchema(
        id=uuid4(),
        profile_id=payload.profile_id,
        source_type=payload.source_type,
        original_text=payload.original_text,
        extracted_text=payload.extracted_text,
        file_path=payload.file_path,
        file_name=payload.file_name,
        mime_type=payload.mime_type,
        content_hash=_source_hash(payload),
        pii_masked_text=payload.pii_masked_text,
        metadata=payload.metadata,
        created_at=_now(),
        deleted_at=None,
    )
    _update_records(lambda records: [*records, raw_source.model_dump(mode="json")])
    ensure_source_segments_for_raw_source(raw_source)
    return raw_source


def list_raw_sources(
    profile_id: UUID | None = None,
    *,
    include_deleted: bool = False,
    deleted_only: bool = False,
) -> list[RawSourceSchema]:
    sources: list[RawSourceSchema] = []
    for record in _read_records():
        if profile_id is not None and record.get("profile_id") != str(profile_id):
            continue
        source = _source_from_record(record)
        is_deleted = source.deleted_at is not None
        if deleted_only and not is_deleted:
            continue
        if not include_deleted and not deleted_only and is_deleted:
            continue
        sources.append(source)
    return sorted(sources, key=lambda source: source.created_at, reverse=True)


def get_raw_source(source_id: UUID) -> RawSourceSchema:
    for record in _read_records():
        if record.get("id") == str(source_id):
            return _source_from_record(record)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Raw source not found")


def update_raw_source_metadata(source_id: UUID, metadata: dict[str, Any]) -> RawSourceSchema:
    updated: RawSourceSchema | None = None

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal updated
        for index, record in enumerate(records):
            if record.get("id") != str(source_id):
                continue
            source = _source_from_record(record)
            updated = source.model_copy(update={"metadata": metadata})
            records[index] = updated.model_dump(mode="json")
            break
        return records

    _update_records(mutate)
    if updated is not None:
        return updated
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Raw source not found")


def update_raw_source_content(
    source_id: UUID,
    *,
    original_text: str,
    extracted_text: str,
    pii_masked_text: str,
    metadata: dict[str, Any],
    file_path: str | None = None,
    file_name: str | None = None,
    mime_type: str | None = None,
) -> RawSourceSchema:
    updated: RawSourceSchema | None = None

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal updated
        for index, record in enumerate(records):
            if record.get("id") != str(source_id):
                continue
            source = _source_from_record(record)
            payload = RawSourceCreate(
                profile_id=source.profile_id,
                source_type=source.source_type,
                original_text=original_text,
                extracted_text=extracted_text,
                file_path=file_path if file_path is not None else source.file_path,
                file_name=file_name if file_name is not None else source.file_name,
                mime_type=mime_type if mime_type is not None else source.mime_type,
                pii_masked_text=pii_masked_text,
                metadata=metadata,
            )
            updated = source.model_copy(
                update={
                    "original_text": payload.original_text,
                    "extracted_text": payload.extracted_text,
                    "file_path": payload.file_path,
                    "file_name": payload.file_name,
                    "mime_type": payload.mime_type,
                    "content_hash": _source_hash(payload),
                    "pii_masked_text": payload.pii_masked_text,
                    "metadata": payload.metadata,
                }
            )
            records[index] = updated.model_dump(mode="json")
            break
        return records

    _update_records(mutate)
    if updated is not None:
        refresh_default_source_segments_for_raw_source(updated)
        return updated
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Raw source not found")


def count_raw_sources(profile_id: UUID) -> int:
    return sum(
        1
        for record in _read_records()
        if record.get("profile_id") == str(profile_id) and record.get("deleted_at") is None
    )


def move_raw_source_to_trash(source_id: UUID) -> RawSourceSchema:
    timestamp = _now()
    updated: RawSourceSchema | None = None

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal updated
        for index, record in enumerate(records):
            if record.get("id") != str(source_id):
                continue
            source = _source_from_record(record)
            updated = source if source.deleted_at is not None else source.model_copy(update={"deleted_at": timestamp})
            records[index] = updated.model_dump(mode="json")
            break
        return records

    _update_records(mutate)
    if updated is not None:
        return updated
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Raw source not found")


def restore_raw_source(source_id: UUID) -> RawSourceSchema:
    updated: RawSourceSchema | None = None

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal updated
        for index, record in enumerate(records):
            if record.get("id") != str(source_id):
                continue
            source = _source_from_record(record)
            updated = source if source.deleted_at is None else source.model_copy(update={"deleted_at": None})
            records[index] = updated.model_dump(mode="json")
            break
        return records

    _update_records(mutate)
    if updated is not None:
        return updated
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Raw source not found")


def detach_raw_sources_from_profile(profile_id: UUID, *, reason: str) -> int:
    timestamp = _now().isoformat()
    changed = 0

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal changed
        for index, record in enumerate(records):
            if record.get("profile_id") != str(profile_id):
                continue
            source = _source_from_record(record)
            metadata = dict(source.metadata)
            metadata["detached_from_profile_id"] = str(profile_id)
            metadata["detached_reason"] = reason
            metadata["detached_at"] = timestamp
            if metadata.get("voice_reference"):
                metadata["voice_reference_status"] = "revoked"
                metadata["voice_reference_consent_confirmed"] = False
                metadata["voice_reference_revoked_at"] = timestamp
                metadata["voice_reference_revoked_reason"] = reason
            records[index] = source.model_copy(update={"profile_id": None, "metadata": metadata}).model_dump(mode="json")
            changed += 1
        return records

    _update_records(mutate)
    return changed


def _delete_stored_file_for_purge(source: RawSourceSchema) -> None:
    if not source.file_path:
        return
    try:
        file_path = Path(source.file_path).resolve()
        root = data_dir().resolve()
        if not file_path.is_relative_to(root):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Refusing to purge file outside local data directory",
            )
        if file_path.is_file():
            file_path.unlink()
    except HTTPException:
        raise
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Stored file could not be deleted: {exc}",
        ) from exc
    with suppress(OSError):
        parent = file_path.parent
        root = data_dir().resolve()
        if parent != root and parent.is_relative_to(root) and not any(parent.iterdir()):
            parent.rmdir()


def purge_raw_source(source_id: UUID) -> RawSourceSchema:
    deleted: RawSourceSchema | None = None

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal deleted
        kept_records: list[dict[str, Any]] = []
        for record in records:
            if record.get("id") == str(source_id):
                deleted = _source_from_record(record)
                continue
            kept_records.append(record)
        return kept_records

    _update_records(mutate)
    if deleted is not None:
        delete_segments_for_raw_source(source_id)
        hide_persona_items_for_source(source_id, reason="raw_source_purged")
        _delete_stored_file_for_purge(deleted)
        return deleted
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Raw source not found")
