from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.schemas.raw_source import RawSourceSchema
from app.schemas.source_segment import (
    ExtractedSegmentCreate,
    ExtractedSegmentSchema,
    SourceSegmentBackfillResponse,
    SourceSegmentCreate,
    SourceSegmentSchema,
    SourceSegmentUpdate,
)
from app.services.local_database import read_json_file, update_json_file

SOURCE_SEGMENT_STORE_FILE = "source_segments.json"
EXTRACTED_SEGMENT_STORE_FILE = "extracted_segments.json"
VOICE_GENERATION_USE = "voice_generation"
VOICE_REFERENCE_USE = "voice_reference"


def _now() -> datetime:
    return datetime.now(UTC)


def _read_source_segment_records() -> list[dict[str, Any]]:
    records = read_json_file(SOURCE_SEGMENT_STORE_FILE, [])
    return records if isinstance(records, list) else []


def _read_extracted_segment_records() -> list[dict[str, Any]]:
    records = read_json_file(EXTRACTED_SEGMENT_STORE_FILE, [])
    return records if isinstance(records, list) else []


def _coerce_list(records: Any) -> list[dict[str, Any]]:
    return records if isinstance(records, list) else []


def _update_source_segment_records(updater: Any) -> list[dict[str, Any]]:
    return update_json_file(SOURCE_SEGMENT_STORE_FILE, [], lambda records: updater(_coerce_list(records)))


def _update_extracted_segment_records(updater: Any) -> list[dict[str, Any]]:
    return update_json_file(EXTRACTED_SEGMENT_STORE_FILE, [], lambda records: updater(_coerce_list(records)))


def _source_segment_from_record(record: dict[str, Any]) -> SourceSegmentSchema:
    return SourceSegmentSchema.model_validate(record)


def _extracted_segment_from_record(record: dict[str, Any]) -> ExtractedSegmentSchema:
    return ExtractedSegmentSchema.model_validate(record)


