from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal
from uuid import UUID

from app.schemas.persona_item import PersonaItemSchema
from app.schemas.raw_source import RawSourceSchema
from app.schemas.source_segment import SourceSegmentSchema
from app.services.local_database import read_json_file, update_json_file

RuntimeVerdict = Literal["accept_runtime", "caution_only", "audit_only", "rejected"]

RUNTIME_GATE_SETTINGS_FILE = "runtime_gate_settings.json"


@dataclass(frozen=True)
class RuntimeGateSettings:
    enabled: bool = True
    strictness: str = "strict"
    block_do_not_use: bool = True
    block_rejected_until_confirmed: bool = True
    block_unsupported_fact: bool = True
    block_unconfirmed_conflict: bool = True
    block_third_party_target_judgment: bool = True
    candidate_judgment_policy: RuntimeVerdict = "audit_only"
    low_sample_policy: RuntimeVerdict = "caution_only"
    safety_boundary_policy: RuntimeVerdict = "audit_only"
    caution_skill_input_policy: RuntimeVerdict = "audit_only"


@dataclass(frozen=True)
class RuntimeGateDecision:
    persona_item_id: UUID
    source_id: UUID | None
    library: str
    verdict: RuntimeVerdict
    reason: str
    reasons: list[str] = field(default_factory=list)
    can_chat_retrieve: bool = False
    can_skill_input: bool = False


DEFAULT_RUNTIME_GATE_SETTINGS = RuntimeGateSettings()


def _settings_to_record(settings: RuntimeGateSettings) -> dict[str, Any]:
    return {
        "enabled": settings.enabled,
        "strictness": settings.strictness,
        "block_do_not_use": settings.block_do_not_use,
        "block_rejected_until_confirmed": settings.block_rejected_until_confirmed,
        "block_unsupported_fact": settings.block_unsupported_fact,
        "block_unconfirmed_conflict": settings.block_unconfirmed_conflict,
        "block_third_party_target_judgment": settings.block_third_party_target_judgment,
        "candidate_judgment_policy": settings.candidate_judgment_policy,
        "low_sample_policy": settings.low_sample_policy,
        "safety_boundary_policy": settings.safety_boundary_policy,
        "caution_skill_input_policy": settings.caution_skill_input_policy,
    }


def _settings_from_record(record: dict[str, Any]) -> RuntimeGateSettings:
    defaults = _settings_to_record(DEFAULT_RUNTIME_GATE_SETTINGS)
    merged = {**defaults, **record}
    return RuntimeGateSettings(
        enabled=bool(merged["enabled"]),
        strictness=_coerce_strictness(merged["strictness"]),
        block_do_not_use=bool(merged["block_do_not_use"]),
        block_rejected_until_confirmed=bool(merged["block_rejected_until_confirmed"]),
        block_unsupported_fact=bool(merged["block_unsupported_fact"]),
        block_unconfirmed_conflict=bool(merged["block_unconfirmed_conflict"]),
        block_third_party_target_judgment=bool(merged["block_third_party_target_judgment"]),
        candidate_judgment_policy=_coerce_verdict(merged["candidate_judgment_policy"], "audit_only"),
        low_sample_policy=_coerce_verdict(merged["low_sample_policy"], "caution_only"),
        safety_boundary_policy=_coerce_verdict(merged["safety_boundary_policy"], "audit_only"),
        caution_skill_input_policy=_coerce_verdict(merged["caution_skill_input_policy"], "audit_only"),
    )


def _coerce_strictness(value: object) -> str:
    if value in {"relaxed", "normal", "strict", "audit_only"}:
        return str(value)
    return "strict"


def _coerce_verdict(value: object, fallback: RuntimeVerdict) -> RuntimeVerdict:
    if value in {"accept_runtime", "caution_only", "audit_only", "rejected"}:
        return value  # type: ignore[return-value]
    return fallback


def get_runtime_gate_settings() -> RuntimeGateSettings:
    record = read_json_file(RUNTIME_GATE_SETTINGS_FILE, {})
    if not isinstance(record, dict):
        return DEFAULT_RUNTIME_GATE_SETTINGS
    if not record:
        update_json_file(RUNTIME_GATE_SETTINGS_FILE, {}, lambda _record: _settings_to_record(DEFAULT_RUNTIME_GATE_SETTINGS))
        return DEFAULT_RUNTIME_GATE_SETTINGS
    return _settings_from_record(record)


def reset_runtime_gate_settings() -> RuntimeGateSettings:
    update_json_file(RUNTIME_GATE_SETTINGS_FILE, {}, lambda _record: _settings_to_record(DEFAULT_RUNTIME_GATE_SETTINGS))
    return DEFAULT_RUNTIME_GATE_SETTINGS


