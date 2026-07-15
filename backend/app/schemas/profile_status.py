from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


ProfileStage = Literal[
    "empty",
    "raw_only",
    "library_ready",
    "needs_confirmation",
    "skill_saved",
    "chat_ready",
    "config_missing",
]


class ProfileStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: UUID
    stage: ProfileStage
    stage_label: str = Field(max_length=80)
    next_action: str = Field(max_length=240)
    raw_source_count: int = 0
    persona_item_count: int = 0
    open_question_count: int = 0
    open_uncertain_count: int = 0
    skill_version_count: int = 0
    latest_skill_version_id: UUID | None = None
    ai_configured: bool = False
    can_generate_skill: bool = False
    can_chat: bool = False
    warnings: list[str] = Field(default_factory=list, max_length=8)
