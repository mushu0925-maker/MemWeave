from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.feature_policy import FeaturePolicy


EventMemoryField = Literal[
    "time",
    "place",
    "people",
    "event",
    "user_feeling",
    "evidence_source",
]


class MemoryCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: UUID
    text: str = Field(min_length=1, max_length=20_000)
    source_id: UUID | None = None
    dry_run: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryCompletionGap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: EventMemoryField
    severity: Literal["low", "medium", "high"] = "medium"
    reason: str = Field(min_length=1, max_length=500)
    question: str = Field(min_length=1, max_length=500)
    expected_evidence_type: str = Field(default="", max_length=120)


class MemoryCompletionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created_at: datetime
    feature_policy: FeaturePolicy
    algorithm_key: str
    strictness: str
    profile_id: UUID
    source_id: UUID | None = None
    dry_run: bool = False
    gaps: list[MemoryCompletionGap] = Field(default_factory=list)
    uncertain_item_ids: list[UUID] = Field(default_factory=list)
    question_target_ids: list[UUID] = Field(default_factory=list)
    monitoring_event_id: UUID | None = None
    write_decisions: dict[str, bool] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
