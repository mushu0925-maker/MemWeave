from __future__ import annotations

import shutil
from collections import Counter
from datetime import UTC, datetime
from typing import Callable
from uuid import UUID, uuid4

from app.schemas.acceptance import AcceptanceCheckResult, AcceptanceRunRequest, AcceptanceRunResponse
from app.schemas.chat import ChatRequest
from app.schemas.ingest import IngestRequest
from app.schemas.profile import ProfileCreateRequest
from app.services.data_integrity_service import build_data_integrity_report
from app.services.feature_policy_store import get_feature_policy
from app.services.local_database import LocalDatabaseCorruptionError, data_dir, use_data_dir
from app.services.monitoring_metrics import build_monitoring_report
from app.services.monitoring_store import record_monitoring_event
from app.services.persona_core_libraries import PERSONA_LIBRARY_DEFINITIONS
from app.services.persona_item_store import list_persona_items
from app.services.profile_store import create_profile, get_profile
from app.services.raw_source_store import list_raw_sources
from app.services.runtime_persona_items import build_runtime_gate_diagnostics, list_runtime_persona_items
from app.services.source_segment_store import list_extracted_segments, list_source_segments
from app.services.uncertainty_store import list_question_targets, list_uncertain_items
from app.services.voice_generation_service import voice_generation_status
from app.workflows.ingest_workflow import IngestClassificationFailure, ingest_payload
from app.services.persona_chat import chat_with_profile
from app.workflows.skill_generation_workflow import generate_skill_for_profile


AcceptanceAlgorithm = Callable[[AcceptanceRunRequest], AcceptanceRunResponse]

DEFAULT_ACCEPTANCE_TEXT = (
    "\u6797\u665a\u5728\u9879\u76ee\u590d\u76d8\u4f1a\u4e0a\u8bf4\uff1a"
    "\u201c\u5148\u628a\u65f6\u95f4\u7ebf\u5199\u6e05\u695a\uff0c"
    "\u518d\u5199\u539f\u56e0\u548c\u4e0b\u4e00\u6b65\u3002\u201d"
    "\u5979\u5f53\u65f6\u6ca1\u6709\u8bc4\u4ef7\u8c01\u5bf9\u8c01\u9519\uff0c"
    "\u53ea\u8981\u6c42\u628a\u4e09\u4ef6\u5df2\u53d1\u751f\u7684\u4e8b\u6309\u987a\u5e8f\u5217\u51fa\u6765\u3002"
    "\u8fd9\u6bb5\u8d44\u6599\u53ea\u8bb0\u5f55\u4e00\u6b21\u4f1a\u8bae\u91cc\u7684\u4e00\u53e5\u539f\u8bdd\u3001"
    "\u5979\u7684\u8868\u8fbe\u987a\u5e8f\uff0c\u4ee5\u53ca\u5979\u504f\u5411\u5148\u6574\u7406\u65f6\u95f4\u7ebf\u518d\u8ba8\u8bba\u539f\u56e0\u7684\u5904\u7406\u65b9\u5f0f\u3002"
)


def _now() -> datetime:
    return datetime.now(UTC)


CHECK_METADATA: dict[str, tuple[str, str]] = {
    "feature_policy_enabled": (
        "acceptance_runner",
        "Acceptance execution is controlled by a backend feature policy.",
    ),
    "profile_available": (
        "profile_store",
        "Acceptance needs either an existing profile or permission to create an isolated profile.",
    ),
    "raw_source_preserved_first": (
        "ingest_workflow",
        "Raw source is the evidence source and must survive classification failure.",
    ),
    "persona_items_evidence_bound": (
        "ingest_workflow",
        "Persona items created by classification must point back to the raw source and active profile.",
    ),
    "raw_source_segment_created": (
        "source_segment_store",
        "Every raw source should have a user-confirmable segment attribution record.",
    ),
    "voice_dependencies_visible": (
        "voice_generation_service",
        "Voice output is optional, but IndexTTS2 and ffmpeg readiness must be visible to the user.",
    ),
    "third_person_candidate_isolated": (
        "chat_candidate_workflow",
        "Third-person chat discoveries must stay as candidate evidence until user confirmation.",
    ),
    "candidate_not_persona_item": (
        "chat_candidate_workflow",
        "Chat candidate evidence must not directly create stable persona_items.",
    ),
    "skill_runtime_generated": (
        "skill_generation_workflow",
        "Skill generation must produce a runtime artifact from evidence-backed persona items.",
    ),
    "monitoring_attribution_present": (
        "monitoring_metrics",
        "Monitoring metrics must include attribution and action hints so they are auditable.",
    ),
    "runtime_unsupported_memory_strict": (
        "monitoring_metrics",
        "Unsupported persona items must not enter chat or Skill runtime.",
    ),
    "algorithm_registered": (
        "acceptance_runner",
        "The configured acceptance algorithm must be registered in backend code.",
    ),
}


