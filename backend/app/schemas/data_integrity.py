from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


IntegritySeverity = Literal["info", "warning", "runtime_blocker", "derived_orphan"]


class DataIntegrityIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(min_length=1, max_length=120)
    severity: IntegritySeverity
    record_type: str = Field(min_length=1, max_length=80)
    record_id: str = Field(default="", max_length=120)
    profile_id: str | None = Field(default=None, max_length=120)
    source_id: str | None = Field(default=None, max_length=120)
    action: str = Field(default="", max_length=240)
    details: dict[str, Any] = Field(default_factory=dict)


class DataIntegrityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    summary: dict[str, int] = Field(default_factory=dict)
    issues: list[DataIntegrityIssue] = Field(default_factory=list)


class DataIntegrityRepairResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_before: DataIntegrityReport
    report_after: DataIntegrityReport
    repaired_counts: dict[str, int] = Field(default_factory=dict)
    diff: dict[str, int] = Field(default_factory=dict)
    actions: list[dict[str, Any]] = Field(default_factory=list)
