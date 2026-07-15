from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


PluginStrictness = Literal["relaxed", "normal", "strict", "audit_only"]


class DistillationPluginWriteRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persona_item: bool = True
    uncertain_item: bool = True
    question_target: bool = True
    monitoring_event: bool = True


class DistillationPluginTendency(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conservative_mode: bool = True
    target_profile_only: bool = True
    max_candidate_libraries: int = Field(default=28, ge=8, le=60)
    confidence_cap_single_source: float = Field(default=0.68, ge=0, le=1)
    prompt_appendix: str = Field(default="", max_length=2000)
    focus_weights: dict[str, float] = Field(default_factory=dict)


class DistillationPluginDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plugin_key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=160)
    version: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=1000)
    algorithm_key: str = Field(min_length=1, max_length=120)
    supported_library_plugin_keys: list[str] = Field(default_factory=list)
    default_tendency: DistillationPluginTendency = Field(default_factory=DistillationPluginTendency)
    default_write_rules: DistillationPluginWriteRules = Field(default_factory=DistillationPluginWriteRules)


class DistillationPluginPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_plugin_key: str = Field(min_length=1, max_length=120)
    enabled: bool = True
    strictness: PluginStrictness = "strict"
    tendency: DistillationPluginTendency = Field(default_factory=DistillationPluginTendency)
    write_rules: DistillationPluginWriteRules = Field(default_factory=DistillationPluginWriteRules)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    updated_at: datetime
    updated_by: str = Field(default="system", max_length=120)


class DistillationPluginPolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_plugin_key: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    strictness: PluginStrictness | None = None
    tendency: DistillationPluginTendency | None = None
    write_rules: DistillationPluginWriteRules | None = None
    metadata: dict[str, str | int | float | bool | None] | None = None
    updated_by: str | None = Field(default=None, max_length=120)


class DistillationPluginRegistryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available_plugins: list[DistillationPluginDefinition]
    current: DistillationPluginPolicy
