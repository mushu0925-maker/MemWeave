from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StorageStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_backend: str
    data_dir: str
    sqlite_path: str
    sqlite_exists: bool
    json_file_count: int
    sqlite_document_count: int
    sqlite_documents: list[dict[str, Any]] = Field(default_factory=list)


class StorageMigrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filenames: list[str] | None = Field(default=None, max_length=100)
    overwrite: bool = False


class StorageMigrationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sqlite_path: str
    overwrite: bool
    requested_count: int
    migrated_count: int
    skipped_count: int
    migrated: list[dict[str, Any]] = Field(default_factory=list)
    skipped: list[dict[str, str]] = Field(default_factory=list)


class StorageVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filenames: list[str] | None = Field(default=None, max_length=100)


class StorageVerificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sqlite_path: str
    checked_count: int
    all_match: bool
    results: list[dict[str, Any]] = Field(default_factory=list)
