from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


EvidenceRelation = Literal["direct_quote", "close_paraphrase", "semantic_inference"]
ClassificationStability = Literal["single_observation", "candidate", "stable", "conflict", "unknown"]
SubjectScope = Literal["target_person", "source_author", "other_person", "relationship_dynamic", "unknown"]
WriteTarget = Literal[
    "target_profile",
    "narrator_profile",
    "relationship_context",
    "boundary_only",
    "rejected_until_confirmed",
]
ClassificationUsage = Literal[
    "fact_only",
    "style_only",
    "judgment",
    "scenario_rule",
    "boundary_rule",
    "retrieval_hint",
    "do_not_use",
]
ClassificationRisk = Literal[
    "none",
    "low_sample",
    "unsupported_fact",
    "sensitive",
    "safety_boundary",
    "conflict",
    "over_intimacy",
    "impersonation",
]


class PersonaLibraryClassificationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    library_key: str = Field(min_length=1, max_length=80)
    subject_scope: SubjectScope
    write_target: WriteTarget
    signal: str = Field(min_length=1, max_length=300)
    evidence_quote: str = Field(min_length=1, max_length=500)
    evidence_relation: EvidenceRelation
    confidence: float = Field(ge=0, le=1)
    stability: ClassificationStability
    usage: ClassificationUsage
    risk: ClassificationRisk
    prompt_snippet: str = Field(min_length=1, max_length=320)
    tags: list[str] = Field(default_factory=list, max_length=12)
    time_scope: str | None = Field(default=None, max_length=120)
    priority: Literal["ai_classified"] = "ai_classified"

    @field_validator("tags")
    @classmethod
    def _trim_tags(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            tag = str(value or "").strip()[:40]
            if tag and tag not in cleaned:
                cleaned.append(tag)
        return cleaned[:12]


class PersonaLibraryRejectedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text_or_claim: str = Field(min_length=1, max_length=300)
    reason: Literal[
        "irrelevant",
        "too_vague",
        "unsupported",
        "unsafe",
        "duplicate",
        "needs_user_confirmation",
    ]
    note: str = Field(default="", max_length=240)


class PersonaLibraryConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    library_key: str = Field(min_length=1, max_length=80)
    conflict_summary: str = Field(min_length=1, max_length=300)
    evidence_quotes: list[str] = Field(default_factory=list, max_length=6)
    resolution: Literal["lower_confidence", "split_by_time", "needs_user_confirmation", "ignore_weak_claim"]


class PersonaLibraryClassificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_summary: str = Field(min_length=1, max_length=600)
    source_period: str | None = Field(default=None, max_length=120)
    dominant_categories: list[str] = Field(default_factory=list, max_length=12)
    items: list[PersonaLibraryClassificationItem] = Field(default_factory=list, max_length=80)
    rejected_items: list[PersonaLibraryRejectedItem] = Field(default_factory=list, max_length=30)
    conflicts: list[PersonaLibraryConflict] = Field(default_factory=list, max_length=20)
    notes: list[str] = Field(default_factory=list, max_length=20)


PERSONA_CLASSIFICATION_RESPONSE_SCHEMA: dict[str, object] = {
    "source_summary": "string: one concise summary of what this source can support",
    "source_period": "string|null: period/time range if the source clearly indicates one",
    "dominant_categories": "array[string]: categories most relevant to this source",
    "items": [
        {
            "library_key": "one key from the provided persona library catalog",
            "subject_scope": "target_person | source_author | other_person | relationship_dynamic | unknown",
            "write_target": "target_profile | narrator_profile | relationship_context | boundary_only | rejected_until_confirmed",
            "signal": "short claim extracted for this specific library",
            "evidence_quote": "short quote or close excerpt from the source",
            "evidence_relation": "direct_quote | close_paraphrase | semantic_inference",
            "confidence": "number between 0 and 1",
            "stability": "single_observation | candidate | stable | conflict | unknown",
            "usage": "fact_only | style_only | judgment | scenario_rule | boundary_rule | retrieval_hint | do_not_use",
            "risk": "none | low_sample | unsupported_fact | sensitive | safety_boundary | conflict | over_intimacy | impersonation",
            "prompt_snippet": "short future retrieval snippet, no raw long evidence",
            "tags": ["short tags"],
            "time_scope": "string|null",
            "priority": "ai_classified",
        }
    ],
    "rejected_items": [
        {
            "text_or_claim": "claim that should not be stored as a persona signal",
            "reason": "irrelevant | too_vague | unsupported | unsafe | duplicate | needs_user_confirmation",
            "note": "short reason",
        }
    ],
    "conflicts": [
        {
            "library_key": "affected library key",
            "conflict_summary": "short conflict explanation",
            "evidence_quotes": ["short quotes"],
            "resolution": "lower_confidence | split_by_time | needs_user_confirmation | ignore_weak_claim",
        }
    ],
    "notes": ["short processing notes"],
}
