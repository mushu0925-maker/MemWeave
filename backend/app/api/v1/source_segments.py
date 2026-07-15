from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.schemas.source_segment import (
    ExtractedSegmentSchema,
    SourceSegmentBackfillResponse,
    SourceSegmentSchema,
    SourceSegmentUpdate,
)
from app.services.profile_store import get_profile
from app.services.raw_source_store import get_raw_source, list_raw_sources
from app.services.source_segment_store import (
    backfill_source_segments,
    ensure_source_segments_for_raw_source,
    list_extracted_segments,
    list_source_segments,
    update_source_segment,
)

router = APIRouter(prefix="/source-segments", tags=["source_segments"])


@router.get("", response_model=list[SourceSegmentSchema])
def read_source_segments(
    profile_id: UUID | None = Query(default=None),
    raw_source_id: UUID | None = Query(default=None),
    ensure_missing: bool = Query(default=False),
) -> list[SourceSegmentSchema]:
    if profile_id is not None:
        get_profile(profile_id)
    if ensure_missing:
        if raw_source_id is not None:
            ensure_source_segments_for_raw_source(get_raw_source(raw_source_id))
        elif profile_id is not None:
            for raw_source in list_raw_sources(profile_id):
                ensure_source_segments_for_raw_source(raw_source)
    return list_source_segments(profile_id=profile_id, raw_source_id=raw_source_id)


@router.get("/extracted", response_model=list[ExtractedSegmentSchema])
def read_extracted_segments(
    profile_id: UUID | None = Query(default=None),
    raw_source_id: UUID | None = Query(default=None),
    source_segment_id: UUID | None = Query(default=None),
) -> list[ExtractedSegmentSchema]:
    if profile_id is not None:
        get_profile(profile_id)
    return list_extracted_segments(
        profile_id=profile_id,
        raw_source_id=raw_source_id,
        source_segment_id=source_segment_id,
    )


@router.post("/backfill", response_model=SourceSegmentBackfillResponse)
def backfill_missing_source_segments(
    profile_id: UUID | None = Query(default=None),
    include_deleted: bool = Query(default=False),
) -> SourceSegmentBackfillResponse:
    if profile_id is not None:
        get_profile(profile_id)
    return backfill_source_segments(
        list_raw_sources(profile_id, include_deleted=include_deleted),
        profile_id=profile_id,
        include_deleted=include_deleted,
    )


@router.post("/raw-sources/{raw_source_id}/ensure", response_model=list[SourceSegmentSchema])
def ensure_raw_source_segments(raw_source_id: UUID) -> list[SourceSegmentSchema]:
    return ensure_source_segments_for_raw_source(get_raw_source(raw_source_id))


@router.patch("/{segment_id}", response_model=SourceSegmentSchema)
def patch_source_segment(segment_id: UUID, payload: SourceSegmentUpdate) -> SourceSegmentSchema:
    return update_source_segment(segment_id, payload)
