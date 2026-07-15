from __future__ import annotations

import base64
import hashlib
import mimetypes
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings
from app.schemas.memory import SourceType
from app.schemas.raw_source import RawSourceCreate, RawSourceSchema
from app.schemas.voice_generation import (
    VoiceGenerationRequest,
    VoiceGenerationResponse,
    VoiceGenerationStatusResponse,
    VoiceReferenceUploadResponse,
)
from app.services.chat_store import list_chat_records
from app.services.monitoring_store import record_monitoring_event
from app.services.profile_store import get_profile
from app.services.raw_source_store import get_raw_source, save_raw_source, update_raw_source_metadata
from app.services.source_segment_store import (
    VOICE_GENERATION_USE,
    VOICE_REFERENCE_USE,
    ensure_source_segments_for_raw_source,
    find_voice_reference_segment,
    voice_generation_block_reason,
)
from app.services.voice_generation_store import (
    list_voice_generation_records,
    new_voice_generation_record,
    save_voice_generation_record,
)

MAX_REFERENCE_BYTES = 100 * 1024 * 1024
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".webm"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


@dataclass(frozen=True)
class IndexTTS2AdapterResult:
    audio_bytes: bytes
    mime_type: str
    metadata: dict[str, str | int | float | bool | None]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _project_root() -> Path:
    return _backend_root().parent


def _configured_path(value: str) -> Path:
    configured = Path(value)
    if configured.is_absolute():
        return configured
    return _backend_root() / configured


def _resolve_ffmpeg_path() -> tuple[str, bool, str]:
    settings = get_settings()
    configured_value = settings.voice_video_ffmpeg_path.strip() if settings.voice_video_ffmpeg_path else "ffmpeg"
    candidates: list[str] = []
    configured = Path(configured_value)
    if configured.is_absolute() or configured.parent != Path("."):
        if configured.is_absolute():
            candidates.append(str(configured))
        else:
            candidates.append(str(_project_root() / configured))
            candidates.append(str(_backend_root() / configured))
    else:
        project_local = _project_root() / "tools" / "ffmpeg" / "ffmpeg.exe"
        candidates.append(str(project_local))
        which_result = shutil.which(configured_value)
        if which_result:
            candidates.append(which_result)
        candidates.append(configured_value)

    seen: set[str] = set()
    errors: list[str] = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        path_candidate = Path(candidate)
        if path_candidate.is_absolute() and not path_candidate.exists():
            errors.append(f"{candidate} not found")
            continue
        try:
            completed = subprocess.run(
                [candidate, "-version"],
                capture_output=True,
                check=False,
                text=True,
                timeout=10,
            )
        except FileNotFoundError:
            errors.append(f"{candidate} not found")
            continue
        except subprocess.TimeoutExpired:
            errors.append(f"{candidate} version check timed out")
            continue
        except OSError as exc:
            errors.append(f"{candidate}: {exc}")
            continue
        if completed.returncode == 0:
            return candidate, True, ""
        message = (completed.stderr or completed.stdout or "ffmpeg version check failed").strip()
        errors.append(f"{candidate}: {message[:300]}")
    return candidates[0] if candidates else configured_value, False, "; ".join(errors)[:1000]


def _safe_filename(filename: str | None, fallback_extension: str) -> str:
    stem = Path(filename or "voice-reference").stem
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-._")[:80] or "voice-reference"
    extension = Path(filename or "").suffix.lower() or fallback_extension
    return f"{stem}-{uuid4().hex[:12]}{extension}"


def _extension(filename: str | None) -> str:
    return Path(filename or "").suffix.lower()


def _is_audio_or_video(filename: str | None, content_type: str | None) -> bool:
    extension = _extension(filename)
    if extension in AUDIO_EXTENSIONS | VIDEO_EXTENSIONS:
        return True
    normalized = content_type or ""
    return normalized.startswith("audio/") or normalized.startswith("video/")


