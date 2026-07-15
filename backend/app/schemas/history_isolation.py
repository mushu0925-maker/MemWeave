from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


IsolationVerdict = Literal["accept_runtime", "caution_only", "audit_only", "rejected"]


class HistoryIsolationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dry_run: bool = True
    target_verdicts: list[IsolationVerdict] = Field(default_factory=lambda: ["audit_only", "rejected"])
    target_reasons: list[str] = Field(default_factory=list, max_length=50)
    max_items: int = Field(default=100, ge=1, le=500)
    updated_by: str = Field(default="backend-admin", max_length=120)


class HistoryIsolationCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persona_item_id: UUID
    source_id: UUID | None = None
    library: str
    signal: str
    evidence_quote: str = ""
    status: str
    verdict: IsolationVerdict
    reason: str
    reasons: list[str] = Field(default_factory=list)
    can_skill_input: bool = False
    can_chat_retrieve: bool = False


class HistoryIsolationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: UUID
    generated_at: datetime
    dry_run: bool
    applied: bool = False
    total_persona_items: int
    candidate_count: int
    hidden_count: int = 0
    raw_sources_before: int
    raw_sources_after: int
    target_verdicts: list[IsolationVerdict]
    target_reasons: list[str] = Field(default_factory=list)
    max_items: int


class HistoryIsolationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: HistoryIsolationSummary
    candidates: list[HistoryIsolationCandidate] = Field(default_factory=list)
