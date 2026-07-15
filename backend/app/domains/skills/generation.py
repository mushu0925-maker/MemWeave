from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.schemas.clarification import QuestionTargetSchema, UncertainItemSchema
from app.schemas.persona_item import PersonaItemSchema
from app.schemas.raw_source import RawSourceSchema
from app.schemas.skill_generation import (
    SkillAuditEntry,
    SkillBucket,
    SkillEvidenceType,
    SkillEvidenceUnit,
    SkillGenerationResponse,
    SkillLibrarySection,
    SkillQuestionBacklogItem,
    SkillUsageMatrix,
)
from app.services.persona_core_libraries import PERSONA_LIBRARY_DEFINITIONS

HARD_EXCLUDE_POLICIES = {
    "exclude_from_chat_and_skill_keep_for_audit",
    "do_not_use_for_chat_or_skill",
}
DOWNRANK_POLICY = "low_confidence_context_only"
CORRECT_POLICY = "use_corrected_claim"
KEEP_POLICY = "usable_evidence"

RISK_PENALTY = {
    "none": 0,
    "low_confidence": 8,
    "negative_memory": 12,
    "sensitive": 15,
    "conflict": 20,
    "unsupported_fact": 30,
    "over_intimacy": 25,
    "impersonation": 40,
    "safety_boundary": 0,
}

BUCKET_ORDER: dict[SkillBucket, int] = {
    "excluded": 0,
    "audit": 1,
    "caution": 2,
    "supporting": 3,
    "core": 4,
}


@dataclass(frozen=True)
class SkillGenerationInput:
    profile_id: Any
    persona_items: list[PersonaItemSchema]
    raw_sources: list[RawSourceSchema]
    uncertain_items: list[UncertainItemSchema]
    question_targets: list[QuestionTargetSchema]
    include_audit_units: bool = False


@dataclass(frozen=True)
class RelatedPolicy:
    policy: str = ""
    corrected_claim: str = ""
    uncertain_item_id: str = ""
    uncertain_status: str = ""
    uncertain_risk_type: str = ""
    match_kind: str = ""


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _normalized_claim(value: str) -> str:
    return re.sub(r"\W+", "", value.lower())


def _source_text(source: RawSourceSchema | None) -> str:
    if source is None:
        return ""
    return source.pii_masked_text or source.extracted_text or source.original_text


def _claims_related(item: PersonaItemSchema, uncertain: UncertainItemSchema) -> bool:
    item_text = _normalized_claim(" ".join([item.signal, item.prompt_snippet, item.evidence_quote]))
    uncertain_text = _normalized_claim(uncertain.claim)
    if not item_text or not uncertain_text:
        return False
    return item_text in uncertain_text or uncertain_text in item_text


def _policy_for_item(item: PersonaItemSchema, uncertain_items: list[UncertainItemSchema]) -> RelatedPolicy:
    for uncertain in uncertain_items:
        if uncertain.persona_item_id is None or uncertain.persona_item_id != item.id:
            continue
        policy = str(uncertain.metadata.get("use_policy") or "")
        corrected_claim = str(uncertain.metadata.get("corrected_claim") or "")
        return RelatedPolicy(
            policy=policy,
            corrected_claim=corrected_claim,
            uncertain_item_id=str(uncertain.id),
            uncertain_status=uncertain.status,
            uncertain_risk_type=uncertain.risk_type,
            match_kind="persona_item_id",
        )

    for uncertain in uncertain_items:
        same_source = uncertain.source_id is not None and item.source_id is not None and uncertain.source_id == item.source_id
        same_library = uncertain.library_group == item.library_group and uncertain.library_key == item.library_key
        if not same_source or not same_library or not _claims_related(item, uncertain):
            continue
        policy = str(uncertain.metadata.get("use_policy") or "")
        corrected_claim = str(uncertain.metadata.get("corrected_claim") or "")
        return RelatedPolicy(
            policy=policy,
            corrected_claim=corrected_claim,
            uncertain_item_id=str(uncertain.id),
            uncertain_status=uncertain.status,
            uncertain_risk_type=uncertain.risk_type,
            match_kind="source_library_claim",
        )
    return RelatedPolicy()