def _source_type_from_reference(filename: str | None, content_type: str | None) -> SourceType:
    extension = _extension(filename)
    normalized = content_type or ""
    if extension in AUDIO_EXTENSIONS or normalized.startswith("audio/"):
        return "audio"
    if extension in VIDEO_EXTENSIONS or normalized.startswith("video/"):
        return "file"
    return "file"


def _content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _audio_url(record_id: UUID) -> str:
    return f"/api/v1/voice/generations/{record_id}/audio"


def _is_video_reference(filename: str | None, mime_type: str) -> bool:
    return mime_type.startswith("video/") or _extension(filename) in VIDEO_EXTENSIONS


def _extract_video_reference_audio(
    *,
    video_path: Path,
    output_path: Path,
) -> tuple[Path | None, str, str]:
    settings = get_settings()
    ffmpeg_path, ffmpeg_available, ffmpeg_error = _resolve_ffmpeg_path()
    if not ffmpeg_available:
        detail = ffmpeg_error or "ffmpeg was not found; install ffmpeg or upload an audio reference."
        return None, "ffmpeg_missing", detail
    command = [
        ffmpeg_path,
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "24000",
        "-ac",
        "1",
        str(output_path),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=settings.voice_video_extract_timeout_seconds,
        )
    except FileNotFoundError:
        return None, "ffmpeg_missing", "ffmpeg was not found; install ffmpeg or upload an audio reference."
    except subprocess.TimeoutExpired:
        return None, "timeout", "ffmpeg audio extraction timed out."
    except OSError as exc:
        return None, "failed", str(exc)
    if completed.returncode != 0:
        error = (completed.stderr or completed.stdout or "ffmpeg audio extraction failed").strip()
        return None, "failed", error[:1000]
    if not output_path.exists() or output_path.stat().st_size == 0:
        return None, "failed", "ffmpeg produced no audio output."
    return output_path, "extracted", ""


def voice_generation_status() -> VoiceGenerationStatusResponse:
    settings = get_settings()
    ffmpeg_path, ffmpeg_available, ffmpeg_error = _resolve_ffmpeg_path()
    return VoiceGenerationStatusResponse(
        enabled=settings.enable_voice_generation,
        provider=settings.voice_generation_provider,
        configured=bool(settings.voice_generation_base_url),
        base_url=settings.voice_generation_base_url,
        reference_dir=str(_configured_path(settings.voice_reference_dir)),
        output_dir=str(_configured_path(settings.voice_output_dir)),
        ffmpeg_configured=bool(ffmpeg_path),
        ffmpeg_path=ffmpeg_path,
        ffmpeg_available=ffmpeg_available,
        ffmpeg_error=ffmpeg_error,
        video_reference_supported=ffmpeg_available,
        safety=(
            "Voice generation is disabled by default. It only speaks fixed reply_text, "
            "requires explicit source-segment target-person attribution and consent, "
            "and must be labeled AI-generated."
        ),
    )


def _reference_ready_fields(raw_source: RawSourceSchema) -> dict[str, object]:
    ensure_source_segments_for_raw_source(raw_source)
    segment = find_voice_reference_segment(raw_source.id)
    block_reason = voice_generation_block_reason(segment)
    return {
        "source_segment_id": segment.id if segment else None,
        "segment_target_person": segment.target_person if segment else "unknown",
        "segment_attribution_status": segment.attribution_status if segment else "pending",
        "voice_generation_ready": block_reason is None,
        "voice_generation_block_reason": block_reason or "",
    }


