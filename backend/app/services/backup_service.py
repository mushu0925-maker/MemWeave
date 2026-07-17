from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import threading
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings
from app.schemas.backup import (
    BackupArchiveAttachment,
    BackupArchiveDocument,
    BackupImportPreview,
    BackupImportRequest,
    BackupImportResponse,
    BackupManifest,
    BackupProfilePreview,
)
from app.schemas.chat import ChatRecord
from app.schemas.clarification import QuestionTargetSchema, UncertainItemSchema
from app.schemas.persona_item import PersonaItemSchema
from app.schemas.profile import ProfileSchema
from app.schemas.raw_source import RawSourceSchema
from app.schemas.skill_version import SkillVersionSchema
from app.schemas.source_segment import ExtractedSegmentSchema, SourceSegmentSchema
from app.schemas.voice_generation import VoiceGenerationRecord
from app.services.profile_store import get_profile
from app.services.local_database import (
    data_dir,
    list_json_store_files,
    list_sqlite_documents,
    read_json_file,
    write_json_file,
)

BACKUP_FORMAT_VERSION = 1
MANIFEST_PATH = "manifest.json"
DATA_PREFIX = "data/"
ATTACHMENT_PREFIX = "attachments/"
MAX_IMPORT_BYTES = 2 * 1024 * 1024 * 1024
MAX_IMPORT_UNCOMPRESSED_BYTES = 4 * 1024 * 1024 * 1024
MAX_IMPORT_ENTRIES = 20_000
IMPORT_TOKEN_TTL = timedelta(minutes=30)

PROFILE_DOCUMENTS = (
    "profiles.json",
    "raw_sources.json",
    "persona_items.json",
    "skill_versions.json",
    "chat_records.json",
    "uncertain_items.json",
    "question_targets.json",
    "source_segments.json",
    "extracted_segments.json",
    "voice_generation_records.json",
)
GLOBAL_SAFE_DOCUMENTS = (
    "feature_policies.json",
    "distillation_plugin_policy.json",
    "library_plugin_policy.json",
    "monitoring_settings.json",
    "monitoring_events.json",
)
FULL_DOCUMENTS = PROFILE_DOCUMENTS + GLOBAL_SAFE_DOCUMENTS
DOCUMENT_VALIDATORS: dict[str, Any] = {
    "profiles.json": ProfileSchema,
    "raw_sources.json": RawSourceSchema,
    "persona_items.json": PersonaItemSchema,
    "skill_versions.json": SkillVersionSchema,
    "chat_records.json": ChatRecord,
    "uncertain_items.json": UncertainItemSchema,
    "question_targets.json": QuestionTargetSchema,
    "source_segments.json": SourceSegmentSchema,
    "extracted_segments.json": ExtractedSegmentSchema,
    "voice_generation_records.json": VoiceGenerationRecord,
}
VOICE_PATH_METADATA_FIELDS = (
    "voice_reference_original_file_path",
    "voice_reference_tts_file_path",
)


@dataclass(frozen=True)
class _LoadedBackup:
    manifest: BackupManifest
    documents: dict[str, Any]
    attachment_paths: set[str]


@dataclass(frozen=True)
class _PendingImport:
    archive_path: Path
    preview: BackupImportPreview
    expires_at: datetime


_PENDING_IMPORTS: dict[str, _PendingImport] = {}
_PENDING_LOCK = threading.RLock()


def _now() -> datetime:
    return datetime.now(UTC)


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record_count(payload: Any) -> int:
    return len(payload) if isinstance(payload, (list, dict)) else 0


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _configured_path(value: str) -> Path:
    configured = Path(value)
    return configured if configured.is_absolute() else _backend_root() / configured


def _allowed_attachment_roots() -> list[Path]:
    settings = get_settings()
    roots = [
        data_dir().resolve(),
        _configured_path(settings.voice_reference_dir).resolve(),
        _configured_path(settings.voice_output_dir).resolve(),
    ]
    return list(dict.fromkeys(roots))


def _is_allowed_attachment_path(path: Path) -> bool:
    resolved = path.resolve()
    return any(resolved.is_relative_to(root) for root in _allowed_attachment_roots())


