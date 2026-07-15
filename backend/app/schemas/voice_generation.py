from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.source_segment import SegmentAttributionStatus, SegmentTargetPerson


VoiceGenerationStatus = Literal["success", "failed", "blocked", "skipped"]
VoiceReferenceStatus = Literal["active", "revoked", "deleted"]


class VoiceReferenceUploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_source_id: UUID
    profile_id: UUID
    file_name: str
    mime_type: str
    file_path: str
    size_bytes: int
    consent_confirmed: bool
    ai_generated_notice_required: bool = True
    voice_reference_kind: Literal["audio", "video"]
    tts_reference_ready: bool
    audio_extraction_status: str = ""
    audio_extraction_error: str = ""
    source_segment_id: UUID | None = None
    segment_target_person: SegmentTargetPerson = "unknown"
    segment_attribution_status: SegmentAttributionStatus = "pending"
    voice_generation_ready: bool = False
    voice_generation_block_reason: str = ""
    message: str


class VoiceGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply_text: str = Field(min_length=1, max_length=4000)
    reference_raw_source_id: UUID
    chat_record_id: UUID | None = None
    consent_confirmed: bool = False
    model: str = Field(default="indextts2", max_length=80)
    emotion: str | None = Field(default=None, max_length=80)
    generation_notes: str = Field(default="", max_length=500)


class VoiceGenerationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    profile_id: UUID
    reference_raw_source_id: UUID
    chat_record_id: UUID | None = None
    reply_text: str = Field(max_length=4000)
    model: str = Field(max_length=80)
    provider: str = Field(default="indextts2", max_length=80)
    status: VoiceGenerationStatus
    consent_confirmed: bool
    ai_generated: bool = True
    output_file_path: str | None = Field(default=None, max_length=1000)
    output_mime_type: str | None = Field(default=None, max_length=160)
    duration_seconds: float | None = None
    error: str = Field(default="", max_length=1000)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    created_at: datetime


class VoiceGenerationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record: VoiceGenerationRecord
    audio_url: str | None = None
    message: str


class VoiceGenerationStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    provider: str
    configured: bool
    base_url: str | None = None
    reference_dir: str
    output_dir: str
    ffmpeg_configured: bool = False
    ffmpeg_path: str = ""
    ffmpeg_available: bool = False
    ffmpeg_error: str = ""
    video_reference_supported: bool = False
    safety: str


class VoiceGenerationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[VoiceGenerationRecord]