async def save_voice_reference_upload(
    *,
    profile_id: UUID,
    upload: UploadFile,
    consent_confirmed: bool,
    consent_note: str,
) -> VoiceReferenceUploadResponse:
    get_profile(profile_id)
    if not consent_confirmed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Voice reference consent is required.")

    data = await upload.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Uploaded reference file is empty.")
    if len(data) > MAX_REFERENCE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Voice reference is larger than 100 MB.")
    if not _is_audio_or_video(upload.filename, upload.content_type):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Voice reference must be an audio or video file.")

    settings = get_settings()
    directory = _configured_path(settings.voice_reference_dir) / str(profile_id)
    directory.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(upload.filename, ".bin")
    path = directory / safe_name
    path.write_bytes(data)

    mime_type = upload.content_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
    source_type = _source_type_from_reference(upload.filename, mime_type)
    is_video = _is_video_reference(upload.filename, mime_type)
    tts_reference_path = path
    tts_reference_mime_type = mime_type
    extraction_status = "not_required"
    extraction_error = ""
    extracted_audio_path: Path | None = None
    if is_video:
        extracted_audio_path, extraction_status, extraction_error = _extract_video_reference_audio(
            video_path=path,
            output_path=directory / f"{Path(safe_name).stem}.reference.wav",
        )
        if extracted_audio_path is not None:
            tts_reference_path = extracted_audio_path
            tts_reference_mime_type = "audio/wav"
    metadata: dict[str, str | int | float | bool | None] = {
        "voice_reference": True,
        "voice_reference_status": "active",
        "voice_reference_consent_confirmed": True,
        "voice_reference_consent_note": consent_note.strip()[:1000],
        "voice_reference_uploaded_at": _now_iso(),
        "voice_reference_ai_generated_notice_required": True,
        "voice_reference_file_sha256": _content_hash(data),
        "voice_reference_original_filename": upload.filename or "",
        "voice_reference_kind": "video" if is_video else "audio",
        "voice_reference_original_file_path": str(path),
        "voice_reference_tts_file_path": str(tts_reference_path),
        "voice_reference_tts_mime_type": tts_reference_mime_type,
        "voice_reference_audio_extraction_status": extraction_status,
        "voice_reference_audio_extraction_error": extraction_error,
    }
    raw_source = save_raw_source(
        RawSourceCreate(
            profile_id=profile_id,
            source_type=source_type,
            original_text="Authorized voice reference file. This is not persona evidence by itself.",
            extracted_text="Authorized voice reference file for external TTS only.",
            file_path=str(path),
            file_name=safe_name,
            mime_type=mime_type,
            pii_masked_text="Authorized voice reference file for external TTS only.",
            metadata=metadata,
        )
    )
    ready_fields = _reference_ready_fields(raw_source)
    return VoiceReferenceUploadResponse(
        raw_source_id=raw_source.id,
        profile_id=profile_id,
        file_name=safe_name,
        mime_type=mime_type,
        file_path=str(path),
        size_bytes=len(data),
        consent_confirmed=True,
        voice_reference_kind="video" if is_video else "audio",
        tts_reference_ready=not is_video or extracted_audio_path is not None,
        audio_extraction_status=extraction_status,
        audio_extraction_error=extraction_error,
        **ready_fields,
        message="Voice reference saved. It can be used only for authorized AI-generated voice output.",
    )


def extract_voice_reference_audio(
    *,
    profile_id: UUID,
    raw_source_id: UUID,
) -> VoiceReferenceUploadResponse:
    get_profile(profile_id)
    reference = _validate_reference(profile_id, raw_source_id, require_segment_ready=False)
    metadata = dict(reference.metadata)
    if metadata.get("voice_reference_kind") != "video":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Only video voice references need audio extraction.")
    original_path_value = metadata.get("voice_reference_original_file_path") or reference.file_path
    if not isinstance(original_path_value, str) or not original_path_value.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Video reference file path is missing.")
    video_path = Path(original_path_value)
    if not video_path.exists():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Video reference file does not exist on disk.")

    output_path = video_path.with_name(f"{video_path.stem}.reference.wav")
    extracted_audio_path, extraction_status, extraction_error = _extract_video_reference_audio(
        video_path=video_path,
        output_path=output_path,
    )
    metadata["voice_reference_audio_extraction_status"] = extraction_status
    metadata["voice_reference_audio_extraction_error"] = extraction_error
    if extracted_audio_path is not None:
        metadata["voice_reference_tts_file_path"] = str(extracted_audio_path)
        metadata["voice_reference_tts_mime_type"] = "audio/wav"
    updated = update_raw_source_metadata(reference.id, metadata)
    ready_fields = _reference_ready_fields(updated)
    ready = extracted_audio_path is not None
    return VoiceReferenceUploadResponse(
        raw_source_id=updated.id,
        profile_id=profile_id,
        file_name=updated.file_name or video_path.name,
        mime_type=updated.mime_type or "application/octet-stream",
        file_path=updated.file_path or str(video_path),
        size_bytes=video_path.stat().st_size,
        consent_confirmed=bool(metadata.get("voice_reference_consent_confirmed")),
        voice_reference_kind="video",
        tts_reference_ready=ready,
        audio_extraction_status=extraction_status,
        audio_extraction_error=extraction_error,
        **ready_fields,
        message=(
            "Video reference audio extracted. It can be used only for authorized AI-generated voice output."
            if ready
            else "Video reference is still saved, but audio extraction is not ready."
        ),
    )


