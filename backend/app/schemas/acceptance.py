from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.feature_policy import FeaturePolicy


AcceptanceCheckStatus = Literal["pass", "warning", "fail", "blocked", "skipped"]
AcceptanceOverallStatus = Literal["pass", "warning", "fail", "blocked"]


class AcceptanceRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: UUID | None = None
    create_isolated_profile: bool = True
    use_model_for_chat: bool = False
    raw_content: str | None = Field(default=None, max_length=20_000)
    updated_by: str = Field(default="backend-acceptance", max_length=120)


class AcceptanceCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=160)
    status: AcceptanceCheckStatus
    module: str = Field(default="", max_length=120)
    record_ids: list[str] = Field(default_factory=list, max_length=200)
    reason: str = Field(default="", max_length=1000)
    expected: str = Field(default="", max_length=1000)
    actual: str = Field(default="", max_length=1000)
    evidence: dict[str, Any] = Field(default_factory=dict)
    action_hint: str = Field(default="", max_length=1000)
    suggested_action: str = Field(default="", max_length=1000)


class AcceptanceRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    started_at: datetime
    finished_at: datetime
    feature_policy: FeaturePolicy
    overall_status: AcceptanceOverallStatus
    profile_id: UUID | None = None
    created_profile_id: UUID | None = None
    algorithm_key: str
    strictness: str
    checks: list[AcceptanceCheckResult] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)
