from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.core.security import mask_pii
from app.schemas.ingest import IngestResponse
from app.schemas.raw_source import RawSourceSchema
from app.services.media_extraction import extract_uploaded_source
from app.services.persona_item_store import hide_persona_items_for_source
from app.services.profile_store import get_profile
from app.services.raw_source_store import (
    get_raw_source,
    list_raw_sources,
    move_raw_source_to_trash,
    purge_raw_source,
    restore_raw_source,
    update_raw_source_content,
)
from app.services.source_segment_store import list_extracted_segments, list_source_segments
from app.workflows.ingest_workflow import (
    IngestClassificationFailure,
    classify_raw_source,
    persist_uncertainty_from_diagnostics,
    save_classification_persona_items,
)

router = APIRouter(prefix="/raw-sources", tags=["raw_sources"])

UNAVAILABLE_IMAGE_EXTRACTION_STATUSES = {"disabled", "not_configured", "failed"}


def _image_extraction_unavailable(raw_source: RawSourceSchema) -> bool:
    return (
        raw_source.source_type == "image"
        and str(raw_source.metadata.get("extraction_status") or "") in UNAVAILABLE_IMAGE_EXTRACTION_STATUSES
    )


def _saved_image_without_classification_response(
    *,
    raw_source: RawSourceSchema,
    exc: IngestClassificationFailure,
    pii_summary: dict[str, int] | None = None,
) -> IngestResponse:
    source_segments = list_source_segments(raw_source_id=raw_source.id)
    extracted_segments = list_extracted_segments(raw_source_id=raw_source.id)
    diagnostics = {
        "classifier_provider": exc.provider,
        "classifier_model_call_status": exc.status,
        "classifier_model_call_reason": exc.reason,
        "classifier_model_name": exc.model_name,
        "candidate_library_keys": exc.candidate_library_keys,
        "notes": exc.notes,
        "plugin_metadata": exc.plugin_metadata,
        "classification_status": "skipped_after_unavailable_image_extraction",
        "classification_failure_preserved_raw_source": True,
        "extraction_status": raw_source.metadata.get("extraction_status"),
        "extraction_provider": raw_source.metadata.get("extraction_provider"),
        "extraction_error": raw_source.metadata.get("extraction_error"),
        "extraction_hint": raw_source.metadata.get("extraction_hint"),
        "source_segment_count": len(source_segments),
        "source_segment_ids": [str(segment.id) for segment in source_segments],
        "extracted_segment_count": len(extracted_segments),
        "segment_attribution_status": "pending",
    }
    return IngestResponse(
        raw_source=raw_source,
        persona_items=[],
        sanitized_content=raw_source.pii_masked_text,
        pii_summary=pii_summary or {},
        routing_key=f"{raw_source.source_type}:reextract",
        persona_library_classification=None,
        diagnostics=diagnostics,
    )


@router.get("", response_model=list[RawSourceSchema])
def read_raw_sources(
    profile_id: UUID | None = Query(default=None),
    include_deleted: bool = Query(default=False),
    deleted_only: bool = Query(default=False),
) -> list[RawSourceSchema]:
    if profile_id is not None:
        get_profile(profile_id)
    return list_raw_sources(profile_id, include_deleted=include_deleted, deleted_only=deleted_only)


@router.delete("/{source_id}", response_model=RawSourceSchema)
def delete_raw_source_to_trash(source_id: UUID) -> RawSourceSchema:
    """删除只进入回收站；不级联处理 persona_items。"""

    return move_raw_source_to_trash(source_id)


@router.post("/{source_id}/restore", response_model=RawSourceSchema)
def restore_deleted_raw_source(source_id: UUID) -> RawSourceSchema:
    return restore_raw_source(source_id)


@router.delete("/{source_id}/purge", response_model=RawSourceSchema)
def purge_deleted_raw_source(source_id: UUID) -> RawSourceSchema:
    """彻底删除单条原数据；不级联处理 persona_items。"""

    return purge_raw_source(source_id)


@router.post("/{source_id}/reextract", response_model=IngestResponse)
def reextract_raw_source(source_id: UUID) -> IngestResponse:
    raw_source = get_raw_source(source_id)
    if raw_source.profile_id is not None:
        get_profile(raw_source.profile_id)

    pii_summary: dict[str, int] = {}
    if raw_source.source_type == "image" and raw_source.file_path:
        stored_path = Path(raw_source.file_path)
        if stored_path.exists():
            upload_notes = str(raw_source.metadata.get("upload_notes") or "")
            extracted = extract_uploaded_source(
                stored_path.read_bytes(),
                filename=raw_source.file_name,
                content_type=raw_source.mime_type,
                notes=upload_notes,
            )
            pii_result = mask_pii(extracted.raw_content)
            metadata = {
                **raw_source.metadata,
                **extracted.metadata,
                "stored_file_path": raw_source.file_path,
                "stored_file_name": raw_source.metadata.get("stored_file_name") or stored_path.name,
                "reextract_from_stored_file": True,
                "reextract_file_exists": True,
            }
            raw_source = update_raw_source_content(
                raw_source.id,
                original_text=extracted.raw_content,
                extracted_text=extracted.raw_content,
                pii_masked_text=pii_result.content,
                file_path=raw_source.file_path,
                file_name=raw_source.file_name,
                mime_type=raw_source.mime_type,
                metadata=metadata,
            )
            pii_summary = pii_result.replacements
        else:
            metadata = {
                **raw_source.metadata,
                "reextract_from_stored_file": True,
                "reextract_file_exists": False,
                "reextract_file_error": f"Stored file not found: {raw_source.file_path}",
            }
            raw_source = update_raw_source_content(
                raw_source.id,
                original_text=raw_source.original_text,
                extracted_text=raw_source.extracted_text,
                pii_masked_text=raw_source.pii_masked_text,
                file_path=raw_source.file_path,
                file_name=raw_source.file_name,
                mime_type=raw_source.mime_type,
                metadata=metadata,
            )

    try:
        classification, diagnostics, extraction_method, model_name = classify_raw_source(raw_source)
    except IngestClassificationFailure as exc:
        if _image_extraction_unavailable(raw_source):
            return _saved_image_without_classification_response(
                raw_source=raw_source,
                exc=exc,
                pii_summary=pii_summary,
            )
        raise HTTPException(status_code=422, detail=exc.to_http_detail()) from exc

    hide_before = datetime.now(UTC)
    persona_items = save_classification_persona_items(
        raw_source=raw_source,
        classification=classification,
        extraction_method=extraction_method,
        model_name=model_name,
    )
    persist_uncertainty_from_diagnostics(raw_source=raw_source, diagnostics=diagnostics)
    hidden_count = 0
    if persona_items:
        hidden_count = hide_persona_items_for_source(source_id, reason="reextract_success", before=hide_before)
    source_segments = list_source_segments(raw_source_id=raw_source.id)
    extracted_segments = list_extracted_segments(raw_source_id=raw_source.id)
    return IngestResponse(
        raw_source=raw_source,
        persona_items=persona_items,
        sanitized_content=raw_source.pii_masked_text,
        pii_summary=pii_summary,
        routing_key=f"{raw_source.source_type}:reextract",
        persona_library_classification=classification,
        diagnostics={
            **diagnostics,
            "hidden_old_persona_items": hidden_count,
            "new_persona_items": len(persona_items),
            "source_segment_count": len(source_segments),
            "source_segment_ids": [str(segment.id) for segment in source_segments],
            "extracted_segment_count": len(extracted_segments),
            "segment_attribution_status": "pending",
        },
    )