def update_runtime_gate_settings(payload: dict[str, Any]) -> RuntimeGateSettings:
    current = _settings_to_record(get_runtime_gate_settings())
    allowed_keys = set(current)
    updates = {key: value for key, value in payload.items() if key in allowed_keys}
    updated = _settings_from_record({**current, **updates})
    update_json_file(RUNTIME_GATE_SETTINGS_FILE, {}, lambda _record: _settings_to_record(updated))
    return updated


def decide_runtime_gate(
    item: PersonaItemSchema,
    *,
    source: RawSourceSchema | None,
    source_segments: list[SourceSegmentSchema] | None = None,
    settings: RuntimeGateSettings | None = None,
) -> RuntimeGateDecision:
    config = _settings_for_strictness(settings or get_runtime_gate_settings())
    if not config.enabled:
        return _decision(item, "accept_runtime", "runtime_gate_disabled", ["runtime_gate_disabled"], settings=config)

    hard_reason = _hard_reject_reason(item, source, config, source_segments=source_segments)
    if hard_reason:
        return _decision(item, "rejected", hard_reason, [hard_reason], settings=config)

    reasons = _policy_reasons(item)
    verdict: RuntimeVerdict = "accept_runtime"

    if item.library_group == "L" or item.write_target == "boundary_only" or item.risk == "safety_boundary":
        verdict = _max_verdict(verdict, config.safety_boundary_policy)
        reasons.append("boundary_or_safety_item_not_runtime_style")

    if item.status == "candidate" and _metadata_usage(item) == "judgment" and item.stability == "single_observation":
        verdict = _max_verdict(verdict, config.candidate_judgment_policy)
        reasons.append("candidate_judgment_single_observation")

    if item.risk == "low_sample" or item.stability in {"single_observation", "unknown"}:
        verdict = _max_verdict(verdict, config.low_sample_policy)
        reasons.append("low_sample_or_single_observation")

    if item.write_target not in {"target_profile", "relationship_context"}:
        verdict = _max_verdict(verdict, "audit_only")
        reasons.append(f"write_target_not_runtime:{item.write_target}")

    if _metadata_usage(item) == "boundary_rule":
        verdict = _max_verdict(verdict, "audit_only")
        reasons.append("boundary_rule_constraint_only")

    reason = reasons[0] if reasons else "accepted_by_runtime_gate"
    return _decision(item, verdict, reason, reasons or [reason], settings=config)


def list_runtime_gate_decisions(
    items: list[PersonaItemSchema],
    *,
    sources_by_id: dict[UUID, RawSourceSchema],
    segments_by_source_id: dict[UUID, list[SourceSegmentSchema]] | None = None,
    settings: RuntimeGateSettings | None = None,
) -> list[RuntimeGateDecision]:
    config = _settings_for_strictness(settings or get_runtime_gate_settings())
    return [
        decide_runtime_gate(
            item,
            source=sources_by_id.get(item.source_id) if item.source_id else None,
            source_segments=segments_by_source_id.get(item.source_id, []) if item.source_id and segments_by_source_id else None,
            settings=config,
        )
        for item in items
    ]


def runtime_gate_summary(decisions: list[RuntimeGateDecision]) -> dict[str, Any]:
    counts: dict[str, int] = {
        "accept_runtime": 0,
        "caution_only": 0,
        "audit_only": 0,
        "rejected": 0,
    }
    for decision in decisions:
        counts[decision.verdict] += 1
    blocked = [decision for decision in decisions if not decision.can_skill_input]
    return {
        "total": len(decisions),
        "counts": counts,
        "skill_input_count": sum(1 for decision in decisions if decision.can_skill_input),
        "chat_retrievable_count": sum(1 for decision in decisions if decision.can_chat_retrieve),
        "blocked_count": len(blocked),
        "blocked_samples": [_decision_record(decision) for decision in blocked[:50]],
    }


def runtime_allowed_item_ids(decisions: list[RuntimeGateDecision], *, for_chat: bool = False) -> set[UUID]:
    if for_chat:
        return {decision.persona_item_id for decision in decisions if decision.can_chat_retrieve}
    return {decision.persona_item_id for decision in decisions if decision.can_skill_input}


def runtime_gate_report(decisions: list[RuntimeGateDecision]) -> list[dict[str, Any]]:
    return [_decision_record(decision) for decision in decisions]