def _evidence_type(item: PersonaItemSchema) -> SkillEvidenceType:
    key = item.library_key
    group = item.library_group
    if group == "L" or key.startswith("boundary_"):
        return "boundary_rule"
    if group == "M" or key.startswith("voice_"):
        return "voice_feature"
    if key == "fact_direct_quotes":
        return "quote"
    if group == "A":
        return "fact"
    if group == "B":
        return "style_marker"
    if group == "C":
        return "emotion_response"
    if group == "F":
        return "relationship_pattern"
    if group == "G":
        return "decision_pattern"
    if item.risk == "unsupported_fact":
        return "model_inference"
    if item.subject_scope in {"source_author", "other_person"} and item.write_target != "target_profile":
        return "user_interpretation"
    return "model_inference" if item.status == "rejected_until_confirmed" else "emotion_response"


def _scene_from_key(item: PersonaItemSchema) -> str:
    key = item.library_key
    if key.startswith("care_"):
        return "care"
    if key.startswith("conflict_"):
        return "conflict"
    if key.startswith("emotion_"):
        return key.removeprefix("emotion_")
    if key.startswith("scenario_"):
        return key.removeprefix("scenario_")
    if key.startswith("relationship_"):
        return "relationship"
    if key.startswith("decision_"):
        return "decision"
    if key.startswith("growth_"):
        return "growth_change"
    if key.startswith("boundary_"):
        return "boundary"
    if key.startswith("voice_"):
        return "voice"
    if key.startswith("language_"):
        return "language_style"
    if key.startswith("fact_"):
        return "fact"
    return "unknown"


def _context_signature(item: PersonaItemSchema, source: RawSourceSchema | None) -> dict[str, str]:
    tags = item.metadata.get("tags")
    tag_text = ",".join(str(tag) for tag in tags) if isinstance(tags, list) else ""
    return {
        "scene": _scene_from_key(item),
        "relationship": str(item.metadata.get("relationship") or "unknown"),
        "emotion": str(item.metadata.get("emotion") or "unknown"),
        "speaker": str(item.metadata.get("speaker") or "unknown"),
        "target": str(item.metadata.get("target") or item.subject_scope or "unknown"),
        "time_phase": item.evidence_time_range or "unknown",
        "medium": source.source_type if source is not None else "unknown",
        "tags": tag_text[:160],
    }


def _claim_text(item: PersonaItemSchema, policy: RelatedPolicy) -> str:
    if policy.policy == CORRECT_POLICY and policy.corrected_claim:
        return _clean_text(policy.corrected_claim)
    claim = _clean_text(item.prompt_snippet or item.signal)
    if "别管我" in claim and ("挽留" in claim or "别马上走" in claim):
        return (
            "边界表达：'别管我'只支持“不希望对方马上离开/需要低压陪伴”，"
            "不支持继续追问；'停一下，别问了'表示必须停止追问。"
        )
    return claim


def _hard_exclusion_reason(item: PersonaItemSchema, policy: RelatedPolicy) -> str | None:
    if item.status in {"hidden", "forgotten", "deleted"}:
        return f"persona_item_status_{item.status}"
    if policy.policy in HARD_EXCLUDE_POLICIES:
        return policy.policy
    if policy.uncertain_status == "open" and policy.policy not in {KEEP_POLICY, CORRECT_POLICY}:
        return "open_uncertain_item_requires_confirmation"
    if item.write_target == "rejected_until_confirmed" and policy.policy not in {KEEP_POLICY, CORRECT_POLICY}:
        return "rejected_until_confirmed_without_user_confirmation"
    if item.risk == "impersonation" and item.library_group != "L":
        return "impersonation_risk_outside_boundary_library"
    if item.risk == "unsupported_fact" and item.library_group == "A":
        return "unsupported_fact_cannot_be_fact_core"
    return None


def _status_score(status: str) -> float:
    return {"active": 10, "candidate": 3, "rejected_until_confirmed": 0}.get(status, 0)


def _stability_score(stability: str) -> float:
    return {"stable": 15, "candidate": 6, "single_observation": 3, "unknown": 0, "conflict": -10}.get(
        stability, 0
    )


def _evidence_score(item: PersonaItemSchema, source: RawSourceSchema | None) -> float:
    score = 0.0
    if item.source_id is not None:
        score += 4
    if source is not None and source.deleted_at is None:
        score += 4
    if item.evidence_quote:
        score += 3
    if item.evidence_time_range:
        score += 2
    if _source_text(source) and source is not None and source.deleted_at is None:
        score += 2
    return score


