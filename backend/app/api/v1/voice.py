from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse

from app.schemas.voice_generation import (
    VoiceGenerationListResponse,
    VoiceGenerationRequest,
    VoiceGenerationResponse,
    VoiceGenerationStatusResponse,
    VoiceReferenceUploadResponse,
)
from app.services.voice_generation_service import (
    audio_file_for_record,
    extract_voice_reference_audio,
    generate_authorized_voice,
    list_profile_voice_generation_records,
    save_voice_reference_upload,
    voice_generation_status,
)

router = APIRouter(prefix="/voice", tags=["voice"])


@router.get("/status", response_model=VoiceGenerationStatusResponse)
def read_voice_generation_status() -> VoiceGenerationStatusResponse:
    return voice_generation_status()


@router.post("/profiles/{profile_id}/references", response_model=VoiceReferenceUploadResponse)
async def upload_voice_reference(
    profile_id: UUID,
    upload: UploadFile = File(...),
    consent_confirmed: bool = Form(default=False),
    consent_note: str = Form(default=""),
) -> VoiceReferenceUploadResponse:
    return await save_voice_reference_upload(
        profile_id=profile_id,
        upload=upload,
        consent_confirmed=consent_confirmed,
        consent_note=consent_note,
    )


@router.post("/profiles/{profile_id}/references/{raw_source_id}/extract-audio", response_model=VoiceReferenceUploadResponse)
def extract_saved_video_voice_reference(
    profile_id: UUID,
    raw_source_id: UUID,
) -> VoiceReferenceUploadResponse:
    return extract_voice_reference_audio(profile_id=profile_id, raw_source_id=raw_source_id)


@router.post("/profiles/{profile_id}/generate", response_model=VoiceGenerationResponse)
def create_authorized_voice_generation(
    profile_id: UUID,
    payload: VoiceGenerationRequest,
) -> VoiceGenerationResponse:
    return generate_authorized_voice(profile_id=profile_id, payload=payload)


@router.get("/profiles/{profile_id}/generations", response_model=VoiceGenerationListResponse)
def read_profile_voice_generations(profile_id: UUID) -> VoiceGenerationListResponse:
    return VoiceGenerationListResponse(records=list_profile_voice_generation_records(profile_id))


@router.get("/generations/{record_id}/audio")
def read_voice_generation_audio(record_id: UUID) -> FileResponse:
    path, mime_type = audio_file_for_record(record_id)
    return FileResponse(path, media_type=mime_type, filename=path.name)
