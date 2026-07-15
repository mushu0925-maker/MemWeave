from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Callable
from uuid import UUID

from app.schemas.quality_validation import QualityCheckResult, QualityValidationRequest, QualityValidationResponse
from app.services.chat_store import list_chat_records
from app.services.feature_policy_store import can_write, get_feature_policy
from app.services.monitoring_store import record_monitoring_event
from app.services.profile_store import get_profile
from app.services.raw_source_store import list_raw_sources
from app.services.runtime_persona_items import list_runtime_persona_items
from app.workflows.skill_generation_workflow import generate_skill_for_profile


QualityAlgorithm = Callable[[QualityValidationRequest], QualityValidationResponse]


def _now() -> datetime:
    return datetime.now(UTC)


def _check(
    key: str,
    name: str,
    passed: bool,
    *,
    expected: str,
    actual: str,
    evidence: dict[str, object] | None = None,
    action_hint: str = "",
    blocked: bool = False,
) -> QualityCheckResult:
    return QualityCheckResult(
        key=key,
        name=name,
        status="blocked" if blocked else ("pass" if passed else "fail"),
        expected=expected,
        actual=actual,
        evidence=evidence or {},
        action_hint=action_hint,
    )


def _overall(checks: list[QualityCheckResult]) -> str:
    if any(check.status == "fail" for check in checks):
        return "fail"
    if any(check.status == "blocked" for check in checks):
        return "blocked"
    return "pass"


def _score(checks: list[QualityCheckResult]) -> float | None:
    scored = [check for check in checks if check.status != "skipped"]
    if not scored:
        return None
    return round(sum(1 for check in scored if check.status == "pass") / len(scored), 6)


def _response(
    *,
    validation_key: str,
    policy_key: str,
    profile_id: UUID,
    checks: list[QualityCheckResult],
    diagnostics: dict[str, object] | None = None,
) -> QualityValidationResponse:
    policy = get_feature_policy(policy_key)
    summary = Counter(check.status for check in checks)
    summary["total"] = len(checks)
    return QualityValidationResponse(
        validation_key=validation_key,
        generated_at=_now(),
        feature_policy=policy,
        algorithm_key=policy.algorithm_key,
        strictness=policy.strictness,
        profile_id=profile_id,
        overall_status=_overall(checks),  # type: ignore[arg-type]
        checks=checks,
        score=_score(checks),
        summary=dict(summary),
        diagnostics=diagnostics or {},
    )


def _record_quality_event(policy_key: str, response: QualityValidationResponse) -> None:
    if not can_write(policy_key, "monitoring_event"):
        return
    record_monitoring_event(
        event_type="acceptance",
        status="success" if response.overall_status == "pass" else "blocked",
        profile_id=response.profile_id,
        subject_id=response.validation_key,
        workflow=policy_key,
        output_summary=f"overall={response.overall_status},score={response.score}",
        metadata={
            "validation_key": response.validation_key,
            "algorithm_key": response.algorithm_key,
            "strictness": response.strictness,
            "summary": response.summary,
            "diagnostics": response.diagnostics,
        },
    )


