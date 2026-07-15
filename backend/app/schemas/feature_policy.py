from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


FeatureStrictness = Literal["relaxed", "normal", "strict", "audit_only"]


class FeatureWriteRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_source: bool = False
    persona_item: bool = False
    uncertain_item: bool = False
    question_target: bool = False
    chat_record: bool = False
    skill_version: bool = False
    monitoring_event: bool = True


class FeaturePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=1000)
    enabled: bool = True
    algorithm_key: str = Field(min_length=1, max_length=120)
    strictness: FeatureStrictness = "normal"
    write_rules: FeatureWriteRules = Field(default_factory=FeatureWriteRules)
    thresholds: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    updated_at: datetime
    updated_by: str = Field(default="system", max_length=120)


class FeaturePolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    algorithm_key: str | None = Field(default=None, min_length=1, max_length=120)
    strictness: FeatureStrictness | None = None
    write_rules: FeatureWriteRules | None = None
    thresholds: dict[str, float] | None = None
    metadata: dict[str, str | int | float | bool | None] | None = None
    updated_by: str | None = Field(default=None, max_length=120)
