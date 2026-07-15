from __future__ import annotations

from fastapi import APIRouter

from app.schemas.storage import (
    StorageMigrationRequest,
    StorageMigrationResponse,
    StorageStatusResponse,
    StorageVerificationRequest,
    StorageVerificationResponse,
)
from app.services.local_database import get_storage_status, migrate_json_to_sqlite, verify_sqlite_against_json

router = APIRouter(prefix="/storage", tags=["storage"])


@router.get("/status", response_model=StorageStatusResponse)
def read_storage_status() -> StorageStatusResponse:
    return StorageStatusResponse.model_validate(get_storage_status())


@router.post("/sqlite/migrate", response_model=StorageMigrationResponse)
def migrate_sqlite_documents(payload: StorageMigrationRequest) -> StorageMigrationResponse:
    return StorageMigrationResponse.model_validate(
        migrate_json_to_sqlite(filenames=payload.filenames, overwrite=payload.overwrite)
    )


@router.post("/verify", response_model=StorageVerificationResponse)
def verify_storage_documents(payload: StorageVerificationRequest | None = None) -> StorageVerificationResponse:
    request = payload or StorageVerificationRequest()
    return StorageVerificationResponse.model_validate(verify_sqlite_against_json(filenames=request.filenames))
