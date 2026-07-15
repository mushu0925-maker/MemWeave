from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


PluginStrictness = Literal["relaxed", "normal", "strict", "audit_only"]


class PersonaLibraryDefinitionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    category: str
    label: str
    purpose: str
    extraction_targets: list[str] = Field(default_factory=list)
    retrieval_triggers: list[str] = Field(default_factory=list)
    prompt_budget: int
    default_usage: str


class LibraryPluginDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plugin_key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=160)
    version: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=1000)
    algorithm_key: str = Field(min_length=1, max_length=120)
    allowed_library_keys: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    library_count: int = 0


class LibraryPluginPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_plugin_key: str = Field(min_length=1, max_length=120)
    enabled: bool = True
    strictness: PluginStrictness = "strict"
    allowed_library_keys_override: list[str] | None = None
    min_required_library_keys: list[str] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    updated_at: datetime
    updated_by: str = Field(default="system", max_length=120)


class LibraryPluginPolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_plugin_key: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    strictness: PluginStrictness | None = None
    allowed_library_keys_override: list[str] | None = None
    min_required_library_keys: list[str] | None = None
    metadata: dict[str, str | int | float | bool | None] | None = None
    updated_by: str | None = Field(default=None, max_length=120)


class LibraryPluginCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plugin_key: str
    enabled: bool
    strictness: PluginStrictness
    library_count: int
    categories: dict[str, list[PersonaLibraryDefinitionPayload]]
    allowed_library_keys: list[str]
    min_required_library_keys: list[str] = Field(default_factory=list)


class LibraryPluginRegistryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available_plugins: list[LibraryPluginDefinition]
    current: LibraryPluginPolicy
