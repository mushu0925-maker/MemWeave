from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


LibraryGroup = Literal["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M"]
PersonaItemStatus = Literal["active", "candidate", "hidden", "forgotten", "rejected_until_confirmed", "deleted"]


class PersonaItemSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    profile_id: UUID
    source_id: UUID | None = None
    library_group: LibraryGroup
    library_key: str = Field(min_length=1, max_length=80)
    signal: str = Field(min_length=1, max_length=500)
    evidence_quote: str = Field(default="", max_length=1000)
    evidence_time_range: str | None = Field(default=None, max_length=160)
    confidence: float = Field(ge=0, le=1)
    stability: str = Field(default="unknown", max_length=80)
    subject_scope: str = Field(default="unknown", max_length=80)
    write_target: str = Field(default="rejected_until_confirmed", max_length=80)
    risk: str = Field(default="none", max_length=80)
    prompt_snippet: str = Field(default="", max_length=600)
    extraction_method: str = Field(default="unknown", max_length=120)
    model_name: str | None = Field(default=None, max_length=160)
    status: PersonaItemStatus = "candidate"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class PersonaItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: UUID
    source_id: UUID | None = None
    library_group: LibraryGroup
    library_key: str = Field(min_length=1, max_length=80)
    signal: str = Field(min_length=1, max_length=500)
    evidence_quote: str = Field(default="", max_length=1000)
    evidence_time_range: str | None = Field(default=None, max_length=160)
    confidence: float = Field(ge=0, le=1)
    stability: str = Field(default="unknown", max_length=80)
    subject_scope: str = Field(default="unknown", max_length=80)
    write_target: str = Field(default="rejected_until_confirmed", max_length=80)
    risk: str = Field(default="none", max_length=80)
    prompt_snippet: str = Field(default="", max_length=600)
    extraction_method: str = Field(default="unknown", max_length=120)
    model_name: str | None = Field(default=None, max_length=160)
    status: PersonaItemStatus = "candidate"
    metadata: dict[str, Any] = Field(default_factory=dict)
