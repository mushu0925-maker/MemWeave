from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.memory import SourceType


SegmentTargetPerson = Literal["target_person", "user", "other", "unknown"]
SegmentAttributionStatus = Literal["pending", "confirmed", "rejected", "needs_review"]


class SourceSegmentSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    raw_source_id: UUID
    profile_id: UUID | None = None
    source_type: SourceType
    segment_index: int = Field(ge=0)
    start_char: int | None = Field(default=None, ge=0)
    end_char: int | None = Field(default=None, ge=0)
    start_seconds: float | None = Field(default=None, ge=0)
    end_seconds: float | None = Field(default=None, ge=0)
    text_excerpt: str = Field(default="", max_length=4000)
    target_person: SegmentTargetPerson = "unknown"
    attribution_status: SegmentAttributionStatus = "pending"
    consent_confirmed: bool = False
    consent_note: str = Field(default="", max_length=1000)
    permitted_uses: list[str] = Field(default_factory=list, max_length=16)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class SourceSegmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_source_id: UUID
    profile_id: UUID | None = None
    source_type: SourceType
    segment_index: int = Field(default=0, ge=0)
    start_char: int | None = Field(default=None, ge=0)
    end_char: int | None = Field(default=None, ge=0)
    start_seconds: float | None = Field(default=None, ge=0)
    end_seconds: float | None = Field(default=None, ge=0)
    text_excerpt: str = Field(default="", max_length=4000)
    target_person: SegmentTargetPerson = "unknown"
    attribution_status: SegmentAttributionStatus = "pending"
    consent_confirmed: bool = False
    consent_note: str = Field(default="", max_length=1000)
    permitted_uses: list[str] = Field(default_factory=list, max_length=16)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceSegmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_person: SegmentTargetPerson | None = None
    attribution_status: SegmentAttributionStatus | None = None
    consent_confirmed: bool | None = None
    consent_note: str | None = Field(default=None, max_length=1000)
    permitted_uses: list[str] | None = Field(default=None, max_length=16)
    metadata: dict[str, Any] | None = None


class SourceSegmentBackfillResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: UUID | None = None
    include_deleted: bool = False
    raw_source_count: int = Field(ge=0)
    raw_sources_missing_segment_before: int = Field(ge=0)
    raw_sources_with_segment_after: int = Field(ge=0)
    source_segments_created: int = Field(ge=0)
    extracted_segments_created: int = Field(ge=0)
    pending_segment_count: int = Field(ge=0)
    backfilled_raw_source_ids: list[UUID] = Field(default_factory=list)


class ExtractedSegmentSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    source_segment_id: UUID
    raw_source_id: UUID
    profile_id: UUID | None = None
    extraction_type: str = Field(default="source_text", max_length=80)
    extracted_text: str = Field(default="", max_length=120_000)
    confidence: float = Field(default=0, ge=0, le=1)
    model_name: str | None = Field(default=None, max_length=160)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ExtractedSegmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_segment_id: UUID
    raw_source_id: UUID
    profile_id: UUID | None = None
    extraction_type: str = Field(default="source_text", max_length=80)
    extracted_text: str = Field(default="", max_length=120_000)
    confidence: float = Field(default=0, ge=0, le=1)
    model_name: str | None = Field(default=None, max_length=160)
    metadata: dict[str, Any] = Field(default_factory=dict)