def _hard_reject_reason(
    item: PersonaItemSchema,
    source: RawSourceSchema | None,
    settings: RuntimeGateSettings,
    *,
    source_segments: list[SourceSegmentSchema] | None = None,
) -> str:
    if item.status in {"hidden", "forgotten", "deleted"}:
        return f"status:{item.status}"
    if item.source_id is None:
        return "missing_source_id"
    if source is None:
        return "missing_raw_source"
    if source.deleted_at is not None:
        return "raw_source_deleted"
    if source.profile_id != item.profile_id:
        return "raw_source_profile_mismatch"
    if source_segments is not None:
        if not source_segments:
            return "missing_source_segment_attribution"
        if not _has_confirmed_target_person_segment(source_segments):
            return "source_segment_attribution_unconfirmed"
    if settings.block_rejected_until_confirmed and (
        item.status == "rejected_until_confirmed" or item.write_target == "rejected_until_confirmed"
    ):
        return "rejected_until_confirmed"
    if settings.block_do_not_use and _metadata_usage(item) == "do_not_use":
        return "usage_do_not_use"
    if settings.block_unsupported_fact and item.risk == "unsupported_fact":
        return "risk_unsupported_fact"
    if settings.block_unconfirmed_conflict and item.risk == "conflict":
        return "risk_conflict_requires_confirmation"
    if (
        settings.block_third_party_target_judgment
        and item.write_target == "target_profile"
        and _metadata_usage(item) == "judgment"
        and (item.subject_scope in {"source_author", "other_person", "unknown"} or item.risk == "low_sample")
    ):
        return "third_party_or_low_sample_judgment_target_profile"
    return ""


def _settings_for_strictness(settings: RuntimeGateSettings) -> RuntimeGateSettings:
    strictness = _coerce_strictness(settings.strictness)
    base = replace(settings, strictness=strictness)
    if strictness == "audit_only":
        return replace(
            base,
            candidate_judgment_policy="audit_only",
            low_sample_policy="audit_only",
            safety_boundary_policy="audit_only",
            caution_skill_input_policy="audit_only",
        )
    if strictness == "relaxed":
        return replace(
            base,
            candidate_judgment_policy="caution_only",
            low_sample_policy="accept_runtime",
            safety_boundary_policy="audit_only",
            caution_skill_input_policy="caution_only",
        )
    if strictness == "normal":
        return replace(
            base,
            candidate_judgment_policy="audit_only",
            low_sample_policy="caution_only",
            safety_boundary_policy="audit_only",
            caution_skill_input_policy="caution_only",
        )
    return base


def _has_confirmed_target_person_segment(segments: list[SourceSegmentSchema]) -> bool:
    return any(
        segment.target_person == "target_person" and segment.attribution_status == "confirmed"
        for segment in segments
    )


def _metadata_usage(item: PersonaItemSchema) -> str:
    usage = item.metadata.get("usage")
    return usage if isinstance(usage, str) else ""


def _policy_reasons(item: PersonaItemSchema) -> list[str]:
    reasons: list[str] = []
    if item.status != "active":
        reasons.append(f"status_{item.status}")
    if item.stability != "stable":
        reasons.append(f"stability_{item.stability}")
    if item.risk != "none":
        reasons.append(f"risk_{item.risk}")
    return reasons


def _max_verdict(current: RuntimeVerdict, candidate: RuntimeVerdict) -> RuntimeVerdict:
    order: dict[RuntimeVerdict, int] = {
        "accept_runtime": 0,
        "caution_only": 1,
        "audit_only": 2,
        "rejected": 3,
    }
    return candidate if order[candidate] > order[current] else current


def _decision(
    item: PersonaItemSchema,
    verdict: RuntimeVerdict,
    reason: str,
    reasons: list[str],
    *,
    settings: RuntimeGateSettings | None = None,
) -> RuntimeGateDecision:
    config = settings or get_runtime_gate_settings()
    can_skill_input = verdict == "accept_runtime" or (
        verdict == "caution_only" and config.caution_skill_input_policy == "caution_only"
    )
    return RuntimeGateDecision(
        persona_item_id=item.id,
        source_id=item.source_id,
        library=f"{item.library_group}/{item.library_key}",
        verdict=verdict,
        reason=reason,
        reasons=reasons,
        can_chat_retrieve=verdict == "accept_runtime",
        can_skill_input=can_skill_input,
    )


def _decision_record(decision: RuntimeGateDecision) -> dict[str, Any]:
    return {
        "persona_item_id": str(decision.persona_item_id),
        "source_id": str(decision.source_id) if decision.source_id else "",
        "library": decision.library,
        "verdict": decision.verdict,
        "reason": decision.reason,
        "reasons": decision.reasons,
        "can_chat_retrieve": decision.can_chat_retrieve,
        "can_skill_input": decision.can_skill_input,
    }