def _safe_filename(value: str) -> str:
    name = Path(value).name
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip(".-")
    return safe[:160] or "attachment.bin"


def _is_safe_archive_path(value: str, *, prefix: str | None = None) -> bool:
    if not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and (prefix is None or value.startswith(prefix))


def _existing_document_names() -> set[str]:
    return set(list_json_store_files()) | {item["filename"] for item in list_sqlite_documents()}


def _read_selected_documents(*, scope: str, profile_id: UUID | None = None) -> dict[str, Any]:
    selected = FULL_DOCUMENTS if scope == "full" else PROFILE_DOCUMENTS
    available = _existing_document_names()
    documents: dict[str, Any] = {}
    for filename in selected:
        if filename not in available:
            continue
        payload = read_json_file(filename, None)
        if payload is None:
            continue
        if scope == "profile":
            if profile_id is None:
                raise ValueError("profile_id is required for a profile backup")
            if not isinstance(payload, list):
                continue
            if filename == "profiles.json":
                payload = [record for record in payload if record.get("id") == str(profile_id)]
            else:
                payload = [record for record in payload if record.get("profile_id") == str(profile_id)]
        documents[filename] = copy.deepcopy(payload)
    return documents


def _portable_attachment(
    *,
    archive: zipfile.ZipFile,
    source_path_value: object,
    kind: str,
    record_id: str,
    cache: dict[str, str],
    attachments: list[BackupArchiveAttachment],
    warnings: list[str],
) -> str | None:
    if not isinstance(source_path_value, str) or not source_path_value.strip():
        return None
    source_path = Path(source_path_value)
    try:
        resolved = source_path.resolve()
    except OSError:
        warnings.append(f"attachment_path_unavailable:{kind}:{record_id}")
        return None
    if not resolved.is_file() or not _is_allowed_attachment_path(resolved):
        warnings.append(f"attachment_not_exported:{kind}:{record_id}")
        return None
    cache_key = str(resolved)
    if cache_key in cache:
        return cache[cache_key]
    archive_path = f"{ATTACHMENT_PREFIX}{kind}/{record_id}/{_safe_filename(resolved.name)}"
    archive.write(resolved, archive_path)
    attachment = BackupArchiveAttachment(
        archive_path=archive_path,
        sha256=_sha256_file(resolved),
        size_bytes=resolved.stat().st_size,
        kind=kind,
    )
    attachments.append(attachment)
    cache[cache_key] = archive_path
    return archive_path


def _make_documents_portable(
    documents: dict[str, Any],
    archive: zipfile.ZipFile,
    warnings: list[str],
) -> list[BackupArchiveAttachment]:
    attachments: list[BackupArchiveAttachment] = []
    cache: dict[str, str] = {}
    raw_records = documents.get("raw_sources.json", [])
    if isinstance(raw_records, list):
        for record in raw_records:
            if not isinstance(record, dict):
                continue
            record_id = str(record.get("id") or uuid4())
            record["file_path"] = _portable_attachment(
                archive=archive,
                source_path_value=record.get("file_path"),
                kind="raw",
                record_id=record_id,
                cache=cache,
                attachments=attachments,
                warnings=warnings,
            )
            metadata = record.get("metadata")
            if not isinstance(metadata, dict):
                continue
            for key in VOICE_PATH_METADATA_FIELDS:
                if key in metadata:
                    metadata[key] = _portable_attachment(
                        archive=archive,
                        source_path_value=metadata.get(key),
                        kind="voice-reference",
                        record_id=record_id,
                        cache=cache,
                        attachments=attachments,
                        warnings=warnings,
                    )
    voice_records = documents.get("voice_generation_records.json", [])
    if isinstance(voice_records, list):
        for record in voice_records:
            if not isinstance(record, dict):
                continue
            record_id = str(record.get("id") or uuid4())
            record["output_file_path"] = _portable_attachment(
                archive=archive,
                source_path_value=record.get("output_file_path"),
                kind="voice-output",
                record_id=record_id,
                cache=cache,
                attachments=attachments,
                warnings=warnings,
            )
    return attachments