def _chat_record_quality_v1(payload: QualityValidationRequest) -> QualityValidationResponse:
    get_profile(payload.profile_id)
    policy = get_feature_policy("chat_quality_validation")
    checks: list[QualityCheckResult] = []
    if not policy.enabled:
        checks.append(
            _check(
                "feature_policy_enabled",
                "聊天质量验收已启用",
                False,
                expected="chat_quality_validation.enabled=true。",
                actual="enabled=false",
                action_hint="在 /admin 或 feature-policies API 打开该策略。",
                blocked=True,
            )
        )
        response = _response(
            validation_key="chat_quality_validation",
            policy_key="chat_quality_validation",
            profile_id=payload.profile_id,
            checks=checks,
        )
        _record_quality_event("chat_quality_validation", response)
        return response

    records = list_chat_records(payload.profile_id, limit=payload.sample_limit)
    successful = [record for record in records if record.model_call_status in {"success", "local"} and record.assistant_message.strip()]
    retrieval_hits = [
        record for record in successful if record.used_persona_item_ids or record.used_raw_source_ids
    ]
    third_person = [record for record in records if record.chat_mode == "third_person"]
    third_person_bad = [
        record
        for record in third_person
        if any(term in record.assistant_message for term in ("我是TA", "我就是TA", "作为TA本人", "我代替TA"))
    ]
    empty_replies = [record for record in records if not record.assistant_message.strip()]

    checks.append(
        _check(
            "chat_samples_present",
            "聊天样本存在",
            bool(records),
            expected="至少有 1 条聊天记录才能验收聊天体感。",
            actual=f"records={len(records)}",
            action_hint="先在前端或 API 执行一次真实聊天。",
            blocked=not records,
        )
    )
    checks.append(
        _check(
            "assistant_reply_not_empty",
            "助手回复非空",
            not empty_replies,
            expected="所有聊天记录都应有非空 assistant_message。",
            actual=f"empty_replies={len(empty_replies)}",
            evidence={"empty_record_ids": [str(record.id) for record in empty_replies[:20]]},
            action_hint="检查 persona_chat 的本地 fallback 和模型失败分支。",
        )
    )
    checks.append(
        _check(
            "retrieval_hit_rate",
            "聊天检索命中率",
            bool(successful) and len(retrieval_hits) / len(successful) >= policy.thresholds.get("blocker_min_rate", 0.6),
            expected="成功聊天应命中 persona_item 或 raw_source；严格模式不接受完全无上下文的回复。",
            actual=f"successful={len(successful)}, retrieval_hits={len(retrieval_hits)}",
            evidence={"hit_record_ids": [str(record.id) for record in retrieval_hits[:20]]},
            action_hint="检查 list_runtime_persona_items、raw_source fallback 和 chat_record used_* 写入。",
            blocked=not successful,
        )
    )
    checks.append(
        _check(
            "third_person_boundary",
            "第三人称边界",
            not third_person_bad,
            expected="第三人称聊天不能冒充 TA 或声称自己就是 TA。",
            actual=f"third_person_records={len(third_person)}, boundary_violations={len(third_person_bad)}",
            evidence={"bad_record_ids": [str(record.id) for record in third_person_bad[:20]]},
            action_hint="收紧 _third_person_system_prompt 或候选证据提示。",
        )
    )

    response = _response(
        validation_key="chat_quality_validation",
        policy_key="chat_quality_validation",
        profile_id=payload.profile_id,
        checks=checks,
        diagnostics={
            "record_count": len(records),
            "successful_count": len(successful),
            "retrieval_hit_count": len(retrieval_hits),
            "third_person_count": len(third_person),
        },
    )
    _record_quality_event("chat_quality_validation", response)
    return response


