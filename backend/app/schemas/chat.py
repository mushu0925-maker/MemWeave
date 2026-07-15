from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


ChatModelStatus = Literal["success", "failed", "skipped", "blocked", "local"]
ChatMode = Literal["direct", "third_person"]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)
    chat_mode: ChatMode = "direct"
    use_model: bool = True
    save_record: bool = True
    skill_version_id: UUID | None = None


class ChatRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    profile_id: UUID
    chat_mode: ChatMode = "direct"
    user_message: str
    assistant_message: str
    model_call_status: ChatModelStatus
    model_call_reason: str = Field(default="", max_length=500)
    provider: str = Field(default="local", max_length=120)
    model_name: str | None = Field(default=None, max_length=160)
    used_persona_item_ids: list[UUID] = Field(default_factory=list, max_length=20)
    used_raw_source_ids: list[UUID] = Field(default_factory=list, max_length=10)
    created_at: datetime


class ChatRuntimeStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_skill_available: bool = False
    generated_skill_used: bool = False
    runtime_pack_in_prompt: bool = False
    skill_version: str | None = Field(default=None, max_length=80)
    skill_version_id: UUID | None = None
    skill_generated_at: datetime | None = None
    skill_version_title: str | None = Field(default=None, max_length=160)
    evidence_unit_count: int = 0
    runtime_slice_unit_count: int = 0
    audit_count: int = 0
    question_backlog_count: int = 0
    selected_skill_unit_ids: list[str] = Field(default_factory=list, max_length=50)
    selected_skill_persona_item_ids: list[UUID] = Field(default_factory=list, max_length=50)
    selected_skill_source_ids: list[UUID] = Field(default_factory=list, max_length=50)
    runtime_guard_applied: bool = False
    runtime_guard_reason: str = Field(default="", max_length=500)
    runtime_guard_rewrite_count: int = 0
    blocked_persona_item_count: int = 0
    blocked_persona_item_samples: list[dict[str, Any]] = Field(default_factory=list, max_length=30)
    reason: str = Field(default="", max_length=500)


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record: ChatRecord
    context_summary: str
    runtime_status: ChatRuntimeStatus = Field(default_factory=ChatRuntimeStatus)
    candidate_evidence: dict[str, str | bool | None] = Field(default_factory=dict)


class ChatClearResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: UUID
    deleted_count: int = 0