def _validate_reference(
    profile_id: UUID,
    reference_raw_source_id: UUID,
    *,
    require_segment_ready: bool = True,
) -> RawSourceSchema:
    reference = get_raw_source(reference_raw_source_id)
    if reference.profile_id != profile_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voice reference not found for this profile.")
    if reference.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Voice reference has been deleted.")
    if not reference.metadata.get("voice_reference"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Raw source is not an authorized voice reference.")
    if not reference.metadata.get("voice_reference_consent_confirmed"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Voice reference consent is missing.")
    if require_segment_ready:
        ensure_source_segments_for_raw_source(reference)
        segment = find_voice_reference_segment(reference.id)
        block_reason = voice_generation_block_reason(segment)
        if block_reason:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=block_reason)
    if not reference.file_path:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Voice reference file path is missing.")
    if not Path(reference.file_path).exists():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Voice reference file does not exist on disk.")
    return reference


def _tts_reference_path(reference: RawSourceSchema) -> str:
    metadata_path = reference.metadata.get("voice_reference_tts_file_path")
    path_value = metadata_path if isinstance(metadata_path, str) and metadata_path.strip() else reference.file_path
    if not path_value:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Voice reference audio path is missing.")
    path = Path(path_value)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Voice reference audio file does not exist on disk.")

    reference_kind = reference.metadata.get("voice_reference_kind")
    extraction_status = reference.metadata.get("voice_reference_audio_extraction_status")
    if reference_kind == "video" and extraction_status != "extracted":
        extraction_error = reference.metadata.get("voice_reference_audio_extraction_error")
        detail = "Video reference was saved, but audio extraction is not ready. Install ffmpeg or upload an audio reference."
        if isinstance(extraction_error, str) and extraction_error:
            detail = f"{detail} Extraction error: {extraction_error}"
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)

    suffix = path.suffix.lower()
    mime_type = reference.metadata.get("voice_reference_tts_mime_type")
    if suffix not in AUDIO_EXTENSIONS and not (isinstance(mime_type, str) and mime_type.startswith("audio/")):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Voice reference for generation must be an audio file.")
    return str(path)


def _validate_chat_record(profile_id: UUID, chat_record_id: UUID | None, reply_text: str) -> None:
    if chat_record_id is None:
        return
    for record in list_chat_records(profile_id, limit=500):
        if record.id == chat_record_id:
            if record.assistant_message.strip() != reply_text.strip():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="reply_text must match the selected chat record assistant_message.",
                )
            return
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat record not found for this profile.")


def _index_tts2_payload(
    *,
    text: str,
    reference_path: str,
    emotion: str | None,
) -> dict[str, str | bool | None]:
    return {
        "text": text,
        "prompt_audio": reference_path,
        "reference_audio": reference_path,
        "audio_path": reference_path,
        "emotion": emotion,
        "return_base64": True,
        "ai_generated": True,
    }