def _confirmation_score(item: PersonaItemSchema, policy: RelatedPolicy) -> float:
    if policy.policy in {KEEP_POLICY, CORRECT_POLICY}:
        return 15
    if item.extraction_method in {"manual", "manual_override", "question_target_answer"}:
        return 12
    if item.status == "active":
        return 5
    return 0


def _library_weight(item: PersonaItemSchema) -> float:
    if item.library_group in {"B", "I", "J"}:
        return 1.12
    if item.library_group == "L":
        return 1.18
    if item.library_group == "M":
        return 1.05
    if item.library_group in {"A", "E"}:
        return 1.0
    return 1.06


def _context_weight(item: PersonaItemSchema, context: dict[str, str]) -> float:
    known_values = sum(1 for key in ("scene", "target", "time_phase", "medium") if context.get(key) not in {"", "unknown"})
    if item.library_group in {"B", "C", "F", "H", "I", "J"} and known_values >= 2:
        return 1.2
    if known_values >= 2:
        return 1.1
    if known_values == 1:
        return 1.0
    return 0.85


def _duplicate_key(item: PersonaItemSchema) -> tuple[str, str, str]:
    return (item.library_group, item.library_key, _normalized_claim(item.signal))


def _repetition_score(item: PersonaItemSchema, duplicate_counts: Counter[tuple[str, str, str]]) -> float:
    count = duplicate_counts.get(_duplicate_key(item), 1)
    if count >= 4:
        return 10
    if count == 3:
        return 8
    if count == 2:
        return 5
    return 0


def _repetition_quality_weight(item: PersonaItemSchema, duplicate_counts: Counter[tuple[str, str, str]]) -> float:
    count = duplicate_counts.get(_duplicate_key(item), 1)
    if count <= 1:
        return 1.0
    if item.library_group in {"B", "I", "J"}:
        return 1.25
    return 1.1


def _independent_source_counts(persona_items: list[PersonaItemSchema]) -> dict[tuple[str, str, str], int]:
    sources_by_claim: dict[tuple[str, str, str], set[Any]] = {}
    for item in persona_items:
        if item.source_id is None:
            continue
        sources_by_claim.setdefault(_duplicate_key(item), set()).add(item.source_id)
    return {key: len(source_ids) for key, source_ids in sources_by_claim.items()}


def _independent_source_count(
    item: PersonaItemSchema,
    source_counts: dict[tuple[str, str, str], int],
) -> int:
    return source_counts.get(_duplicate_key(item), 0)


def _is_user_confirmed(
    item: PersonaItemSchema,
    source: RawSourceSchema | None,
    policy: RelatedPolicy,
) -> bool:
    if policy.policy in {KEEP_POLICY, CORRECT_POLICY}:
        return True
    if item.extraction_method in {"manual", "manual_override"}:
        return True
    if item.metadata.get("confirmation_action") in {"keep", "correct"}:
        return True
    if source is None:
        return False
    if source.source_type == "manual_override":
        return True
    return source.metadata.get("confirmation_action") in {"keep", "correct"} or source.metadata.get("use_policy") in {
        KEEP_POLICY,
        CORRECT_POLICY,
    }


def _max_bucket(
    item: PersonaItemSchema,
    evidence_type: SkillEvidenceType,
    source: RawSourceSchema | None,
    policy: RelatedPolicy,
    independent_source_count: int,
    user_confirmed: bool,
) -> tuple[SkillBucket, str]:
    if policy.policy in HARD_EXCLUDE_POLICIES:
        return "excluded", policy.policy
    if policy.policy == DOWNRANK_POLICY:
        return "caution", "user_downranked"
    if evidence_type == "fact" and independent_source_count < 2 and not user_confirmed:
        return "supporting", "single_source_fact_requires_confirmation"
    if evidence_type in {"user_interpretation", "model_inference"}:
        return "caution", f"{evidence_type}_cannot_be_core"
    if item.risk in {"negative_memory", "sensitive", "conflict", "low_confidence"}:
        return "caution", f"risk_{item.risk}"
    if item.confidence < 0.5:
        return "caution", "confidence_below_0_5"
    if item.stability in {"single_observation", "candidate", "unknown"}:
        return "supporting", f"stability_{item.stability}"
    if source is None or source.deleted_at is not None:
        return "supporting", "source_missing_or_deleted"
    if item.source_id is None:
        return "supporting", "source_id_missing"
    return "core", "none"