def create_backup_archive(*, profile_id: UUID | None = None) -> Path:
    scope = "profile" if profile_id is not None else "full"
    if profile_id is not None:
        get_profile(profile_id)
    documents = _read_selected_documents(scope=scope, profile_id=profile_id)
    profile_ids = [profile_id] if profile_id is not None else [
        UUID(str(record["id"]))
        for record in documents.get("profiles.json", [])
        if isinstance(record, dict) and record.get("id")
    ]
    export_root = data_dir() / "exports"
    export_root.mkdir(parents=True, exist_ok=True)
    archive_path = export_root / f"memweave-{scope}-{_now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}.zip"
    warnings: list[str] = []
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        attachments = _make_documents_portable(documents, archive, warnings)
        document_entries: list[BackupArchiveDocument] = []
        for filename, payload in sorted(documents.items()):
            content = _canonical_json_bytes(payload)
            archive_path_name = f"{DATA_PREFIX}{filename}"
            archive.writestr(archive_path_name, content)
            document_entries.append(
                BackupArchiveDocument(
                    filename=filename,
                    archive_path=archive_path_name,
                    sha256=_sha256_bytes(content),
                    record_count=_record_count(payload),
                )
            )
        manifest = BackupManifest(
            version=BACKUP_FORMAT_VERSION,
            scope=scope,  # type: ignore[arg-type]
            created_at=_now(),
            profile_ids=profile_ids,
            documents=document_entries,
            attachments=attachments,
            warnings=warnings,
        )
        archive.writestr(MANIFEST_PATH, _canonical_json_bytes(manifest.model_dump(mode="json")))
    return archive_path


def _zip_sha256(archive: zipfile.ZipFile, archive_path: str) -> str:
    digest = hashlib.sha256()
    with archive.open(archive_path) as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_document_payload(filename: str, payload: Any) -> None:
    validator = DOCUMENT_VALIDATORS.get(filename)
    if validator is None:
        if not isinstance(payload, (dict, list)):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Invalid backup document: {filename}")
        return
    if not isinstance(payload, list):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Backup document must be a list: {filename}")
    identifiers: set[str] = set()
    for record in payload:
        validated = validator.model_validate(record)
        record_id = str(validated.id)
        if record_id in identifiers:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Duplicate record id in backup: {filename}")
        identifiers.add(record_id)


