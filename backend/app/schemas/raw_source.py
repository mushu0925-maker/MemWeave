from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.memory import SourceType


class RawSourceSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    profile_id: UUID | None = None
    source_type: SourceType
    original_text: str = Field(default="", max_length=120_000)
    extracted_text: str = Field(default="", max_length=120_000)
    file_path: str | None = Field(default=None, max_length=1000)
    file_name: str | None = Field(default=None, max_length=260)
    mime_type: str | None = Field(default=None, max_length=160)
    content_hash: str = Field(min_length=1, max_length=128)
    pii_masked_text: str = Field(default="", max_length=120_000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    deleted_at: datetime | None = None


class RawSourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: UUID | None = None
    source_type: SourceType
    original_text: str = Field(default="", max_length=120_000)
    extracted_text: str = Field(default="", max_length=120_000)
    file_path: str | None = Field(default=None, max_length=1000)
    file_name: str | None = Field(default=None, max_length=260)
    mime_type: str | None = Field(default=None, max_length=160)
    pii_masked_text: str = Field(default="", max_length=120_000)
    metadata: dict[str, Any] = Field(default_factory=dict)
