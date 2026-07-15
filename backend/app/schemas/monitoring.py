from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


MonitoringMetricStatus = Literal[
    "ok",
    "disabled",
    "insufficient_data",
    "insufficient_ground_truth",
    "blocked",
]
MonitoringHealthLevel = Literal["ok", "warning", "blocker", "audit", "disabled", "unknown"]
MonitoringAttribution = Literal[
    "not_applicable",
    "history_data_issue",
    "missing_runtime_event",
    "real_runtime_bug",
    "configuration_issue",
    "mixed",
]
MonitoringStrictness = Literal["relaxed", "normal", "strict", "audit_only"]
MonitoringFailPolicy = Literal["fail_open", "warn", "fail_closed"]
MonitoringDirection = Literal["higher_is_better", "lower_is_better"]
MonitoringSampleQuality = Literal["sufficient", "insufficient_data", "insufficient_ground_truth", "disabled", "blocked"]
MonitoringEventType = Literal[
    "acceptance",
    "distillation",
    "confirmation",
    "skill_generation",
    "chat_skill_usage",
    "mcp_tool_call",
    "voice_generation",
]
MonitoringEventStatus = Literal["success", "failed", "skipped", "blocked", "local"]


class MonitoringMetricConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=1000)
    enabled: bool = True
    algorithm_key: str = Field(min_length=1, max_length=120)
    strictness: MonitoringStrictness = "normal"
    direction: MonitoringDirection = "higher_is_better"
    thresholds: dict[str, float] = Field(default_factory=dict)
    window_days: int = Field(default=30, ge=1, le=3650)
    sample_limit: int = Field(default=50, ge=1, le=500)
    fail_policy: MonitoringFailPolicy = "warn"
    updated_at: datetime
    updated_by: str = Field(default="system", max_length=120)


class MonitoringMetricConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    algorithm_key: str | None = Field(default=None, min_length=1, max_length=120)
    strictness: MonitoringStrictness | None = None
    thresholds: dict[str, float] | None = None
    window_days: int | None = Field(default=None, ge=1, le=3650)
    sample_limit: int | None = Field(default=None, ge=1, le=500)
    fail_policy: MonitoringFailPolicy | None = None
    updated_by: str | None = Field(default=None, max_length=120)


class MonitoringMetricResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_key: str
    name: str
    numerator: int
    denominator: int
    rate: float | None = None
    status: MonitoringMetricStatus
    level: MonitoringHealthLevel = "unknown"
    calculation_note: str = ""
    sample_ids: list[str] = Field(default_factory=list)
    problem_sample_ids: list[str] = Field(default_factory=list)
    missing_data_reason: str = ""
    sample_quality: MonitoringSampleQuality = "sufficient"
    strict_acceptance: bool = False
    attribution: MonitoringAttribution = "not_applicable"
    attribution_note: str = ""
    action_hint: str = ""
    algorithm_key: str
    strictness: MonitoringStrictness
    thresholds: dict[str, float] = Field(default_factory=dict)
    window_days: int
    sample_limit: int
    updated_at: datetime


class MonitoringReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    profile_id: UUID | None = None
    overall_level: MonitoringHealthLevel
    summary: dict[str, int] = Field(default_factory=dict)
    metrics: list[MonitoringMetricResult] = Field(default_factory=list)


class MonitoringEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    event_type: MonitoringEventType
    status: MonitoringEventStatus
    profile_id: UUID | None = None
    raw_source_id: UUID | None = None
    chat_record_id: UUID | None = None
    skill_version_id: UUID | None = None
    subject_id: str = Field(default="", max_length=160)
    workflow: str = Field(default="", max_length=160)
    provider: str = Field(default="", max_length=120)
    model_name: str | None = Field(default=None, max_length=160)
    input_summary: str = Field(default="", max_length=1000)
    output_summary: str = Field(default="", max_length=1000)
    error: str = Field(default="", max_length=1000)
    used_persona_item_ids: list[UUID] = Field(default_factory=list, max_length=500)
    used_raw_source_ids: list[UUID] = Field(default_factory=list, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class MonitoringEventListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[MonitoringEvent] = Field(default_factory=list)