def _bucket_from_score(score: float) -> SkillBucket:
    if score >= 80:
        return "core"
    if score >= 60:
        return "supporting"
    if score >= 40:
        return "caution"
    return "audit"


def _apply_bucket_cap(bucket: SkillBucket, max_bucket: SkillBucket) -> SkillBucket:
    return bucket if BUCKET_ORDER[bucket] <= BUCKET_ORDER[max_bucket] else max_bucket


def _usage_matrix(
    *,
    item: PersonaItemSchema,
    evidence_type: SkillEvidenceType,
    bucket: SkillBucket,
    source: RawSourceSchema | None,
    policy: RelatedPolicy,
    independent_source_count: int,
    user_confirmed: bool,
) -> SkillUsageMatrix:
    audit_only = bucket in {"audit", "excluded"}
    needs_caution = bucket == "caution" or item.risk != "none" or policy.policy == DOWNRANK_POLICY
    source_available = source is not None and source.deleted_at is None
    can_state_as_fact = (
        evidence_type == "fact"
        and source_available
        and item.risk == "none"
        and item.confidence >= 0.6
        and bucket in {"core", "supporting"}
        and policy.policy != DOWNRANK_POLICY
        and item.subject_scope not in {"source_author", "other_person"}
        and (independent_source_count >= 2 or user_confirmed)
    )
    can_generate_style = (
        evidence_type in {"style_marker", "emotion_response", "relationship_pattern", "decision_pattern", "voice_feature"}
        and bucket in {"core", "supporting"}
        and not audit_only
        and item.risk == "none"
        and item.stability == "stable"
    )
    if bucket == "caution":
        can_generate_style = False
    return SkillUsageMatrix(
        can_retrieve=not audit_only,
        can_generate_style=can_generate_style,
        can_state_as_fact=can_state_as_fact,
        can_quote=bool(item.evidence_quote and source_available and not audit_only),
        can_simulate=bucket == "core" and item.confidence >= 0.75 and item.library_group not in {"L", "M"},
        needs_caution=needs_caution,
        needs_question=bucket == "caution" or item.status == "rejected_until_confirmed",
        audit_only=audit_only,
    )


def _ranking_score(
    item: PersonaItemSchema,
    source: RawSourceSchema | None,
    policy: RelatedPolicy,
    duplicate_counts: Counter[tuple[str, str, str]],
    context: dict[str, str],
) -> tuple[float, list[str], dict[str, float]]:
    confidence_score = item.confidence * 35
    status_score = _status_score(item.status)
    stability_score = _stability_score(item.stability)
    evidence_score = _evidence_score(item, source)
    confirmation_score = _confirmation_score(item, policy)
    repetition_score = _repetition_score(item, duplicate_counts)
    risk_penalty = RISK_PENALTY.get(item.risk, 8)
    policy_penalty = 25 if policy.policy == DOWNRANK_POLICY else 0
    base = confidence_score + status_score + stability_score + evidence_score + confirmation_score + repetition_score
    score = (
        base
        * _library_weight(item)
        * _context_weight(item, context)
        * _repetition_quality_weight(item, duplicate_counts)
        - risk_penalty
        - policy_penalty
    )
    clamped = max(0.0, min(100.0, round(score, 2)))
    parts = {
        "confidence": round(confidence_score, 2),
        "status": round(status_score, 2),
        "stability": round(stability_score, 2),
        "evidence": round(evidence_score, 2),
        "confirmation": round(confirmation_score, 2),
        "repetition": round(repetition_score, 2),
        "risk_penalty": round(risk_penalty, 2),
        "policy_penalty": round(policy_penalty, 2),
    }
    reasons = [
        f"confidence={item.confidence:.2f}",
        f"status={item.status}",
        f"stability={item.stability}",
        f"risk={item.risk}",
        f"policy={policy.policy or 'none'}",
    ]
    if source is None:
        reasons.append("source_missing")
    elif source.deleted_at is not None:
        reasons.append("source_deleted")
    return clamped, reasons, parts