def _call_indextts2(
    *,
    text: str,
    reference_path: str,
    emotion: str | None,
) -> IndexTTS2AdapterResult:
    settings = get_settings()
    if not settings.enable_voice_generation:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Voice generation is disabled.")
    if not settings.voice_generation_base_url:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="IndexTTS2 endpoint is not configured.")

    base_url = settings.voice_generation_base_url.rstrip("/")
    endpoint_errors: list[str] = []
    for suffix in ("/synthesize", "/tts", "/generate"):
        url = f"{base_url}{suffix}"
        try:
            response = httpx.post(
                url,
                json=_index_tts2_payload(text=text, reference_path=reference_path, emotion=emotion),
                timeout=settings.voice_generation_timeout_seconds,
            )
        except httpx.HTTPError as exc:
            endpoint_errors.append(f"{suffix}: {exc}")
            continue
        if response.status_code == 404:
            endpoint_errors.append(f"{suffix}: 404")
            continue
        if not response.is_success:
            endpoint_errors.append(f"{suffix}: {response.status_code} {response.text[:300]}")
            continue
        content_type = response.headers.get("content-type", "")
        if content_type.startswith("audio/") or response.content[:4] == b"RIFF":
            return IndexTTS2AdapterResult(response.content, content_type or "audio/wav", {"adapter_endpoint": suffix})
        try:
            payload = response.json()
        except ValueError:
            endpoint_errors.append(f"{suffix}: response was not audio or JSON")
            continue
        audio_b64 = payload.get("audio_base64") or payload.get("audio") or payload.get("wav_base64")
        if isinstance(audio_b64, str) and audio_b64.strip():
            return IndexTTS2AdapterResult(
                base64.b64decode(audio_b64),
                str(payload.get("mime_type") or "audio/wav"),
                {
                    "adapter_endpoint": suffix,
                    "remote_duration_seconds": payload.get("duration_seconds") if isinstance(payload.get("duration_seconds"), (int, float)) else None,
                },
            )
        audio_url = payload.get("audio_url") or payload.get("url")
        if isinstance(audio_url, str) and audio_url:
            audio_response = httpx.get(audio_url, timeout=settings.voice_generation_timeout_seconds)
            if audio_response.is_success:
                return IndexTTS2AdapterResult(
                    audio_response.content,
                    audio_response.headers.get("content-type", "audio/wav"),
                    {"adapter_endpoint": suffix, "remote_audio_url": audio_url},
                )
        endpoint_errors.append(f"{suffix}: JSON response had no supported audio field")
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="IndexTTS2 adapter call failed: " + " | ".join(endpoint_errors),
    )


