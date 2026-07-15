from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SourceType = Literal[
    "text",
    "file",
    "interview",
    "extension",
    "image",
    "audio",
    "book",
    "manual",
    "manual_override",
    "chat",
]


class PersonaAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_kind: str = Field(min_length=1, max_length=120)
    data_role: str = Field(min_length=1, max_length=120)
    detected_modalities: list[str] = Field(default_factory=list, max_length=12)
    evidence_types: list[str] = Field(default_factory=list, max_length=16)
    emotional_tone: list[str] = Field(default_factory=list, max_length=16)
    speech_markers: list[str] = Field(default_factory=list, max_length=24)
    catchphrases: list[str] = Field(default_factory=list, max_length=24)
    care_cases: list[str] = Field(default_factory=list, max_length=24)
    memory_facts: list[str] = Field(default_factory=list, max_length=24)
    boundaries: list[str] = Field(default_factory=list, max_length=16)
    confidence: float = Field(ge=0, le=1)
    provider: str = Field(min_length=1, max_length=80)
    model_call_status: str = Field(default="not_recorded", max_length=40)
    model_call_reason: str = Field(default="", max_length=500)
    model_name: str | None = Field(default=None, max_length=120)
    notes: list[str] = Field(default_factory=list, max_length=16)
