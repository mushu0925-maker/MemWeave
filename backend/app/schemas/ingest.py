from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.memory import SourceType
from app.schemas.persona_classification import PersonaLibraryClassificationResult
from app.schemas.persona_item import PersonaItemSchema
from app.schemas.raw_source import RawSourceSchema


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: SourceType
    raw_content: str = Field(min_length=1, max_length=100_000)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    profile_id: UUID | None = None


class IngestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_source: RawSourceSchema
    persona_items: list[PersonaItemSchema] = Field(default_factory=list)
    sanitized_content: str
    pii_summary: dict[str, int]
    routing_key: str
    persona_library_classification: PersonaLibraryClassificationResult | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)
