from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.schemas.backup import BackupImportPreview, BackupImportRequest, BackupImportResponse
from app.services.backup_service import create_backup_archive, import_pending_backup, inspect_backup_upload

router = APIRouter(prefix="/backups", tags=["backups"])


def _remove_export(path: Path) -> None:
    path.unlink(missing_ok=True)


def _export_response(archive_path: Path) -> FileResponse:
    return FileResponse(
        archive_path,
        media_type="application/zip",
        filename=archive_path.name,
        background=BackgroundTask(_remove_export, archive_path),
    )


@router.get("/export")
def export_full_backup() -> FileResponse:
    return _export_response(create_backup_archive())


@router.get("/profiles/{profile_id}/export")
def export_profile_backup(profile_id: UUID) -> FileResponse:
    return _export_response(create_backup_archive(profile_id=profile_id))


@router.post("/inspect", response_model=BackupImportPreview)
async def inspect_backup(upload: UploadFile = File(...)) -> BackupImportPreview:
    return await inspect_backup_upload(upload)


@router.post("/import", response_model=BackupImportResponse)
def import_backup(payload: BackupImportRequest) -> BackupImportResponse:
    return import_pending_backup(payload)