def _record_ids_from_evidence(evidence: dict[str, object]) -> list[str]:
    record_ids: list[str] = []
    for key in (
        "raw_source_id",
        "chat_record_id",
        "persona_item_ids",
        "invalid_item_ids",
        "bad_question_ids",
        "bad_uncertain_ids",
        "broken_item_ids",
        "unsupported_unit_ids",
        "used_persona_item_ids",
        "used_raw_source_ids",
    ):
        value = evidence.get(key)
        if isinstance(value, str) and value:
            record_ids.append(value)
        elif isinstance(value, list):
            record_ids.extend(str(item) for item in value[:50])
    return record_ids[:200]


def _check(
    key: str,
    name: str,
    passed: bool,
    *,
    module: str = "",
    record_ids: list[str] | None = None,
    reason: str = "",
    expected: str,
    actual: str,
    evidence: dict[str, object] | None = None,
    action_hint: str = "",
    suggested_action: str = "",
    blocked: bool = False,
    warning: bool = False,
) -> AcceptanceCheckResult:
    if blocked:
        status = "blocked"
    elif not passed:
        status = "warning" if warning else "fail"
    else:
        status = "pass"
    evidence_payload = evidence or {}
    default_module, default_reason = CHECK_METADATA.get(key, ("acceptance_runner", ""))
    return AcceptanceCheckResult(
        key=key,
        name=name,
        status=status,
        module=module or default_module,
        record_ids=record_ids or _record_ids_from_evidence(evidence_payload),
        reason=reason or default_reason,
        expected=expected,
        actual=actual,
        evidence=evidence_payload,
        action_hint=action_hint,
        suggested_action=suggested_action or action_hint,
    )


def _overall(checks: list[AcceptanceCheckResult]) -> str:
    if any(check.status == "blocked" for check in checks):
        return "blocked"
    if any(check.status == "fail" for check in checks):
        return "fail"
    if any(check.status == "warning" for check in checks):
        return "warning"
    return "pass"


def _response_with_checks(response: AcceptanceRunResponse, checks: list[AcceptanceCheckResult]) -> AcceptanceRunResponse:
    summary = Counter(check.status for check in checks)
    summary["total"] = len(checks)
    return response.model_copy(
        update={
            "checks": checks,
            "summary": dict(summary),
            "overall_status": _overall(checks),
        }
    )


def _finish(
    *,
    run_id: UUID,
    started_at: datetime,
    policy_key: str,
    profile_id: UUID | None,
    created_profile_id: UUID | None,
    checks: list[AcceptanceCheckResult],
) -> AcceptanceRunResponse:
    policy = get_feature_policy(policy_key)
    summary = Counter(check.status for check in checks)
    summary["total"] = len(checks)
    return AcceptanceRunResponse(
        run_id=run_id,
        started_at=started_at,
        finished_at=_now(),
        feature_policy=policy,
        overall_status=_overall(checks),  # type: ignore[arg-type]
        profile_id=profile_id,
        created_profile_id=created_profile_id,
        algorithm_key=policy.algorithm_key,
        strictness=policy.strictness,
        checks=checks,
        summary=dict(summary),
    )


def _runtime_blocker_checks(profile_id: UUID) -> list[AcceptanceCheckResult]:
    report = build_data_integrity_report()
    runtime_blockers = [issue for issue in report.issues if issue.severity == "runtime_blocker"]
    active_profile_blockers = [
        issue
        for issue in runtime_blockers
        if issue.profile_id in {None, str(profile_id)}
    ]
    return [
        _check(
            "data_integrity_runtime_blockers_zero",
            "运行态数据完整性硬门",
            not active_profile_blockers,
            module="data_integrity",
            record_ids=[f"{issue.record_type}:{issue.record_id}" for issue in active_profile_blockers[:50]],
            reason="runtime_blocker issues mean broken evidence could affect chat or Skill runtime.",
            expected="当前 profile 不存在 runtime_blocker 级别完整性问题。",
            actual=f"runtime_blockers={len(active_profile_blockers)}",
            evidence={
                "issues": [issue.model_dump(mode="json") for issue in active_profile_blockers[:20]],
                "summary": report.summary,
            },
            action_hint="先运行 /api/v1/integrity/repair，再重新执行验收。",
        )
    ]


def _registered_library_key_check(profile_id: UUID) -> AcceptanceCheckResult:
    persona_items = list_persona_items(profile_id, include_hidden=True)
    invalid_items = [
        item
        for item in persona_items
        if item.library_key not in PERSONA_LIBRARY_DEFINITIONS
    ]
    return _check(
        "registered_library_keys_only",
        "persona_items 库 key 注册硬门",
        not invalid_items,
        module="persona_item_store",
        record_ids=[str(item.id) for item in invalid_items[:50]],
        reason="Unregistered library_key cannot be safely routed into A-M library, chat retrieval, or Skill generation.",
        expected="所有 persona_items.library_key 都必须在后端 A-M registry 中注册。",
        actual=f"persona_items={len(persona_items)}, invalid_library_key_items={len(invalid_items)}",
        evidence={
            "invalid_library_keys": sorted({item.library_key for item in invalid_items}),
            "invalid_item_ids": [str(item.id) for item in invalid_items[:20]],
        },
        action_hint="修复库插件配置或隐藏/迁移异常 persona_items 后再验收。",
    )


