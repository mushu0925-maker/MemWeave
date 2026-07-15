from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.skill_generation import SkillGenerationResponse


class SkillVersionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    profile_id: UUID
    title: str = Field(default="", max_length=160)
    notes: str = Field(default="", max_length=1000)
    source_generation_version: str = Field(default="", max_length=120)
    skill_markdown: str = Field(default="", max_length=120_000)
    skill_json: SkillGenerationResponse
    evidence_unit_count: int = 0
    audit_count: int = 0
    question_backlog_count: int = 0
    created_at: datetime


class SkillVersionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=1000)
    skill: SkillGenerationResponse


class SkillVersionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    versions: list[SkillVersionSchema] = Field(default_factory=list)