def _build_unit(
    *,
    item: PersonaItemSchema,
    source: RawSourceSchema | None,
    policy: RelatedPolicy,
    duplicate_counts: Counter[tuple[str, str, str]],
    source_counts: dict[tuple[str, str, str], int],
) -> SkillEvidenceUnit:
    evidence_type = _evidence_type(item)
    context = _context_signature(item, source)
    score, reasons, confidence_parts = _ranking_score(item, source, policy, duplicate_counts, context)
    independent_source_count = _independent_source_count(item, source_counts)
    user_confirmed = _is_user_confirmed(item, source, policy)
    max_bucket, cap_reason = _max_bucket(
        item,
        evidence_type,
        source,
        policy,
        independent_source_count,
        user_confirmed,
    )
    bucket = _apply_bucket_cap(_bucket_from_score(score), max_bucket)
    reasons.extend(
        [
            f"independent_sources={independent_source_count}",
            f"user_confirmed={str(user_confirmed).lower()}",
        ]
    )
    usage = _usage_matrix(
        item=item,
        evidence_type=evidence_type,
        bucket=bucket,
        source=source,
        policy=policy,
        independent_source_count=independent_source_count,
        user_confirmed=user_confirmed,
    )
    claim_text = _claim_text(item, policy)
    if bucket == "caution" and item.risk in {"low_sample", "conflict"} and "仅低置信参考" not in claim_text:
        claim_text = f"仅低置信参考，不能作为稳定规则：{claim_text}"
    return SkillEvidenceUnit(
        unit_id=f"{item.id}:{item.library_key}",
        profile_id=item.profile_id,
        source_id=item.source_id,
        persona_item_id=item.id,
        library_group=item.library_group,
        library_key=item.library_key,
        claim_text=claim_text,
        evidence_quote=item.evidence_quote,
        evidence_type=evidence_type,
        context_signature=context,
        source_role=str(item.metadata.get("source_role") or "unknown"),
        subject_scope=item.subject_scope,
        time_range=item.evidence_time_range,
        source_deleted=source.deleted_at is not None if source is not None else False,
        user_policy=policy.policy,
        risk=item.risk,
        status=item.status,
        confidence_parts=confidence_parts,
        ranking_score=score,
        bucket=bucket,
        cap_rule=max_bucket,
        cap_reason=cap_reason,
        usage=usage,
        score_reason=reasons,
    )


def _empty_library_sections() -> dict[str, SkillLibrarySection]:
    return {group: SkillLibrarySection(library_group=group) for group in "ABCDEFGHIJKLM"}


def _append_to_library(libraries: dict[str, SkillLibrarySection], unit: SkillEvidenceUnit) -> None:
    section = libraries.setdefault(unit.library_group, SkillLibrarySection(library_group=unit.library_group))
    if unit.bucket == "core":
        section.core.append(unit)
    elif unit.bucket == "supporting":
        section.supporting.append(unit)
    elif unit.bucket == "caution":
        section.caution.append(unit)


def _question_backlog(question_targets: list[QuestionTargetSchema]) -> list[SkillQuestionBacklogItem]:
    questions = [
        SkillQuestionBacklogItem(
            question_target_id=question.id,
            source_id=question.source_id,
            target_group=question.target_group,
            target_library_key=question.target_library_key,
            reason=question.reason,
            question=question.question,
            priority=question.priority,
            expected_evidence_type=question.expected_evidence_type,
        )
        for question in question_targets
        if question.status == "open"
    ]
    return sorted(questions, key=lambda question: question.priority, reverse=True)


def _section_units(section: SkillLibrarySection) -> list[SkillEvidenceUnit]:
    return [*section.core, *section.supporting, *section.caution]


def _all_library_units(libraries: dict[str, SkillLibrarySection]) -> list[SkillEvidenceUnit]:
    units: list[SkillEvidenceUnit] = []
    for section in libraries.values():
        units.extend(_section_units(section))
    return sorted(units, key=lambda unit: unit.ranking_score, reverse=True)


def _top_units(units: list[SkillEvidenceUnit], limit: int) -> list[SkillEvidenceUnit]:
    return sorted(units, key=lambda unit: unit.ranking_score, reverse=True)[:limit]