def _load_backup_archive(archive_path: Path) -> _LoadedBackup:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            if len(names) > MAX_IMPORT_ENTRIES or len(names) != len(set(names)):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Backup archive has invalid entries")
            total_uncompressed = sum(info.file_size for info in archive.infolist())
            if total_uncompressed > MAX_IMPORT_UNCOMPRESSED_BYTES:
                raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Backup archive is too large")
            if any(not _is_safe_archive_path(name) for name in names) or MANIFEST_PATH not in names:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Backup archive contains unsafe paths")
            try:
                manifest_payload = json.loads(archive.read(MANIFEST_PATH).decode("utf-8"))
                manifest = BackupManifest.model_validate(manifest_payload)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Backup manifest is invalid") from exc
            documents: dict[str, Any] = {}
            for entry in manifest.documents:
                if entry.filename not in FULL_DOCUMENTS or not _is_safe_archive_path(entry.archive_path, prefix=DATA_PREFIX):
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Backup document is not allowed")
                if entry.archive_path not in names or _zip_sha256(archive, entry.archive_path) != entry.sha256:
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Backup document checksum failed: {entry.filename}")
                try:
                    payload = json.loads(archive.read(entry.archive_path).decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Backup document is invalid: {entry.filename}") from exc
                _validate_document_payload(entry.filename, payload)
                if _record_count(payload) != entry.record_count:
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Backup document count failed: {entry.filename}")
                documents[entry.filename] = payload
            attachment_paths: set[str] = set()
            for attachment in manifest.attachments:
                if not _is_safe_archive_path(attachment.archive_path, prefix=ATTACHMENT_PREFIX) or attachment.archive_path not in names:
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Backup attachment is invalid")
                info = archive.getinfo(attachment.archive_path)
                if info.file_size != attachment.size_bytes or _zip_sha256(archive, attachment.archive_path) != attachment.sha256:
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Backup attachment checksum failed")
                attachment_paths.add(attachment.archive_path)
            return _LoadedBackup(manifest=manifest, documents=documents, attachment_paths=attachment_paths)
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Backup archive is not a valid ZIP file") from exc


def _profile_previews(loaded: _LoadedBackup) -> tuple[list[BackupProfilePreview], list[UUID]]:
    local_ids = {
        str(record.get("id"))
        for record in read_json_file("profiles.json", [])
        if isinstance(record, dict) and record.get("id")
    }
    documents = loaded.documents
    profiles: list[BackupProfilePreview] = []
    conflicts: list[UUID] = []
    for record in documents.get("profiles.json", []):
        profile = ProfileSchema.model_validate(record)
        profile_id = str(profile.id)
        conflicts_with_local = profile_id in local_ids
        if conflicts_with_local:
            conflicts.append(profile.id)

        def count(filename: str) -> int:
            payload = documents.get(filename, [])
            return sum(1 for item in payload if isinstance(item, dict) and item.get("profile_id") == profile_id)

        profiles.append(
            BackupProfilePreview(
                id=profile.id,
                display_name=profile.display_name,
                relationship=profile.relationship,
                deleted=profile.deleted_at is not None,
                raw_source_count=count("raw_sources.json"),
                persona_item_count=count("persona_items.json"),
                chat_record_count=count("chat_records.json"),
                voice_generation_count=count("voice_generation_records.json"),
                conflicts_with_local=conflicts_with_local,
            )
        )
    return profiles, conflicts


def _build_preview(loaded: _LoadedBackup, import_token: str) -> BackupImportPreview:
    profiles, conflicts = _profile_previews(loaded)
    return BackupImportPreview(
        import_token=import_token,
        scope=loaded.manifest.scope,
        created_at=loaded.manifest.created_at,
        profiles=profiles,
        conflict_profile_ids=conflicts,
        document_count=len(loaded.manifest.documents),
        attachment_count=len(loaded.manifest.attachments),
        attachment_bytes=sum(item.size_bytes for item in loaded.manifest.attachments),
        warnings=loaded.manifest.warnings,
    )


def _pending_import_root() -> Path:
    path = data_dir() / "pending_imports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cleanup_expired_pending_imports() -> None:
    now = _now()
    for token, pending in list(_PENDING_IMPORTS.items()):
        if pending.expires_at >= now:
            continue
        pending.archive_path.unlink(missing_ok=True)
        _PENDING_IMPORTS.pop(token, None)


async def inspect_backup_upload(upload: UploadFile) -> BackupImportPreview:
    token = uuid4().hex
    destination = _pending_import_root() / f"{token}.zip"
    temporary = destination.with_suffix(".part")
    total = 0
    try:
        with temporary.open("wb") as stream:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_IMPORT_BYTES:
                    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Backup upload is too large")
                stream.write(chunk)
        temporary.replace(destination)
        loaded = _load_backup_archive(destination)
        preview = _build_preview(loaded, token)
        with _PENDING_LOCK:
            _cleanup_expired_pending_imports()
            _PENDING_IMPORTS[token] = _PendingImport(destination, preview, _now() + IMPORT_TOKEN_TTL)
        return preview
    except Exception:
        temporary.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


def _canonical_json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _current_list_document(filename: str) -> list[dict[str, Any]]:
    payload = read_json_file(filename, [])
    return payload if isinstance(payload, list) else []


def _rewrite_ids(value: Any, id_map: dict[str, str]) -> Any:
    if isinstance(value, str):
        return id_map.get(value, value)
    if isinstance(value, list):
        return [_rewrite_ids(item, id_map) for item in value]
    if isinstance(value, dict):
        return {key: _rewrite_ids(item, id_map) for key, item in value.items()}
    return value


def _prepare_profile_documents(loaded: _LoadedBackup, request: BackupImportRequest) -> tuple[dict[str, Any], dict[str, str], list[UUID]]:
    documents = copy.deepcopy(loaded.documents)
    incoming_profiles = documents.get("profiles.json", [])
    if not isinstance(incoming_profiles, list):
        incoming_profiles = []
    current_profiles = _current_list_document("profiles.json")
    current_profile_ids = {str(record.get("id")) for record in current_profiles if record.get("id")}
    id_map: dict[str, str] = {}
    incoming_profile_ids = {str(profile.id) for profile in _incoming_profiles(loaded)}
    conflict_profile_ids = incoming_profile_ids & current_profile_ids
    for record in incoming_profiles:
        old_id = str(record.get("id"))
        if old_id in conflict_profile_ids and request.profile_conflict_mode == "import_as_new":
            id_map[old_id] = str(uuid4())
    for filename in PROFILE_DOCUMENTS:
        if filename == "profiles.json":
            continue
        payload = documents.get(filename, [])
        if not isinstance(payload, list):
            continue
        occupied = {str(record.get("id")) for record in _current_list_document(filename) if record.get("id")}
        for record in payload:
            if not isinstance(record, dict) or not record.get("id"):
                continue
            record_id = str(record["id"])
            if record_id in occupied:
                id_map[record_id] = str(uuid4())
    for filename, payload in list(documents.items()):
        if filename not in PROFILE_DOCUMENTS or not isinstance(payload, list):
            continue
        documents[filename] = [_rewrite_ids(record, id_map) for record in payload if isinstance(record, dict)]
    prepared_profiles: list[dict[str, Any]] = []
    for original, transformed in zip(incoming_profiles, documents.get("profiles.json", []), strict=False):
        old_id = str(original.get("id"))
        if old_id in conflict_profile_ids and request.profile_conflict_mode == "merge":
            continue
        prepared_profiles.append(transformed)
    documents["profiles.json"] = prepared_profiles
    return documents, id_map, [UUID(str(record["id"])) for record in prepared_profiles]


def _incoming_profiles(loaded: _LoadedBackup) -> list[ProfileSchema]:
    return [ProfileSchema.model_validate(record) for record in loaded.documents.get("profiles.json", [])]


def _copy_archive_entry(archive: zipfile.ZipFile, archive_path: str, destination: Path, created: list[Path]) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    target = destination
    if target.exists():
        target = target.with_name(f"{target.stem}-{uuid4().hex[:8]}{target.suffix}")
    partial = target.with_name(f".{target.name}.part")
    with archive.open(archive_path) as source, partial.open("wb") as output:
        shutil.copyfileobj(source, output, length=1024 * 1024)
    partial.replace(target)
    created.append(target)
    return str(target)


def _attachment_destination(*, archive_path: str, profile_id: str | None, category: str) -> Path:
    suffix = _safe_filename(PurePosixPath(archive_path).name)
    identifier = profile_id or "unassigned"
    if category == "voice-output":
        root = _configured_path(get_settings().voice_output_dir)
    elif category == "voice-reference":
        root = _configured_path(get_settings().voice_reference_dir)
    else:
        root = data_dir() / "uploads"
    return root / "imported" / identifier / f"{uuid4().hex[:8]}-{suffix}"


def _restore_attachment_path(
    *,
    archive: zipfile.ZipFile,
    archive_path: object,
    attachment_paths: set[str],
    profile_id: str | None,
    category: str,
    created: list[Path],
) -> str | None:
    if not isinstance(archive_path, str) or not archive_path:
        return None
    if not archive_path.startswith(ATTACHMENT_PREFIX):
        return None
    if archive_path not in attachment_paths:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Backup record refers to an undeclared attachment")
    destination = _attachment_destination(archive_path=archive_path, profile_id=profile_id, category=category)
    return _copy_archive_entry(archive, archive_path, destination, created)


def _restore_document_attachments(loaded: _LoadedBackup, documents: dict[str, Any], archive: zipfile.ZipFile) -> int:
    created: list[Path] = []
    try:
        raw_records = documents.get("raw_sources.json", [])
        if isinstance(raw_records, list):
            for record in raw_records:
                if not isinstance(record, dict):
                    continue
                profile_id = record.get("profile_id") if isinstance(record.get("profile_id"), str) else None
                metadata = record.get("metadata")
                is_voice_reference = isinstance(metadata, dict) and bool(metadata.get("voice_reference"))
                record["file_path"] = _restore_attachment_path(
                    archive=archive,
                    archive_path=record.get("file_path"),
                    attachment_paths=loaded.attachment_paths,
                    profile_id=profile_id,
                    category="voice-reference" if is_voice_reference else "raw",
                    created=created,
                )
                if isinstance(metadata, dict):
                    for key in VOICE_PATH_METADATA_FIELDS:
                        if key in metadata:
                            metadata[key] = _restore_attachment_path(
                                archive=archive,
                                archive_path=metadata.get(key),
                                attachment_paths=loaded.attachment_paths,
                                profile_id=profile_id,
                                category="voice-reference",
                                created=created,
                            )
        voice_records = documents.get("voice_generation_records.json", [])
        if isinstance(voice_records, list):
            for record in voice_records:
                if not isinstance(record, dict):
                    continue
                profile_id = record.get("profile_id") if isinstance(record.get("profile_id"), str) else None
                record["output_file_path"] = _restore_attachment_path(
                    archive=archive,
                    archive_path=record.get("output_file_path"),
                    attachment_paths=loaded.attachment_paths,
                    profile_id=profile_id,
                    category="voice-output",
                    created=created,
                )
        return len(created)
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise


def _merge_global_document(current: Any, incoming: Any) -> Any:
    if current in (None, [], {}):
        return incoming
    if isinstance(current, list) and isinstance(incoming, list):
        seen = {_canonical_json_text(item) for item in current}
        return [*current, *(item for item in incoming if _canonical_json_text(item) not in seen)]
    if isinstance(current, dict) and isinstance(incoming, dict):
        return {**incoming, **current}
    return current


def import_pending_backup(request: BackupImportRequest) -> BackupImportResponse:
    with _PENDING_LOCK:
        _cleanup_expired_pending_imports()
        pending = _PENDING_IMPORTS.get(request.import_token)
        if pending is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup import preview has expired or was not found")
    archive_path = pending.archive_path
    try:
        loaded = _load_backup_archive(archive_path)
        preview = _build_preview(loaded, request.import_token)
        documents, id_map, imported_profile_ids = _prepare_profile_documents(loaded, request)
        imported_counts: dict[str, int] = {}
        skipped_globals: list[str] = []
        profile_writes: dict[str, list[dict[str, Any]]] = {}
        for filename in PROFILE_DOCUMENTS:
            incoming = documents.get(filename)
            if not isinstance(incoming, list):
                continue
            current = _current_list_document(filename)
            profile_writes[filename] = [*current, *incoming]
            imported_counts[filename] = len(incoming)
        global_writes: dict[str, Any] = {}
        if loaded.manifest.scope == "full":
            for filename in GLOBAL_SAFE_DOCUMENTS:
                if filename not in documents:
                    continue
                current = read_json_file(filename, None)
                if request.global_data_mode == "keep_existing" and current not in (None, [], {}):
                    skipped_globals.append(filename)
                    continue
                global_writes[filename] = _merge_global_document(current, documents[filename])
                imported_counts[filename] = _record_count(documents[filename])
        with zipfile.ZipFile(archive_path) as archive:
            attachment_count = _restore_document_attachments(loaded, documents, archive)
        for filename, payload in profile_writes.items():
            write_json_file(filename, payload)
        for filename, payload in global_writes.items():
            write_json_file(filename, payload)
        preview_profile_ids = {str(item.id) for item in preview.profiles}
        return BackupImportResponse(
            scope=loaded.manifest.scope,
            imported_profile_ids=imported_profile_ids,
            remapped_profile_ids={old: UUID(new) for old, new in id_map.items() if old in preview_profile_ids},
            imported_document_counts=imported_counts,
            imported_attachment_count=attachment_count,
            skipped_global_documents=skipped_globals,
            warnings=loaded.manifest.warnings,
        )
    finally:
        archive_path.unlink(missing_ok=True)
        with _PENDING_LOCK:
            _PENDING_IMPORTS.pop(request.import_token, None)
