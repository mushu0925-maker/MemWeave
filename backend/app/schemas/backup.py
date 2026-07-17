from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


BackupScope = Literal["full", "profile"]
ProfileConflictMode = Literal["merge", "import_as_new"]
GlobalDataMode = Literal["keep_existing", "merge"]


class BackupArchiveDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=160)
    archive_path: str = Field(min_length=1, max_length=260)
    sha256: str = Field(min_length=64, max_length=64)
    record_count: int = Field(ge=0)


class BackupArchiveAttachment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    archive_path: str = Field(min_length=1, max_length=500)
    sha256: str = Field(min_length=64, max_length=64)
    size_bytes: int = Field(ge=0)
    kind: str = Field(min_length=1, max_length=80)


class BackupManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["memweave-backup"] = "memweave-backup"
    version: int = Field(ge=1, le=1)
    scope: BackupScope
    created_at: datetime
    profile_ids: list[UUID] = Field(default_factory=list, max_length=10_000)
    documents: list[BackupArchiveDocument] = Field(default_factory=list, max_length=64)
    attachments: list[BackupArchiveAttachment] = Field(default_factory=list, max_length=20_000)
    warnings: list[str] = Field(default_factory=list, max_length=500)


class BackupProfilePreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    display_name: str = Field(min_length=1, max_length=120)
    relationship: str = Field(min_length=1, max_length=40)
    deleted: bool = False
    raw_source_count: int = Field(ge=0)
    persona_item_count: int = Field(ge=0)
    chat_record_count: int = Field(ge=0)
    voice_generation_count: int = Field(ge=0)
    conflicts_with_local: bool = False


class BackupImportPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    import_token: str = Field(min_length=16, max_length=128)
    scope: BackupScope
    created_at: datetime
    profiles: list[BackupProfilePreview] = Field(default_factory=list)
    conflict_profile_ids: list[UUID] = Field(default_factory=list)
    document_count: int = Field(ge=0)
    attachment_count: int = Field(ge=0)
    attachment_bytes: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class BackupImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    import_token: str = Field(min_length=16, max_length=128)
    profile_conflict_mode: ProfileConflictMode
    global_data_mode: GlobalDataMode = "keep_existing"


class BackupImportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: BackupScope
    imported_profile_ids: list[UUID] = Field(default_factory=list)
    remapped_profile_ids: dict[str, UUID] = Field(default_factory=dict)
    imported_document_counts: dict[str, int] = Field(default_factory=dict)
    imported_attachment_count: int = Field(ge=0)
    skipped_global_documents: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