def _dedupe_units(units: list[SkillEvidenceUnit]) -> list[SkillEvidenceUnit]:
    seen: set[str] = set()
    deduped: list[SkillEvidenceUnit] = []
    for unit in units:
        if unit.unit_id in seen:
            continue
        seen.add(unit.unit_id)
        deduped.append(unit)
    return deduped


def _unit_line(unit: SkillEvidenceUnit, *, include_quote: bool = False) -> str:
    flags = []
    if unit.usage.can_state_as_fact:
        flags.append("fact")
    if unit.usage.can_generate_style:
        flags.append("style")
    if unit.usage.needs_caution:
        flags.append("caution")
    flag_text = ",".join(flags) if flags else "context"
    line = (
        f"- [{unit.library_key}] {unit.claim_text} "
        f"(bucket={unit.bucket}, score={unit.ranking_score:.2f}, use={flag_text}, cap={unit.cap_reason})"
    )
    if include_quote and unit.evidence_quote:
        line += f" evidence={unit.evidence_quote}"
    return line


def _append_unit_lines(
    lines: list[str],
    units: list[SkillEvidenceUnit],
    *,
    empty_text: str,
    limit: int = 8,
    include_quote: bool = False,
) -> None:
    selected = _top_units(units, limit)
    if not selected:
        lines.append(f"- {empty_text}")
        return
    for unit in selected:
        lines.append(_unit_line(unit, include_quote=include_quote))


def _skill_markdown(libraries: dict[str, SkillLibrarySection], caution_count: int, question_count: int) -> str:
    all_units = _all_library_units(libraries)
    quote_units = [unit for unit in all_units if unit.evidence_quote and unit.usage.can_quote]
    style_units = [
        unit
        for unit in all_units
        if unit.evidence_type in {"quote", "style_marker", "voice_feature"} and not unit.usage.audit_only
    ]
    scene_units = [
        unit
        for unit in all_units
        if unit.evidence_type in {"emotion_response", "relationship_pattern", "decision_pattern"}
        or unit.library_group in {"H", "I", "J"}
    ]
    boundary_units = [unit for unit in all_units if unit.evidence_type == "boundary_rule"]
    caution_units = [unit for unit in all_units if unit.bucket == "caution" or unit.usage.needs_caution]
    lines = [
        "# Generated Skill V2 Runtime Pack",
        "",
        "## Runtime Boundary",
        "- Generated Skill 是运行态产物，不是源数据。",
        "- 只能使用 evidence units 的 usage_matrix 允许的用途。",
        "- hide / forget / rejected_until_confirmed 不得靠高分进入正文。",
        "- 单来源事实没有用户确认时，不得当作确定事实陈述。",
        "- L 边界库优先于普通人格和语言风格。",
        "- 不要补写资料中没有的时间、地点、经历、关系进展或心理动机。",
        "- caution units 只能作为约束或低置信参考，不能作为风格生成材料。",
        "- 边界语义必须保留动作限制：“不希望马上离开”不等于允许继续追问。",
        "",
        "## Banned Generic Assistant Moves",
        "- 没有证据时，不套用“喝点水、坐一会儿、别想太多、我一直都在、你值得更好”等通用安抚话术。",
        "- 不把运行包写成心理画像报告；回复时优先使用下方原话、节奏、场景反应和边界。",
        "- 不把 caution 内容说成稳定事实；需要表达时必须带不确定性。",
        "",
        "## Runtime Speech Pack",
        "### Quoted Speech Fragments",
    ]
    _append_unit_lines(
        lines,
        quote_units,
        empty_text="当前没有可直接引用的原话；不要编造口头禅。",
        limit=8,
        include_quote=True,
    )
    lines.append("")
    lines.append("### Sentence Rhythm And Language")
    _append_unit_lines(
        lines,
        style_units,
        empty_text="当前语言风格证据不足；回复保持克制，不强行模仿。",
        limit=10,
        include_quote=True,
    )
    lines.append("")
    lines.append("### Scene Response Rules")
    _append_unit_lines(
        lines,
        scene_units,
        empty_text="当前场景反应证据不足；只做低置信陪伴，不扩写人格。",
        limit=12,
        include_quote=True,
    )
    lines.append("")
    lines.append("### Boundaries And Prohibitions")
    _append_unit_lines(
        lines,
        _dedupe_units(boundary_units + caution_units),
        empty_text="当前没有额外边界证据；仍遵守事实与安全默认边界。",
        limit=12,
        include_quote=True,
    )
    lines.extend(
        [
            "",
            "## Library Evidence Index",
        ]
    )
    for group, section in libraries.items():
        total = len(section.core) + len(section.supporting) + len(section.caution)
        if total == 0:
            continue
        lines.append(f"### {group}")
        for title, items in (("core", section.core), ("supporting", section.supporting), ("caution", section.caution)):
            if not items:
                continue
            lines.append(f"#### {title}")
            for unit in items[:12]:
                lines.append(_unit_line(unit, include_quote=True))
    lines.extend(
        [
            "",
            "## Caution And Questions",
            f"- caution_units={caution_count}",
            f"- open_questions={question_count}",
        ]
    )
    return "\n".join(lines)