def _skill_runtime_quality_v1(payload: QualityValidationRequest) -> QualityValidationResponse:
    get_profile(payload.profile_id)
    policy = get_feature_policy("skill_quality_validation")
    checks: list[QualityCheckResult] = []
    if not policy.enabled:
        checks.append(
            _check(
                "feature_policy_enabled",
                "Skill 质量验收已启用",
                False,
                expected="skill_quality_validation.enabled=true。",
                actual="enabled=false",
                action_hint="在 /admin 或 feature-policies API 打开该策略。",
                blocked=True,
            )
        )
        response = _response(
            validation_key="skill_quality_validation",
            policy_key="skill_quality_validation",
            profile_id=payload.profile_id,
            checks=checks,
        )
        _record_quality_event("skill_quality_validation", response)
        return response

    raw_source_ids = {source.id for source in list_raw_sources(payload.profile_id)}
    runtime_items = list_runtime_persona_items(payload.profile_id)
    skill = generate_skill_for_profile(payload.profile_id, include_audit_units=payload.include_audit_units)
    unsupported_units = [
        unit
        for unit in skill.evidence_units
        if unit.source_id is None or unit.source_id not in raw_source_ids
    ]
    fact_unsafe_units = [
        unit
        for unit in skill.evidence_units
        if unit.usage.can_state_as_fact and (unit.source_id is None or unit.usage.audit_only or unit.usage.needs_question)
    ]
    retrievable_units = [unit for unit in skill.evidence_units if unit.usage.can_retrieve and not unit.usage.audit_only]

    checks.append(
        _check(
            "runtime_persona_items_present",
            "运行态 persona_items 存在",
            bool(runtime_items),
            expected="Skill 质量验收需要至少 1 条证据链完整的 runtime persona_item。",
            actual=f"runtime_persona_items={len(runtime_items)}",
            action_hint="先完成一次真实 ingest 并确保 persona_item.source_id 指向未删除 raw_source。",
            blocked=not runtime_items,
        )
    )
    checks.append(
        _check(
            "skill_markdown_present",
            "Skill markdown 非空",
            bool(skill.skill_markdown.strip()),
            expected="Skill 预览必须返回非空 markdown。",
            actual=f"markdown_chars={len(skill.skill_markdown.strip())}",
            action_hint="检查 generate_skill_for_profile 输入数据和生成模板。",
            blocked=not skill.skill_markdown.strip(),
        )
    )
    checks.append(
        _check(
            "evidence_units_supported",
            "evidence_units 证据链完整",
            bool(skill.evidence_units) and not unsupported_units,
            expected="每个 evidence_unit 都必须指向当前 profile 的未删除 raw_source。",
            actual=f"evidence_units={len(skill.evidence_units)}, unsupported={len(unsupported_units)}",
            evidence={"unsupported_unit_ids": [unit.unit_id for unit in unsupported_units[:20]]},
            action_hint="检查 runtime_persona_items 过滤和 Skill generation evidence unit 构造。",
            blocked=not skill.evidence_units,
        )
    )
    checks.append(
        _check(
            "usage_flags_safe",
            "usage flags 安全",
            not fact_unsafe_units,
            expected="需要追问、audit_only 或无 source 的 unit 不能 can_state_as_fact。",
            actual=f"unsafe_fact_units={len(fact_unsafe_units)}",
            evidence={"unsafe_unit_ids": [unit.unit_id for unit in fact_unsafe_units[:20]]},
            action_hint="检查 Skill usage matrix 和 cap_rule。",
        )
    )
    checks.append(
        _check(
            "retrievable_slice_available",
            "可检索切片存在",
            bool(retrievable_units),
            expected="至少有 1 个 can_retrieve 且非 audit_only 的 evidence_unit。",
            actual=f"retrievable_units={len(retrievable_units)}",
            action_hint="检查 evidence unit bucket 和 usage.can_retrieve。",
            blocked=not retrievable_units,
        )
    )

    response = _response(
        validation_key="skill_quality_validation",
        policy_key="skill_quality_validation",
        profile_id=payload.profile_id,
        checks=checks,
        diagnostics={
            "runtime_persona_item_count": len(runtime_items),
            "evidence_unit_count": len(skill.evidence_units),
            "retrievable_unit_count": len(retrievable_units),
            "question_backlog_count": len(skill.question_backlog),
            "audit_count": len(skill.audit_report),
        },
    )
    _record_quality_event("skill_quality_validation", response)
    return response


CHAT_QUALITY_ALGORITHMS: dict[str, QualityAlgorithm] = {
    "chat_record_quality_v1": _chat_record_quality_v1,
}

SKILL_QUALITY_ALGORITHMS: dict[str, QualityAlgorithm] = {
    "skill_runtime_quality_v1": _skill_runtime_quality_v1,
}


def validate_chat_quality(payload: QualityValidationRequest) -> QualityValidationResponse:
    policy = get_feature_policy("chat_quality_validation")
    algorithm = CHAT_QUALITY_ALGORITHMS.get(policy.algorithm_key)
    if algorithm is None:
        check = QualityCheckResult(
            key="algorithm_registered",
            name="聊天质量算法已注册",
            status="blocked",
            expected="algorithm_key 必须在 CHAT_QUALITY_ALGORITHMS 注册。",
            actual=f"unsupported_algorithm_key:{policy.algorithm_key}",
            action_hint="恢复 chat_record_quality_v1，或先注册新算法。",
        )
        return _response(
            validation_key="chat_quality_validation",
            policy_key="chat_quality_validation",
            profile_id=payload.profile_id,
            checks=[check],
        )
    return algorithm(payload)


def validate_skill_quality(payload: QualityValidationRequest) -> QualityValidationResponse:
    policy = get_feature_policy("skill_quality_validation")
    algorithm = SKILL_QUALITY_ALGORITHMS.get(policy.algorithm_key)
    if algorithm is None:
        check = QualityCheckResult(
            key="algorithm_registered",
            name="Skill 质量算法已注册",
            status="blocked",
            expected="algorithm_key 必须在 SKILL_QUALITY_ALGORITHMS 注册。",
            actual=f"unsupported_algorithm_key:{policy.algorithm_key}",
            action_hint="恢复 skill_runtime_quality_v1，或先注册新算法。",
        )
        return _response(
            validation_key="skill_quality_validation",
            policy_key="skill_quality_validation",
            profile_id=payload.profile_id,
            checks=[check],
        )
    return algorithm(payload)
