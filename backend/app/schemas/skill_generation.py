from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.persona_item import LibraryGroup


SkillEvidenceType = Literal[
    "fact",
    "quote",
    "style_marker",
    "emotion_response",
    "relationship_pattern",
    "decision_pattern",
    "boundary_rule",
    "voice_feature",
    "user_interpretation",
    "model_inference",
]
SkillBucket = Literal["core", "supporting", "caution", "audit", "excluded"]


class SkillGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: UUID
    include_audit_units: bool = False


class SkillUsageMatrix(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_retrieve: bool = False
    can_generate_style: bool = False
    can_state_as_fact: bool = False
    can_quote: bool = False
    can_simulate: bool = False
    needs_caution: bool = False
    needs_question: bool = False
    audit_only: bool = False


class SkillEvidenceUnit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_id: str = Field(min_length=1, max_length=220)
    profile_id: UUID
    source_id: UUID | None = None
    persona_item_id: UUID
    library_group: LibraryGroup
    library_key: str = Field(min_length=1, max_length=80)
    claim_text: str = Field(min_length=1, max_length=800)
    evidence_quote: str = Field(default="", max_length=1000)
    evidence_type: SkillEvidenceType
    context_signature: dict[str, str] = Field(default_factory=dict)
    source_role: str = Field(default="unknown", max_length=120)
    subject_scope: str = Field(default="unknown", max_length=120)
    time_range: str | None = Field(default=None, max_length=160)
    source_deleted: bool = False
    user_policy: str = Field(default="", max_length=120)
    risk: str = Field(default="none", max_length=80)
    status: str = Field(default="candidate", max_length=80)
    confidence_parts: dict[str, float] = Field(default_factory=dict)
    ranking_score: float = Field(ge=0, le=100)
    bucket: SkillBucket
    cap_rule: str = Field(default="none", max_length=120)
    cap_reason: str = Field(default="", max_length=500)
    usage: SkillUsageMatrix
    score_reason: list[str] = Field(default_factory=list, max_length=24)


class SkillLibrarySection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    library_group: LibraryGroup
    core: list[SkillEvidenceUnit] = Field(default_factory=list)
    supporting: list[SkillEvidenceUnit] = Field(default_factory=list)
    caution: list[SkillEvidenceUnit] = Field(default_factory=list)


class SkillAuditEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_type: str = Field(min_length=1, max_length=80)
    subject_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=160)
    detail: str = Field(default="", max_length=800)
    source_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SkillQuestionBacklogItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_target_id: UUID
    source_id: UUID | None = None
    target_group: LibraryGroup
    target_library_key: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=80)
    question: str = Field(min_length=1, max_length=500)
    priority: int = Field(ge=0, le=100)
    expected_evidence_type: str = Field(default="", max_length=120)


class SkillGenerationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: UUID
    generated_at: datetime
    version: str = "skill-v2-minimal"
    skill_markdown: str = Field(default="", max_length=120_000)
    libraries: dict[str, SkillLibrarySection] = Field(default_factory=dict)
    evidence_units: list[SkillEvidenceUnit] = Field(default_factory=list)
    caution_report: list[SkillEvidenceUnit] = Field(default_factory=list)
    question_backlog: list[SkillQuestionBacklogItem] = Field(default_factory=list)
    audit_report: list[SkillAuditEntry] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