def generate_skill_v2_minimal(payload: SkillGenerationInput) -> SkillGenerationResponse:
    source_by_id = {source.id: source for source in payload.raw_sources}
    duplicate_counts: Counter[tuple[str, str, str]] = Counter(_duplicate_key(item) for item in payload.persona_items)
    source_counts = _independent_source_counts(payload.persona_items)
    libraries = _empty_library_sections()
    units: list[SkillEvidenceUnit] = []
    audit: list[SkillAuditEntry] = []

    for item in payload.persona_items:
        source = source_by_id.get(item.source_id) if item.source_id is not None else None
        policy = _policy_for_item(item, payload.uncertain_items)
        excluded_reason = _hard_exclusion_reason(item, policy)
        if excluded_reason is not None:
            audit.append(
                SkillAuditEntry(
                    subject_type="persona_item",
                    subject_id=str(item.id),
                    source_id=item.source_id,
                    reason=excluded_reason,
                    detail=item.signal,
                    metadata={
                        "library_key": item.library_key,
                        "user_policy": policy.policy,
                        "policy_match_kind": policy.match_kind,
                    },
                )
            )
            continue

        unit = _build_unit(
            item=item,
            source=source,
            policy=policy,
            duplicate_counts=duplicate_counts,
            source_counts=source_counts,
        )
        if unit.bucket == "audit":
            audit.append(
                SkillAuditEntry(
                    subject_type="evidence_unit",
                    subject_id=unit.unit_id,
                    source_id=unit.source_id,
                    reason="audit_bucket",
                    detail=unit.claim_text,
                    metadata={"ranking_score": unit.ranking_score, "cap_reason": unit.cap_reason},
                )
            )
            if not payload.include_audit_units:
                continue

        units.append(unit)
        _append_to_library(libraries, unit)

    for section in libraries.values():
        section.core.sort(key=lambda unit: unit.ranking_score, reverse=True)
        section.supporting.sort(key=lambda unit: unit.ranking_score, reverse=True)
        section.caution.sort(key=lambda unit: unit.ranking_score, reverse=True)

    caution_units = [unit for unit in units if unit.bucket == "caution" or unit.usage.needs_caution]
    questions = _question_backlog(payload.question_targets)
    markdown = _skill_markdown(libraries, len(caution_units), len(questions))
    return SkillGenerationResponse(
        profile_id=payload.profile_id,
        generated_at=datetime.now(UTC),
        skill_markdown=markdown,
        libraries={group: section for group, section in libraries.items() if section.core or section.supporting or section.caution},
        evidence_units=sorted(units, key=lambda unit: unit.ranking_score, reverse=True),
        caution_report=sorted(caution_units, key=lambda unit: unit.ranking_score, reverse=True),
        question_backlog=questions,
        audit_report=audit,
        diagnostics={
            "version": "skill-v2-minimal",
            "algorithm_status": "usable_with_known_limits",
            "persona_items_read": len(payload.persona_items),
            "evidence_units_generated": len(units),
            "audit_entries": len(audit),
            "question_backlog": len(questions),
            "library_definitions": len(PERSONA_LIBRARY_DEFINITIONS),
            "known_limits": [
                "context_signature uses existing metadata and library_key heuristics only",
                "semantic conflict graph is not implemented in this minimal version",
                "no AI summarization or embedding dedupe is used",
            ],
        },
    )
