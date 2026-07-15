from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


RelationshipType = Literal["family", "friend", "partner", "mentor", "self", "other"]


class ProfileCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=120)
    relationship: RelationshipType = "other"
    description: str = Field(default="", max_length=1000)
    boundaries: list[str] = Field(default_factory=list, max_length=24)


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    relationship: RelationshipType | None = None
    description: str | None = Field(default=None, max_length=1000)
    boundaries: list[str] | None = Field(default=None, max_length=24)


class ProfileSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    display_name: str = Field(min_length=1, max_length=120)
    relationship: RelationshipType = "other"
    description: str = Field(default="", max_length=1000)
    boundaries: list[str] = Field(default_factory=list, max_length=24)
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class ProfileDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: ProfileSchema
    raw_source_count: int = 0
    persona_item_count: int = 0
    uncertain_item_count: int = 0
    question_target_count: int = 0