def generate_authorized_voice(
    *,
    profile_id: UUID,
    payload: VoiceGenerationRequest,
) -> VoiceGenerationResponse:
    get_profile(profile_id)
    if not payload.consent_confirmed:
        record = save_voice_generation_record(
            new_voice_generation_record(
                profile_id=profile_id,
                reference_raw_source_id=payload.reference_raw_source_id,
                chat_record_id=payload.chat_record_id,
                reply_text=payload.reply_text,
                model=payload.model,
                provider="indextts2",
                status="blocked",
                consent_confirmed=False,
                error="Voice generation consent is required.",
            )
        )
        record_monitoring_event(
            event_type="voice_generation",
            status="blocked",
            profile_id=profile_id,
            raw_source_id=payload.reference_raw_source_id,
            chat_record_id=payload.chat_record_id,
            subject_id=str(record.id),
            workflow="authorized_voice_generation",
            provider=get_settings().voice_generation_provider,
            model_name=payload.model,
            input_summary=payload.reply_text[:1000],
            output_summary="voice_generation_blocked_no_consent",
            error="Voice generation consent is required.",
            used_raw_source_ids=[payload.reference_raw_source_id],
            metadata={"voice_generation_record_id": str(record.id), "ai_generated": True},
        )
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Voice generation consent is required.")

    reference = _validate_reference(profile_id, payload.reference_raw_source_id)
    _validate_chat_record(profile_id, payload.chat_record_id, payload.reply_text)
    settings = get_settings()
    output_dir = _configured_path(settings.voice_output_dir) / str(profile_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        reference_audio_path = _tts_reference_path(reference)
        adapter_result = _call_indextts2(
            text=payload.reply_text,
            reference_path=reference_audio_path,
            emotion=payload.emotion,
        )
        output_path = output_dir / f"voice-{uuid4().hex}.wav"
        output_path.write_bytes(adapter_result.audio_bytes)
        record = save_voice_generation_record(
            new_voice_generation_record(
                profile_id=profile_id,
                reference_raw_source_id=reference.id,
                chat_record_id=payload.chat_record_id,
                reply_text=payload.reply_text,
                model=payload.model,
                provider=settings.voice_generation_provider,
                status="success",
                consent_confirmed=True,
                output_file_path=str(output_path),
                output_mime_type=adapter_result.mime_type,
                duration_seconds=adapter_result.metadata.get("remote_duration_seconds") if isinstance(adapter_result.metadata.get("remote_duration_seconds"), (int, float)) else None,
                metadata={
                    **adapter_result.metadata,
                    "ai_generated_notice_required": True,
                    "reference_raw_source_id": str(reference.id),
                    "reference_source_segment_id": str(find_voice_reference_segment(reference.id).id)
                    if find_voice_reference_segment(reference.id)
                    else None,
                    "required_segment_uses": f"{VOICE_REFERENCE_USE},{VOICE_GENERATION_USE}",
                    "reference_audio_path": reference_audio_path,
                    "generation_notes": payload.generation_notes,
                },
            )
        )
        record_monitoring_event(
            event_type="voice_generation",
            status="success",
            profile_id=profile_id,
            raw_source_id=reference.id,
            chat_record_id=payload.chat_record_id,
            subject_id=str(record.id),
            workflow="authorized_voice_generation",
            provider=settings.voice_generation_provider,
            model_name=payload.model,
            input_summary=payload.reply_text[:1000],
            output_summary="voice_generation_success",
            used_raw_source_ids=[reference.id],
            metadata={"voice_generation_record_id": str(record.id), "ai_generated": True},
        )
        return VoiceGenerationResponse(
            record=record,
            audio_url=_audio_url(record.id),
            message="Voice generated. Output must be labeled AI-generated.",
        )
    except HTTPException as exc:
        record = save_voice_generation_record(
            new_voice_generation_record(
                profile_id=profile_id,
                reference_raw_source_id=reference.id,
                chat_record_id=payload.chat_record_id,
                reply_text=payload.reply_text,
                model=payload.model,
                provider=settings.voice_generation_provider,
                status="failed",
                consent_confirmed=True,
                error=str(exc.detail),
                metadata={"ai_generated_notice_required": True, "generation_notes": payload.generation_notes},
            )
        )
        record_monitoring_event(
            event_type="voice_generation",
            status="failed",
            profile_id=profile_id,
            raw_source_id=reference.id,
            chat_record_id=payload.chat_record_id,
            subject_id=str(record.id),
            workflow="authorized_voice_generation",
            provider=settings.voice_generation_provider,
            model_name=payload.model,
            input_summary=payload.reply_text[:1000],
            output_summary="voice_generation_failed",
            error=str(exc.detail),
            used_raw_source_ids=[reference.id],
            metadata={"voice_generation_record_id": str(record.id), "ai_generated": True},
        )
        raise


def list_profile_voice_generation_records(profile_id: UUID):
    get_profile(profile_id)
    return list_voice_generation_records(profile_id)


def audio_file_for_record(record_id: UUID) -> tuple[Path, str]:
    settings = get_settings()
    output_root = _configured_path(settings.voice_output_dir)
    for record in list_voice_generation_records_for_all_outputs():
        if record.id == record_id and record.output_file_path:
            path = Path(record.output_file_path)
            if not path.exists():
                break
            try:
                path.resolve().relative_to(output_root.resolve())
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Voice output path is outside output dir.") from exc
            return path, record.output_mime_type or "audio/wav"
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voice output not found.")


def list_voice_generation_records_for_all_outputs():
    from app.services.local_database import read_json_file

    records = read_json_file("voice_generation_records.json", [])
    if not isinstance(records, list):
        return []
    from app.schemas.voice_generation import VoiceGenerationRecord

    return [VoiceGenerationRecord.model_validate(record) for record in records]