def _runtime_persona_source_check(profile_id: UUID) -> AcceptanceCheckResult:
    runtime_items = list_runtime_persona_items(profile_id)
    raw_sources = {source.id: source for source in list_raw_sources(profile_id, include_deleted=True)}
    broken_items = []
    for item in runtime_items:
        source = raw_sources.get(item.source_id) if item.source_id is not None else None
        if source is None or source.deleted_at is not None or source.profile_id != item.profile_id:
            broken_items.append(item)
    return _check(
        "runtime_persona_items_have_live_sources",
        "运行态 persona_items 证据链硬门",
        not broken_items,
        module="runtime_persona_items",
        record_ids=[str(item.id) for item in broken_items[:50]],
        reason="Runtime persona items must be backed by live raw_sources in the same profile.",
        expected="list_runtime_persona_items 只返回 source 存在、未删除、profile 一致的条目。",
        actual=f"runtime_items={len(runtime_items)}, broken_runtime_items={len(broken_items)}",
        evidence={"broken_item_ids": [str(item.id) for item in broken_items[:20]]},
        action_hint="检查 runtime_persona_items 过滤规则与 raw_source 删除/恢复状态。",
    )


def _runtime_gate_accepts_empty_runtime_sample(profile_id: UUID) -> tuple[bool, dict[str, object]]:
    diagnostics = build_runtime_gate_diagnostics(profile_id)
    summary = diagnostics.get("summary", {})
    decisions = diagnostics.get("decisions", [])
    if not isinstance(summary, dict) or not isinstance(decisions, list):
        return False, {"summary": summary, "safe_blocked_count": 0, "unsafe_blocked_samples": []}

    total = int(summary.get("total") or 0)
    skill_input_count = int(summary.get("skill_input_count") or 0)
    chat_retrievable_count = int(summary.get("chat_retrievable_count") or 0)
    safe_reason_tokens = {
        "status_candidate",
        "status_rejected_until_confirmed",
        "stability_single_observation",
        "stability_unknown",
        "risk_low_sample",
        "low_sample_or_single_observation",
        "candidate_judgment_single_observation",
        "boundary_or_safety_item_not_runtime_style",
        "write_target_not_runtime",
        "boundary_rule_constraint_only",
        "rejected_until_confirmed",
        "third_party_or_low_sample_judgment_target_profile",
        "usage_do_not_use",
        "risk_unsupported_fact",
        "risk_conflict_requires_confirmation",
    }
    unsafe_reasons = {
        "missing_source_id",
        "missing_raw_source",
        "raw_source_deleted",
        "raw_source_profile_mismatch",
    }
    blocked_decisions: list[dict[str, object]] = []
    unsafe_blocked: list[dict[str, object]] = []
    for decision in decisions:
        if not isinstance(decision, dict):
            continue
        if decision.get("can_skill_input") is True or decision.get("can_chat_retrieve") is True:
            continue
        blocked_decisions.append(decision)
        reasons = [str(reason) for reason in decision.get("reasons", []) if reason]
        if any(reason in unsafe_reasons for reason in reasons):
            unsafe_blocked.append(decision)
            continue
        if not any(any(reason.startswith(token) for token in safe_reason_tokens) for reason in reasons):
            unsafe_blocked.append(decision)

    accepted = (
        total > 0
        and skill_input_count == 0
        and chat_retrievable_count == 0
        and len(blocked_decisions) == total
        and not unsafe_blocked
    )
    return accepted, {
        "summary": summary,
        "safe_blocked_count": len(blocked_decisions) - len(unsafe_blocked),
        "unsafe_blocked_samples": unsafe_blocked[:20],
        "blocked_samples": blocked_decisions[:20],
    }


def _resolved_target_match_checks(profile_id: UUID) -> list[AcceptanceCheckResult]:
    questions = list_question_targets(profile_id, include_closed=True)
    relevant_questions = [
        question
        for question in questions
        if question.status == "resolved" and "classification_succeeded" in question.metadata
    ]
    bad_questions = [
        question
        for question in relevant_questions
        if question.metadata.get("target_match_succeeded") is not True
    ]
    uncertain_items = list_uncertain_items(profile_id, include_closed=True)
    bad_uncertain = [
        item
        for item in uncertain_items
        if item.status == "resolved"
        and item.metadata.get("resolved_by_question_target_id")
        and item.metadata.get("target_match_succeeded") is False
    ]
    return [
        _check(
            "resolved_question_requires_target_match",
            "确认流 resolved 命中目标硬门",
            not bad_questions,
            module="question_answer_workflow",
            record_ids=[str(question.id) for question in bad_questions[:50]],
            reason="Question target cannot be resolved merely because classification returned some persona item.",
            expected="question_target.status=resolved 时 classification_succeeded=true 且 target_match_succeeded=true。",
            actual=f"resolved_classified_questions={len(relevant_questions)}, bad_resolved_questions={len(bad_questions)}",
            evidence={
                "bad_question_ids": [str(question.id) for question in bad_questions[:20]],
                "bad_targets": [
                    f"{question.target_group}/{question.target_library_key}" for question in bad_questions[:20]
                ],
            },
            action_hint="保持 question open，并把 target mismatch 写入 metadata；修复旧数据可走完整性维护。",
        ),
        _check(
            "resolved_uncertain_requires_target_match",
            "uncertain resolved 命中目标硬门",
            not bad_uncertain,
            module="question_answer_workflow",
            record_ids=[str(item.id) for item in bad_uncertain[:50]],
            reason="Linked uncertain item cannot be resolved when the answer missed the original target.",
            expected="由 question answer resolved 的 uncertain_item 必须继承 target_match_succeeded=true。",
            actual=f"bad_uncertain_resolved_by_question={len(bad_uncertain)}",
            evidence={"bad_uncertain_ids": [str(item.id) for item in bad_uncertain[:20]]},
            action_hint="把未命中 target 的 uncertain_item 保持 open，并提示用户继续补充。",
        ),
    ]