def _clip(text: str, limit: int) -> str:
    compact = " ".join(text.strip().split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "..."


def _source_text(raw_source: RawSourceSchema) -> str:
    return raw_source.pii_masked_text or raw_source.extracted_text or raw_source.original_text or raw_source.file_name or ""


def _is_voice_reference(raw_source: RawSourceSchema) -> bool:
    return bool(raw_source.metadata.get("voice_reference"))


def _default_permitted_uses(raw_source: RawSourceSchema) -> list[str]:
    if _is_voice_reference(raw_source):
        return ["voice_reference_review"]
    return ["evidence_review"]


def _default_metadata(raw_source: RawSourceSchema) -> dict[str, Any]:
    purpose = "voice_reference" if _is_voice_reference(raw_source) else f"{raw_source.source_type}_material"
    return {
        "purpose": purpose,
        "created_by": "source_segment_store.ensure_default",
        "requires_user_attribution": True,
        "raw_source_file_name": raw_source.file_name,
        "raw_source_mime_type": raw_source.mime_type,
    }


def create_source_segment(payload: SourceSegmentCreate) -> SourceSegmentSchema:
    timestamp = _now()
    segment = SourceSegmentSchema(
        id=uuid4(),
        raw_source_id=payload.raw_source_id,
        profile_id=payload.profile_id,
        source_type=payload.source_type,
        segment_index=payload.segment_index,
        start_char=payload.start_char,
        end_char=payload.end_char,
        start_seconds=payload.start_seconds,
        end_seconds=payload.end_seconds,
        text_excerpt=payload.text_excerpt,
        target_person=payload.target_person,
        attribution_status=payload.attribution_status,
        consent_confirmed=payload.consent_confirmed,
        consent_note=payload.consent_note,
        permitted_uses=payload.permitted_uses,
        metadata=payload.metadata,
        created_at=timestamp,
        updated_at=timestamp,
    )
    _update_source_segment_records(lambda records: [*records, segment.model_dump(mode="json")])
    return segment


def create_extracted_segment(payload: ExtractedSegmentCreate) -> ExtractedSegmentSchema:
    segment = ExtractedSegmentSchema(
        id=uuid4(),
        source_segment_id=payload.source_segment_id,
        raw_source_id=payload.raw_source_id,
        profile_id=payload.profile_id,
        extraction_type=payload.extraction_type,
        extracted_text=payload.extracted_text,
        confidence=payload.confidence,
        model_name=payload.model_name,
        metadata=payload.metadata,
        created_at=_now(),
    )
    _update_extracted_segment_records(lambda records: [*records, segment.model_dump(mode="json")])
    return segment


def list_source_segments(
    *,
    profile_id: UUID | None = None,
    raw_source_id: UUID | None = None,
) -> list[SourceSegmentSchema]:
    segments: list[SourceSegmentSchema] = []
    for record in _read_source_segment_records():
        if profile_id is not None and record.get("profile_id") != str(profile_id):
            continue
        if raw_source_id is not None and record.get("raw_source_id") != str(raw_source_id):
            continue
        segments.append(_source_segment_from_record(record))
    return sorted(segments, key=lambda item: (str(item.raw_source_id), item.segment_index, item.created_at))


def list_extracted_segments(
    *,
    profile_id: UUID | None = None,
    raw_source_id: UUID | None = None,
    source_segment_id: UUID | None = None,
) -> list[ExtractedSegmentSchema]:
    segments: list[ExtractedSegmentSchema] = []
    for record in _read_extracted_segment_records():
        if profile_id is not None and record.get("profile_id") != str(profile_id):
            continue
        if raw_source_id is not None and record.get("raw_source_id") != str(raw_source_id):
            continue
        if source_segment_id is not None and record.get("source_segment_id") != str(source_segment_id):
            continue
        segments.append(_extracted_segment_from_record(record))
    return sorted(segments, key=lambda item: item.created_at)


def get_source_segment(segment_id: UUID) -> SourceSegmentSchema:
    for record in _read_source_segment_records():
        if record.get("id") == str(segment_id):
            return _source_segment_from_record(record)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source segment not found")


def update_source_segment(segment_id: UUID, payload: SourceSegmentUpdate) -> SourceSegmentSchema:
    updated: SourceSegmentSchema | None = None

    def mutate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal updated
        for index, record in enumerate(records):
            if record.get("id") != str(segment_id):
                continue
            segment = _source_segment_from_record(record)
            metadata = dict(segment.metadata)
            if payload.metadata is not None:
                metadata.update(payload.metadata)
            updates: dict[str, Any] = {"metadata": metadata, "updated_at": _now()}
            if payload.target_person is not None:
                updates["target_person"] = payload.target_person
            if payload.attribution_status is not None:
                updates["attribution_status"] = payload.attribution_status
            if payload.consent_confirmed is not None:
                updates["consent_confirmed"] = payload.consent_confirmed
            if payload.consent_note is not None:
                updates["consent_note"] = payload.consent_note
            if payload.permitted_uses is not None:
                updates["permitted_uses"] = payload.permitted_uses
            updated = segment.model_copy(update=updates)
            records[index] = updated.model_dump(mode="json")
            break
        return records

    _update_source_segment_records(mutate)
    if updated is not None:
        return updated
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source segment not found")


def ensure_source_segments_for_raw_source(raw_source: RawSourceSchema) -> list[SourceSegmentSchema]:
    existing = list_source_segments(raw_source_id=raw_source.id)
    if existing:
        if not list_extracted_segments(source_segment_id=existing[0].id):
            text = _source_text(raw_source)
            if text:
                create_extracted_segment(
                    ExtractedSegmentCreate(
                        source_segment_id=existing[0].id,
                        raw_source_id=raw_source.id,
                        profile_id=raw_source.profile_id,
                        extraction_type="source_text",
                        extracted_text=text,
                        confidence=0.5,
                        metadata={"created_by": "source_segment_store.ensure_missing_extracted"},
                    )
                )
        return existing

    text = _source_text(raw_source)
    segment = create_source_segment(
        SourceSegmentCreate(
            raw_source_id=raw_source.id,
            profile_id=raw_source.profile_id,
            source_type=raw_source.source_type,
            segment_index=0,
            start_char=0 if text else None,
            end_char=len(text) if text else None,
            text_excerpt=_clip(text, 4000),
            target_person="unknown",
            attribution_status="pending",
            consent_confirmed=bool(raw_source.metadata.get("voice_reference_consent_confirmed"))
            if _is_voice_reference(raw_source)
            else False,
            consent_note=str(raw_source.metadata.get("voice_reference_consent_note") or "")[:1000]
            if _is_voice_reference(raw_source)
            else "",
            permitted_uses=_default_permitted_uses(raw_source),
            metadata=_default_metadata(raw_source),
        )
    )
    if text:
        create_extracted_segment(
            ExtractedSegmentCreate(
                source_segment_id=segment.id,
                raw_source_id=raw_source.id,
                profile_id=raw_source.profile_id,
                extraction_type="source_text",
                extracted_text=text,
                confidence=0.5,
                metadata={"created_by": "source_segment_store.ensure_default"},
            )
        )
    return [segment]


def refresh_default_source_segments_for_raw_source(raw_source: RawSourceSchema) -> list[SourceSegmentSchema]:
    segments = ensure_source_segments_for_raw_source(raw_source)
    if not segments:
        return []
    segment = segments[0]
    text = _source_text(raw_source)
    updated_segment = segment

    def mutate_source(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal updated_segment
        for index, record in enumerate(records):
            if record.get("id") != str(segment.id):
                continue
            metadata = dict(segment.metadata)
            metadata.update(_default_metadata(raw_source))
            metadata["updated_by"] = "source_segment_store.refresh_default"
            updated_segment = segment.model_copy(
                update={
                    "profile_id": raw_source.profile_id,
                    "source_type": raw_source.source_type,
                    "start_char": 0 if text else None,
                    "end_char": len(text) if text else None,
                    "text_excerpt": _clip(text, 4000),
                    "metadata": metadata,
                    "updated_at": _now(),
                }
            )
            records[index] = updated_segment.model_dump(mode="json")
            break
        return records

    _update_source_segment_records(mutate_source)

    updated_extracted = False

    def mutate_extracted(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal updated_extracted
        for index, record in enumerate(records):
            if record.get("source_segment_id") != str(segment.id):
                continue
            extracted = _extracted_segment_from_record(record)
            records[index] = extracted.model_copy(
                update={
                    "profile_id": raw_source.profile_id,
                    "extracted_text": text,
                    "confidence": 0.5,
                    "metadata": {
                        **extracted.metadata,
                        "updated_by": "source_segment_store.refresh_default",
                    },
                }
            ).model_dump(mode="json")
            updated_extracted = True
            break
        return records

    _update_extracted_segment_records(mutate_extracted)
    if updated_extracted:
        return [updated_segment]

    if text:
        create_extracted_segment(
            ExtractedSegmentCreate(
                source_segment_id=segment.id,
                raw_source_id=raw_source.id,
                profile_id=raw_source.profile_id,
                extraction_type="source_text",
                extracted_text=text,
                confidence=0.5,
                metadata={"created_by": "source_segment_store.refresh_default"},
            )
        )
    return [updated_segment]


def source_has_confirmed_target_person_segment(raw_source_id: UUID) -> bool:
    return any(
        segment.target_person == "target_person" and segment.attribution_status == "confirmed"
        for segment in list_source_segments(raw_source_id=raw_source_id)
    )


def delete_segments_for_raw_source(raw_source_id: UUID) -> dict[str, int]:
    source_removed = 0
    extracted_removed = 0

    def remove_sources(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal source_removed
        kept = [record for record in records if record.get("raw_source_id") != str(raw_source_id)]
        source_removed = len(records) - len(kept)
        return kept

    def remove_extracted(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal extracted_removed
        kept = [record for record in records if record.get("raw_source_id") != str(raw_source_id)]
        extracted_removed = len(records) - len(kept)
        return kept

    _update_source_segment_records(remove_sources)
    _update_extracted_segment_records(remove_extracted)
    return {"source_segments_deleted": source_removed, "extracted_segments_deleted": extracted_removed}


def backfill_source_segments(
    raw_sources: list[RawSourceSchema],
    *,
    profile_id: UUID | None = None,
    include_deleted: bool = False,
) -> SourceSegmentBackfillResponse:
    active_raw_sources = raw_sources if include_deleted else [source for source in raw_sources if source.deleted_at is None]
    raw_source_ids = {source.id for source in active_raw_sources}

    segments_before = [segment for segment in list_source_segments() if segment.raw_source_id in raw_source_ids]
    extracted_before = [segment for segment in list_extracted_segments() if segment.raw_source_id in raw_source_ids]
    segmented_ids_before = {segment.raw_source_id for segment in segments_before}
    missing_sources_before = [source for source in active_raw_sources if source.id not in segmented_ids_before]

    backfilled_ids: list[UUID] = []
    for raw_source in active_raw_sources:
        before_count = len(list_source_segments(raw_source_id=raw_source.id))
        ensure_source_segments_for_raw_source(raw_source)
        after_count = len(list_source_segments(raw_source_id=raw_source.id))
        if raw_source.id not in segmented_ids_before and after_count > before_count:
            backfilled_ids.append(raw_source.id)

    segments_after = [segment for segment in list_source_segments() if segment.raw_source_id in raw_source_ids]
    extracted_after = [segment for segment in list_extracted_segments() if segment.raw_source_id in raw_source_ids]
    pending_segments = [
        segment
        for segment in segments_after
        if segment.attribution_status in {"pending", "needs_review"}
    ]

    return SourceSegmentBackfillResponse(
        profile_id=profile_id,
        include_deleted=include_deleted,
        raw_source_count=len(active_raw_sources),
        raw_sources_missing_segment_before=len(missing_sources_before),
        raw_sources_with_segment_after=len({segment.raw_source_id for segment in segments_after}),
        source_segments_created=max(0, len(segments_after) - len(segments_before)),
        extracted_segments_created=max(0, len(extracted_after) - len(extracted_before)),
        pending_segment_count=len(pending_segments),
        backfilled_raw_source_ids=backfilled_ids,
    )


def find_voice_reference_segment(raw_source_id: UUID) -> SourceSegmentSchema | None:
    segments = list_source_segments(raw_source_id=raw_source_id)
    if not segments:
        return None
    for segment in segments:
        if segment.metadata.get("purpose") == "voice_reference":
            return segment
    return segments[0]


def voice_generation_block_reason(segment: SourceSegmentSchema | None) -> str | None:
    if segment is None:
        return "Voice reference has no source-segment attribution record."
    if segment.target_person != "target_person":
        return "Voice reference segment is not confirmed as the target person."
    if segment.attribution_status != "confirmed":
        return "Voice reference segment attribution is not confirmed."
    if not segment.consent_confirmed:
        return "Voice reference segment consent is not confirmed."
    if VOICE_GENERATION_USE not in segment.permitted_uses and VOICE_REFERENCE_USE not in segment.permitted_uses:
        return "Voice reference segment is not permitted for voice generation."
    return None
