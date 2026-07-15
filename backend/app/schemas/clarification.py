from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.persona_classification import PersonaLibraryClassificationResult
from app.schemas.persona_item import LibraryGroup
from app.schemas.persona_item import PersonaItemSchema
from app.schemas.raw_source import RawSourceSchema


ConfirmationOption = Literal["keep", "correct", "downrank", "hide", "forget"]
UncertainRiskType = Literal[
    "unclear",
    "low_confidence",
    "conflict",
    "negative_memory",
    "sensitive",
    "unsupported_fact",
]
UncertainItemStatus = Literal["open", "resolved", "forgotten", "hidden"]
QuestionTargetReason = Literal["missing", "low_confidence", "conflict", "needs_example", "needs_boundary"]
QuestionTargetStatus = Literal["open", "answered", "dismissed", "resolved"]


class UncertainItemSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    profile_id: UUID
    source_id: UUID | None = None
    persona_item_id: UUID | None = None
    library_group: LibraryGroup
    library_key: str = Field(min_length=1, max_length=80)
    claim: str = Field(min_length=1, max_length=500)
    why_uncertain: str = Field(min_length=1, max_length=500)
    risk_type: UncertainRiskType
    suggested_question: str = Field(min_length=1, max_length=500)
    confirmation_options: list[ConfirmationOption] = Field(default_factory=list, max_length=5)
    confidence: float = Field(ge=0, le=1)
    status: UncertainItemStatus = "open"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class UncertainItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: UUID
    source_id: UUID | None = None
    persona_item_id: UUID | None = None
    library_group: LibraryGroup
    library_key: str = Field(min_length=1, max_length=80)
    claim: str = Field(min_length=1, max_length=500)
    why_uncertain: str = Field(min_length=1, max_length=500)
    risk_type: UncertainRiskType
    suggested_question: str = Field(min_length=1, max_length=500)
    confirmation_options: list[ConfirmationOption] = Field(default_factory=list, max_length=5)
    confidence: float = Field(default=0.35, ge=0, le=1)
    status: UncertainItemStatus = "open"
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuestionTargetSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    profile_id: UUID
    source_id: UUID | None = None
    uncertain_item_id: UUID | None = None
    target_group: LibraryGroup
    target_library_key: str = Field(min_length=1, max_length=80)
    reason: QuestionTargetReason
    question: str = Field(min_length=1, max_length=500)
    example_answer: str = Field(default="", max_length=500)
    priority: int = Field(default=50, ge=0, le=100)
    expected_evidence_type: str = Field(default="", max_length=120)
    status: QuestionTargetStatus = "open"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class QuestionTargetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: UUID
    source_id: UUID | None = None
    uncertain_item_id: UUID | None = None
    target_group: LibraryGroup
    target_library_key: str = Field(min_length=1, max_length=80)
    reason: QuestionTargetReason
    question: str = Field(min_length=1, max_length=500)
    example_answer: str = Field(default="", max_length=500)
    priority: int = Field(default=50, ge=0, le=100)
    expected_evidence_type: str = Field(default="", max_length=120)
    status: QuestionTargetStatus = "open"
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuestionAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer_text: str = Field(min_length=1, max_length=120_000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuestionAnswerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_source: RawSourceSchema
    persona_items: list[PersonaItemSchema] = Field(default_factory=list)
    question_target: QuestionTargetSchema
    uncertain_item: UncertainItemSchema | None = None
    persona_library_classification: PersonaLibraryClassificationResult | None = None
    classification_succeeded: bool
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class UncertainItemActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: ConfirmationOption
    corrected_claim: str | None = Field(default=None, max_length=1_000)
    note: str | None = Field(default=None, max_length=1_000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UncertainItemActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uncertain_item: UncertainItemSchema
    question_targets: list[QuestionTargetSchema] = Field(default_factory=list)
    action: ConfirmationOption
    raw_source: RawSourceSchema | None = None
    persona_items: list[PersonaItemSchema] = Field(default_factory=list)
    persona_library_classification: PersonaLibraryClassificationResult | None = None
    classification_succeeded: bool = False
    diagnostics: dict[str, Any] = Field(default_factory=dict)