def _json_store_visibility_check() -> AcceptanceCheckResult:
    try:
        build_data_integrity_report()
    except LocalDatabaseCorruptionError as exc:
        return _check(
            "json_store_corruption_visible",
            "JSON store 损坏可见硬门",
            False,
            module="local_database",
            record_ids=[exc.filename],
            reason="A corrupted JSON store must fail visibly instead of being treated as empty data.",
            expected="读取损坏 JSON 时抛出 LocalDatabaseCorruptionError，并由 API 返回 500 诊断。",
            actual=f"corrupted:{exc.filename}:{exc.message}",
            evidence={"filename": exc.filename, "path": str(exc.path), "error": exc.message},
            action_hint="先备份并修复该 JSON 文件，不要继续写入默认空数据。",
            blocked=True,
        )
    return _check(
        "json_store_corruption_visible",
        "JSON store 损坏可见硬门",
        True,
        module="local_database",
        reason="All JSON stores used by integrity scan parsed successfully.",
        expected="损坏 JSON 不应被静默吞掉。",
        actual="integrity scan completed without LocalDatabaseCorruptionError",
        evidence={},
        action_hint="保持 local_database.read_json_file 的显式失败策略。",
    )


def _api_smoke_v1(payload: AcceptanceRunRequest) -> AcceptanceRunResponse:
    started_at = _now()
    run_id = uuid4()
    policy = get_feature_policy("acceptance_e2e")
    checks: list[AcceptanceCheckResult] = []
    created_profile_id: UUID | None = None

    checks.append(
        _check(
            "feature_policy_enabled",
            "验收模块策略开启",
            policy.enabled,
            expected="acceptance_e2e.enabled=true，且算法由后端 feature policy 控制。",
            actual=f"enabled={policy.enabled}, algorithm_key={policy.algorithm_key}, strictness={policy.strictness}",
            evidence={"write_rules": policy.write_rules.model_dump(mode="json")},
            action_hint="在 /api/v1/feature-policies/acceptance_e2e 打开 enabled。",
            blocked=not policy.enabled,
        )
    )
    if not policy.enabled:
        return _finish(
            run_id=run_id,
            started_at=started_at,
            policy_key="acceptance_e2e",
            profile_id=payload.profile_id,
            created_profile_id=created_profile_id,
            checks=checks,
        )

    if payload.profile_id is None and payload.create_isolated_profile:
        profile = create_profile(
            ProfileCreateRequest(
                display_name=f"MemWeave acceptance {started_at.strftime('%Y%m%d-%H%M%S')}",
                relationship="other",
                description="由后端验收模块创建的隔离 profile。",
                boundaries=["不要把主观感受写成客观事实", "没有证据时必须追问"],
            )
        )
        profile_id = profile.id
        created_profile_id = profile.id
    elif payload.profile_id is not None:
        profile_id = get_profile(payload.profile_id).id
    else:
        checks.append(
            _check(
                "profile_available",
                "验收 profile 可用",
                False,
                expected="提供 profile_id，或允许创建隔离 profile。",
                actual="没有 profile_id 且 create_isolated_profile=false。",
                action_hint="重新调用时传入 profile_id 或 create_isolated_profile=true。",
                blocked=True,
            )
        )
        return _finish(
            run_id=run_id,
            started_at=started_at,
            policy_key="acceptance_e2e",
            profile_id=None,
            created_profile_id=None,
            checks=checks,
        )

    checks.append(_json_store_visibility_check())
    checks.extend(_runtime_blocker_checks(profile_id))
    checks.append(_registered_library_key_check(profile_id))
    checks.append(_runtime_persona_source_check(profile_id))
    checks.extend(_resolved_target_match_checks(profile_id))

    raw_before = len(list_raw_sources(profile_id, include_deleted=True))
    persona_before = len(list_persona_items(profile_id, include_hidden=True))
    text = payload.raw_content or DEFAULT_ACCEPTANCE_TEXT
    ingest_blocked_reason = ""
    try:
        ingest_result = ingest_payload(
            payload=IngestRequest(
                source_type="interview",
                raw_content=text,
                metadata={"acceptance_run_id": str(run_id), "source": "acceptance_e2e"},
                profile_id=profile_id,
            ),
            original_text=text,
            routing_suffix="acceptance",
        )
        raw_source_id = ingest_result.raw_source.id
        persona_items = ingest_result.persona_items
    except IngestClassificationFailure as exc:
        raw_source_id = exc.raw_source.id
        persona_items = []
        ingest_blocked_reason = exc.reason

    raw_after = len(list_raw_sources(profile_id, include_deleted=True))
    persona_after = len(list_persona_items(profile_id, include_hidden=True))
    checks.append(
        _check(
            "raw_source_preserved_first",
            "raw_source 先保存",
            raw_after > raw_before and raw_source_id is not None,
            expected="即使分类失败，也必须先保存 raw_source。",
            actual=f"raw_before={raw_before}, raw_after={raw_after}, raw_source_id={raw_source_id}",
            evidence={"raw_source_id": str(raw_source_id)},
            action_hint="检查 ingest_workflow 是否先 save_raw_source 再 classify。",
        )
    )
    source_segments = list_source_segments(raw_source_id=raw_source_id)
    extracted_segments = list_extracted_segments(raw_source_id=raw_source_id)
    checks.append(
        _check(
            "raw_source_segment_created",
            "raw_source 片段层自动创建",
            bool(source_segments) and bool(extracted_segments),
            expected="每个新 raw_source 至少自动生成 1 条 source_segment 和 1 条 extracted_segment，等待用户确认归属。",
            actual=f"source_segments={len(source_segments)}, extracted_segments={len(extracted_segments)}",
            evidence={
                "raw_source_id": str(raw_source_id),
                "source_segment_ids": [str(segment.id) for segment in source_segments[:20]],
                "extracted_segment_ids": [str(segment.id) for segment in extracted_segments[:20]],
                "segment_statuses": [
                    {
                        "target_person": segment.target_person,
                        "attribution_status": segment.attribution_status,
                        "permitted_uses": segment.permitted_uses,
                    }
                    for segment in source_segments[:20]
                ],
            },
            action_hint="检查 save_raw_source 是否调用 ensure_source_segments_for_raw_source；旧资料可通过 Library 片段确认入口补齐。",
        )
    )
    checks.append(
        _check(
            "persona_items_evidence_bound",
            "persona_items 证据链完整",
            bool(persona_items)
            and all(item.source_id == raw_source_id and item.profile_id == profile_id for item in persona_items),
            expected="分类成功时每个 persona_item 都必须指向本次 raw_source 且 profile_id 一致。",
            actual=f"new_persona_items={len(persona_items)}, persona_total_delta={persona_after - persona_before}",
            evidence={"persona_item_ids": [str(item.id) for item in persona_items[:20]]},
            action_hint="若 blocked，多半是本地未配置 AI；若 fail，检查 save_classification_persona_items。",
            blocked=not persona_items and bool(ingest_blocked_reason),
        )
    )

    voice_status = voice_generation_status()
    voice_ready = voice_status.enabled and voice_status.configured
    checks.append(
        _check(
            "voice_dependencies_visible",
            "IndexTTS2 / ffmpeg 状态可见",
            voice_ready and voice_status.ffmpeg_available,
            module="voice_generation_service",
            reason="Voice output is not the source of truth, but the desktop client must show whether the current local voice path can run.",
            expected="IndexTTS2 enabled/configured；ffmpeg 可用时视频参考可抽音频。",
            actual=(
                f"voice_enabled={voice_status.enabled}, voice_configured={voice_status.configured}, "
                f"ffmpeg_available={voice_status.ffmpeg_available}"
            ),
            evidence={
                "provider": voice_status.provider,
                "base_url": voice_status.base_url,
                "ffmpeg_path": voice_status.ffmpeg_path,
                "ffmpeg_error": voice_status.ffmpeg_error[:500],
                "video_reference_supported": voice_status.video_reference_supported,
            },
            action_hint="如果需要声音效果，先配置 IndexTTS2 adapter 和 ffmpeg；声音模型只朗读已生成文本，不决定记忆事实。",
            warning=True,
        )
    )

    chat_response = chat_with_profile(
        profile_id,
        ChatRequest(
            message="那次冬天晚上她没有急着讲道理，而是陪我把事情按时间线说清楚。",
            chat_mode="third_person",
            use_model=payload.use_model_for_chat,
            save_record=True,
        ),
    )
    runtime_item_by_id = {item.id: item for item in list_runtime_persona_items(profile_id)}
    live_raw_source_ids = {source.id for source in list_raw_sources(profile_id)}
    broken_chat_persona_ids = [
        item_id
        for item_id in chat_response.record.used_persona_item_ids
        if item_id not in runtime_item_by_id
    ]
    broken_chat_raw_ids = [
        source_id
        for source_id in chat_response.record.used_raw_source_ids
        if source_id not in live_raw_source_ids
    ]
    checks.append(
        _check(
            "chat_runtime_usage_evidence_bound",
            "Chat runtime 使用证据链硬门",
            not broken_chat_persona_ids and not broken_chat_raw_ids,
            module="persona_chat",
            record_ids=[
                str(chat_response.record.id),
                *[str(item_id) for item_id in broken_chat_persona_ids[:30]],
                *[str(source_id) for source_id in broken_chat_raw_ids[:30]],
            ],
            reason="Chat runtime must only cite live runtime persona items and live raw sources from the same profile.",
            expected="chat_record.used_persona_item_ids 全部来自 list_runtime_persona_items，used_raw_source_ids 全部来自当前 profile 未删除 raw_sources。",
            actual=(
                f"used_persona={len(chat_response.record.used_persona_item_ids)}, "
                f"broken_persona={len(broken_chat_persona_ids)}, "
                f"used_raw={len(chat_response.record.used_raw_source_ids)}, "
                f"broken_raw={len(broken_chat_raw_ids)}"
            ),
            evidence={
                "chat_record_id": str(chat_response.record.id),
                "used_persona_item_ids": [str(item_id) for item_id in chat_response.record.used_persona_item_ids],
                "used_raw_source_ids": [str(source_id) for source_id in chat_response.record.used_raw_source_ids],
                "broken_persona_item_ids": [str(item_id) for item_id in broken_chat_persona_ids],
                "broken_raw_source_ids": [str(source_id) for source_id in broken_chat_raw_ids],
            },
            action_hint="检查 persona_chat 的 _select_context_items/_select_raw_sources 和 runtime_persona_items 过滤。",
        )
    )
    candidate = chat_response.candidate_evidence
    checks.append(
        _check(
            "third_person_candidate_isolated",
            "第三人称聊天候选隔离",
            candidate.get("created") is True
            and bool(candidate.get("raw_source_id"))
            and bool(candidate.get("uncertain_item_id"))
            and bool(candidate.get("question_target_id")),
            expected="第三人称新增记忆只能进入 raw_source + uncertain_item + question_target。",
            actual=f"candidate={candidate}",
            evidence={"chat_record_id": str(chat_response.record.id), "candidate": candidate},
            action_hint="检查 third_person_candidate 的 write_rules 和 chat_candidate_workflow。",
            blocked=candidate.get("created") is not True,
        )
    )

    uncertain_items = list_uncertain_items(profile_id, include_closed=True)
    question_targets = list_question_targets(profile_id, include_closed=True)
    checks.append(
        _check(
            "candidate_not_persona_item",
            "候选记忆未直写 persona",
            len(list_persona_items(profile_id, include_hidden=True)) == persona_after,
            expected="第三人称候选不得直接新增 persona_items。",
            actual=(
                f"persona_after_ingest={persona_after}, "
                f"persona_after_chat={len(list_persona_items(profile_id, include_hidden=True))}"
            ),
            evidence={
                "uncertain_count": len(uncertain_items),
                "question_count": len(question_targets),
            },
            action_hint="确保 third_person_candidate.write_rules.persona_item=false。",
        )
    )

    skill = generate_skill_for_profile(profile_id, include_audit_units=True)
    skill_persona_item_ids = [
        unit.persona_item_id
        for unit in skill.evidence_units
    ]
    skill_raw_source_ids = [
        unit.source_id
        for unit in skill.evidence_units
        if unit.source_id is not None
    ]
    if skill_persona_item_ids:
        record_monitoring_event(
            event_type="skill_generation",
            status="success" if skill.skill_markdown.strip() else "failed",
            profile_id=profile_id,
            subject_id=str(run_id),
            workflow="acceptance_e2e_runtime_sample",
            output_summary="acceptance runtime sample for unsupported memory metric",
            used_persona_item_ids=skill_persona_item_ids,
            used_raw_source_ids=skill_raw_source_ids,
            metadata={
                "acceptance_run_id": str(run_id),
                "skill_markdown_present": bool(skill.skill_markdown.strip()),
                "evidence_unit_count": len(skill.evidence_units),
                "audit_count": len(skill.audit_report),
            },
        )
    active_raw_source_ids = {source.id for source in list_raw_sources(profile_id)}
    unsupported_runtime_units = [
        unit
        for unit in skill.evidence_units
        if (unit.usage.can_retrieve or unit.usage.can_generate_style or unit.usage.can_state_as_fact)
        and (unit.source_id is None or unit.source_id not in active_raw_source_ids or unit.profile_id != profile_id)
    ]
    fact_unsafe_units = [
        unit
        for unit in skill.evidence_units
        if unit.usage.can_state_as_fact
        and (unit.usage.audit_only or unit.usage.needs_question or unit.source_id not in active_raw_source_ids)
    ]
    checks.append(
        _check(
            "skill_runtime_generated",
            "Skill 运行包可生成",
            bool(skill.skill_markdown.strip()),
            expected="Skill 生成返回非空 markdown；严格模式下最好有 evidence_units。",
            actual=f"markdown={bool(skill.skill_markdown.strip())}, evidence_units={len(skill.evidence_units)}",
            evidence={"evidence_unit_count": len(skill.evidence_units), "audit_count": len(skill.audit_report)},
            action_hint="检查 raw/persona 数据是否足够，或 Skill workflow 是否写入监控日志。",
            blocked=not skill.skill_markdown.strip(),
        )
    )
    checks.append(
        _check(
            "skill_runtime_units_evidence_bound",
            "Skill runtime units 证据链硬门",
            not unsupported_runtime_units,
            module="skill_generation_workflow",
            record_ids=[unit.unit_id for unit in unsupported_runtime_units[:50]],
            reason="Skill runtime units that can retrieve, style, or state facts must have live raw evidence.",
            expected="所有可运行 evidence_units 都指向当前 profile 未删除 raw_source。",
            actual=f"evidence_units={len(skill.evidence_units)}, unsupported_runtime_units={len(unsupported_runtime_units)}",
            evidence={
                "unsupported_unit_ids": [unit.unit_id for unit in unsupported_runtime_units[:20]],
                "unsupported_persona_item_ids": [str(unit.persona_item_id) for unit in unsupported_runtime_units[:20]],
            },
            action_hint="检查 list_runtime_persona_items 与 Skill generation 的 source_deleted/user_policy 使用规则。",
        )
    )
    checks.append(
        _check(
            "skill_fact_units_safe",
            "Skill fact usage flags 硬门",
            not fact_unsafe_units,
            module="skill_generation_workflow",
            record_ids=[unit.unit_id for unit in fact_unsafe_units[:50]],
            reason="Audit-only, needs-question, or source-missing units cannot be stated as facts.",
            expected="can_state_as_fact=true 的 unit 不得 audit_only、needs_question 或缺失 raw_source。",
            actual=f"fact_unsafe_units={len(fact_unsafe_units)}",
            evidence={"unsafe_unit_ids": [unit.unit_id for unit in fact_unsafe_units[:20]]},
            action_hint="调整 usage flags 或把该条降级为 caution/audit，不要进入事实表达。",
        )
    )

    report = build_monitoring_report(profile_id=profile_id)
    metrics_with_attribution = [
        metric.metric_key
        for metric in report.metrics
        if metric.attribution and metric.attribution_note and metric.action_hint
    ]
    checks.append(
        _check(
            "monitoring_attribution_present",
            "监控归因可复算",
            len(metrics_with_attribution) == len(report.metrics),
            expected="每个监控指标都返回 attribution、attribution_note、action_hint。",
            actual=f"metrics={len(report.metrics)}, with_attribution={len(metrics_with_attribution)}",
            evidence={"overall_level": report.overall_level, "metrics": metrics_with_attribution},
            action_hint="检查 monitoring_attribution feature policy 和 ATTRIBUTION_ALGORITHMS。",
        )
    )

    runtime_metric = next(
        (metric for metric in report.metrics if metric.metric_key == "runtime_unsupported_memory_rate"),
        None,
    )
    empty_runtime_sample_accepted = False
    runtime_gate_empty_sample_evidence: dict[str, object] = {}
    if runtime_metric is not None and runtime_metric.rate is None:
        empty_runtime_sample_accepted, runtime_gate_empty_sample_evidence = _runtime_gate_accepts_empty_runtime_sample(profile_id)
    runtime_unsupported_memory_ok = runtime_metric is not None and (
        runtime_metric.rate == 0
        or (
            runtime_metric.rate is None
            and runtime_metric.numerator == 0
            and runtime_metric.denominator == 0
            and runtime_metric.missing_data_reason == "no_runtime_persona_item_usage"
            and empty_runtime_sample_accepted
        )
    )
    runtime_unsupported_memory_blocked = runtime_metric is None or (
        runtime_metric.rate is None and not empty_runtime_sample_accepted
    )
    checks.append(
        _check(
            "runtime_unsupported_memory_strict",
            "无证据记忆运行态比例可审计",
            runtime_unsupported_memory_ok,
            expected="该指标必须可复算；有样本时比例必须为 0，缺样本时必须明确归因为缺运行事件。",
            actual=(
                "missing metric"
                if runtime_metric is None
                else (
                    f"status={runtime_metric.status}, rate={runtime_metric.rate}, "
                    f"denominator={runtime_metric.denominator}, "
                    f"empty_runtime_sample_accepted={empty_runtime_sample_accepted}, "
                    f"attribution={runtime_metric.attribution}"
                )
            ),
            evidence={
                "runtime_metric": runtime_metric.model_dump(mode="json") if runtime_metric else {},
                "runtime_gate_empty_sample": runtime_gate_empty_sample_evidence,
            },
            action_hint="如果 numerator>0，先修复运行态过滤；如果 denominator=0，先跑真实聊天或 Skill。",
            blocked=runtime_unsupported_memory_blocked,
        )
    )

    record_monitoring_event(
        event_type="acceptance",
        status="success" if _overall(checks) == "pass" else "blocked",
        profile_id=profile_id,
        subject_id=str(run_id),
        workflow="acceptance_e2e",
        output_summary=f"overall={_overall(checks)}, checks={len(checks)}",
        used_raw_source_ids=[raw_source_id] if raw_source_id else [],
        metadata={
            "acceptance_run_id": str(run_id),
            "overall": _overall(checks),
            "summary": dict(Counter(check.status for check in checks)),
        },
    )
    return _finish(
        run_id=run_id,
        started_at=started_at,
        policy_key="acceptance_e2e",
        profile_id=profile_id,
        created_profile_id=created_profile_id,
        checks=checks,
    )


