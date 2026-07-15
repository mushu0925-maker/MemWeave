from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.feature_policy import FeaturePolicy


QualityCheckStatus = Literal["pass", "fail", "blocked", "skipped"]
QualityOverallStatus = Literal["pass", "fail", "blocked"]


class QualityValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: UUID
    sample_limit: int = Field(default=30, ge=1, le=200)
    include_audit_units: bool = True
    updated_by: str = Field(default="backend-quality-validation", max_length=120)


class QualityCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=160)
    status: QualityCheckStatus
    expected: str = Field(default="", max_length=1000)
    actual: str = Field(default="", max_length=1000)
    evidence: dict[str, Any] = Field(default_factory=dict)
    action_hint: str = Field(default="", max_length=1000)


class QualityValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_key: str
    generated_at: datetime
    feature_policy: FeaturePolicy
    algorithm_key: str
    strictness: str
    profile_id: UUID
    overall_status: QualityOverallStatus
    checks: list[QualityCheckResult] = Field(default_factory=list)
    score: float | None = None
    summary: dict[str, int] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