ACCEPTANCE_ALGORITHMS: dict[str, AcceptanceAlgorithm] = {
    "api_smoke_v1": _api_smoke_v1,
}


def _legacy_run_acceptance(payload: AcceptanceRunRequest) -> AcceptanceRunResponse:
    policy = get_feature_policy("acceptance_e2e")
    algorithm = ACCEPTANCE_ALGORITHMS.get(policy.algorithm_key)
    if algorithm is None:
        now = _now()
        check = AcceptanceCheckResult(
            key="algorithm_registered",
            name="验收算法已注册",
            status="blocked",
            expected="feature policy algorithm_key 必须在 ACCEPTANCE_ALGORITHMS 注册。",
            actual=f"unsupported_algorithm_key:{policy.algorithm_key}",
            action_hint="恢复 api_smoke_v1，或先注册新的验收算法。",
        )
        return AcceptanceRunResponse(
            run_id=uuid4(),
            started_at=now,
            finished_at=now,
            feature_policy=policy,
            overall_status="blocked",
            profile_id=payload.profile_id,
            algorithm_key=policy.algorithm_key,
            strictness=policy.strictness,
            checks=[check],
            summary={"blocked": 1, "total": 1},
        )
    return algorithm(payload)


# Keep this final definition schema-first. It overrides the legacy branch above so
# unsupported algorithm errors include the same audit fields as normal checks.
def run_acceptance(payload: AcceptanceRunRequest) -> AcceptanceRunResponse:
    policy = get_feature_policy("acceptance_e2e")
    algorithm = ACCEPTANCE_ALGORITHMS.get(policy.algorithm_key)
    if payload.profile_id is not None:
        now = _now()
        check = _check(
            "acceptance_requires_isolated_data_dir",
            "严苛验收必须使用隔离数据目录",
            False,
            module="acceptance_runner",
            record_ids=[str(payload.profile_id)],
            reason="The E2E acceptance flow creates profiles, raw_sources, chat_records, uncertain_items, and monitoring events.",
            expected="不要对真实 profile 直接运行会写数据的 E2E 验收；使用独立临时数据目录。",
            actual=f"profile_id={payload.profile_id}",
            action_hint="不传 profile_id 运行严苛验收；需要检查真实档案时使用只读 self-check / integrity / runtime diagnostics。",
            blocked=True,
        )
        return AcceptanceRunResponse(
            run_id=uuid4(),
            started_at=now,
            finished_at=now,
            feature_policy=policy,
            overall_status="blocked",
            profile_id=payload.profile_id,
            algorithm_key=policy.algorithm_key,
            strictness=policy.strictness,
            checks=[check],
            summary={"blocked": 1, "total": 1},
        )
    if algorithm is None:
        now = _now()
        check = _check(
            "algorithm_registered",
            "验收算法已注册",
            False,
            module="acceptance_runner",
            record_ids=[policy.algorithm_key],
            reason="The configured acceptance algorithm is not registered in ACCEPTANCE_ALGORITHMS.",
            expected="feature policy algorithm_key must be registered in ACCEPTANCE_ALGORITHMS.",
            actual=f"unsupported_algorithm_key:{policy.algorithm_key}",
            action_hint="恢复 api_smoke_v1，或先注册新的验收算法。",
            blocked=True,
        )
        return AcceptanceRunResponse(
            run_id=uuid4(),
            started_at=now,
            finished_at=now,
            feature_policy=policy,
            overall_status="blocked",
            profile_id=payload.profile_id,
            algorithm_key=policy.algorithm_key,
            strictness=policy.strictness,
            checks=[check],
            summary={"blocked": 1, "total": 1},
        )
    isolation_path = data_dir() / "acceptance_runs" / uuid4().hex
    isolated_payload = payload.model_copy(update={"profile_id": None, "create_isolated_profile": True})
    cleanup_error = ""
    response: AcceptanceRunResponse | None = None
    try:
        with use_data_dir(isolation_path):
            response = algorithm(isolated_payload)
    finally:
        try:
            shutil.rmtree(isolation_path)
        except FileNotFoundError:
            pass
        except OSError as exc:
            cleanup_error = str(exc)
    assert response is not None
    isolation_check = _check(
        "acceptance_data_dir_isolated",
        "严苛验收数据隔离",
        cleanup_error == "",
        module="acceptance_runner",
        reason="Acceptance creates synthetic profiles and derived records, so they must not appear in the main UI/store.",
        expected="本次验收在临时数据目录内完成，并在结束后删除。",
        actual=f"isolation_path={isolation_path}, cleanup_error={cleanup_error or 'none'}",
        evidence={"isolation_path": str(isolation_path), "cleaned": cleanup_error == ""},
        action_hint="如果清理失败，手动删除该临时目录后再运行验收。",
        warning=bool(cleanup_error),
    )
    return _response_with_checks(response, [isolation_check, *response.checks])
