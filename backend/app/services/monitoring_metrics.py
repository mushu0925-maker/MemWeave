from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Callable
from uuid import UUID

from app.schemas.chat import ChatRecord
from app.schemas.clarification import QuestionTargetSchema, UncertainItemSchema
from app.schemas.monitoring import MonitoringAttribution, MonitoringHealthLevel, MonitoringMetricConfig, MonitoringMetricResult, MonitoringReport
from app.schemas.monitoring import MonitoringMetricStatus
from app.schemas.persona_item import PersonaItemSchema
from app.schemas.raw_source import RawSourceSchema
from app.services.chat_store import list_chat_records
from app.services.feature_policy_store import get_feature_policy
from app.services.monitoring_store import list_metric_configs, list_monitoring_events
from app.services.persona_item_store import list_persona_items
from app.services.profile_store import list_profiles
from app.services.raw_source_store import list_raw_sources
from app.services.uncertainty_store import list_question_targets, list_uncertain_items


MetricAlgorithm = Callable[[MonitoringMetricConfig, UUID | None], MonitoringMetricResult]
AttributionAlgorithm = Callable[[MonitoringMetricResult], tuple[MonitoringAttribution, str, str]]


def _now() -> datetime:
    return datetime.now(UTC)


def _cutoff(config: MonitoringMetricConfig) -> datetime:
    return _now() - timedelta(days=config.window_days)


def _in_window(value: datetime, config: MonitoringMetricConfig) -> bool:
    return value >= _cutoff(config)


def _id(value: object) -> str:
    return str(value)


def _limited(values: list[str], config: MonitoringMetricConfig) -> list[str]:
    return values[: config.sample_limit]


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def _sample_quality(status: MonitoringMetricStatus, denominator: int) -> str:
    if status == "disabled":
        return "disabled"
    if status == "blocked":
        return "blocked"
    if status == "insufficient_ground_truth":
        return "insufficient_ground_truth"
    if status == "insufficient_data" or denominator <= 0:
        return "insufficient_data"
    return "sufficient"


def _strict_acceptance(
    *,
    config: MonitoringMetricConfig,
    status: MonitoringMetricStatus,
    level: MonitoringHealthLevel,
    denominator: int,
) -> bool:
    return config.enabled and denominator > 0 and status == "ok" and level in {"ok", "audit"}


def _metadata_bool(value: object) -> bool:
    return value is True or value == "true" or value == "True"


def _metadata_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def _raw_source_maps(profile_id: UUID | None = None) -> tuple[dict[UUID, RawSourceSchema], set[UUID]]:
    sources = list_raw_sources(profile_id, include_deleted=True) if profile_id else list_raw_sources(include_deleted=True)
    source_by_id = {source.id: source for source in sources}
    active_source_ids = {
        source.id
        for source in sources
        if source.deleted_at is None and (profile_id is None or source.profile_id == profile_id)
    }
    return source_by_id, active_source_ids


def _all_persona_items(profile_id: UUID | None = None) -> list[PersonaItemSchema]:
    return list_persona_items(profile_id, include_hidden=True) if profile_id else list_persona_items(include_hidden=True)


def _all_uncertain_items(profile_id: UUID | None = None) -> list[UncertainItemSchema]:
    return list_uncertain_items(profile_id, include_closed=True)


def _all_question_targets(profile_id: UUID | None = None) -> list[QuestionTargetSchema]:
    return list_question_targets(profile_id, include_closed=True)


def _all_chat_records(profile_id: UUID | None = None) -> list[ChatRecord]:
    if profile_id is not None:
        return list_chat_records(profile_id, limit=10_000)
    records: list[ChatRecord] = []
    profile_ids = {profile.id for profile in list_profiles()}
    profile_ids.update(item.profile_id for item in list_persona_items(include_hidden=True))
    profile_ids.update(source.profile_id for source in list_raw_sources(include_deleted=True) if source.profile_id is not None)
    for item_profile_id in profile_ids:
        records.extend(list_chat_records(item_profile_id, limit=10_000))
    return records


def _persona_item_has_valid_evidence(
    item: PersonaItemSchema,
    source_by_id: dict[UUID, RawSourceSchema],
) -> bool:
    if item.status in {"hidden", "forgotten", "deleted"}:
        return False
    if item.source_id is None:
        return False
    source = source_by_id.get(item.source_id)
    if source is None or source.deleted_at is not None:
        return False
    return source.profile_id == item.profile_id


def _level_for_rate(
    *,
    config: MonitoringMetricConfig,
    status: MonitoringMetricStatus,
    rate: float | None,
) -> MonitoringHealthLevel:
    if status == "disabled":
        return "disabled"
    if config.strictness == "audit_only":
        return "audit"
    if status in {"insufficient_ground_truth", "insufficient_data"}:
        if config.fail_policy == "fail_closed":
            return "blocker"
        if config.fail_policy == "warn":
            return "warning"
        return "unknown"
    if status == "blocked":
        return "blocker" if config.fail_policy == "fail_closed" else "warning"
    if rate is None:
        return "unknown"

    if config.direction == "lower_is_better":
        blocker_max = config.thresholds.get("blocker_max_rate")
        warning_max = config.thresholds.get("warning_max_rate")
        if blocker_max is not None and rate > blocker_max:
            return "blocker"
        if warning_max is not None and rate > warning_max:
            return "warning"
        return "ok"

    blocker_min = config.thresholds.get("blocker_min_rate")
    warning_min = config.thresholds.get("warning_min_rate")
    if blocker_min is not None and rate < blocker_min:
        return "blocker"
    if warning_min is not None and rate < warning_min:
        return "warning"
    return "ok"


def _result(
    *,
    config: MonitoringMetricConfig,
    numerator: int,
    denominator: int,
    status: MonitoringMetricStatus,
    calculation_note: str,
    sample_ids: list[str] | None = None,
    problem_sample_ids: list[str] | None = None,
    missing_data_reason: str = "",
    attribution: MonitoringAttribution = "not_applicable",
    attribution_note: str = "",
    action_hint: str = "",
) -> MonitoringMetricResult:
    rate = _rate(numerator, denominator)
    level = _level_for_rate(config=config, status=status, rate=rate)
    sample_quality = _sample_quality(status, denominator)
    return MonitoringMetricResult(
        metric_key=config.metric_key,
        name=config.name,
        numerator=numerator,
        denominator=denominator,
        rate=rate,
        status=status,
        level=level,
        calculation_note=calculation_note,
        sample_ids=_limited(sample_ids or [], config),
        problem_sample_ids=_limited(problem_sample_ids or [], config),
        missing_data_reason=missing_data_reason,
        sample_quality=sample_quality,  # type: ignore[arg-type]
        strict_acceptance=_strict_acceptance(
            config=config,
            status=status,
            level=level,
            denominator=denominator,
        ),
        attribution=attribution,
        attribution_note=attribution_note,
        action_hint=action_hint,
        algorithm_key=config.algorithm_key,
        strictness=config.strictness,
        thresholds=config.thresholds,
        window_days=config.window_days,
        sample_limit=config.sample_limit,
        updated_at=_now(),
    )


def _disabled_result(config: MonitoringMetricConfig) -> MonitoringMetricResult:
    return _result(
        config=config,
        numerator=0,
        denominator=0,
        status="disabled",
        calculation_note="该指标已在后端配置中关闭，不参与总览健康状态。",
    )


def _unsupported_algorithm_result(config: MonitoringMetricConfig) -> MonitoringMetricResult:
    return _result(
        config=config,
        numerator=0,
        denominator=0,
        status="blocked",
        calculation_note="该指标配置了当前后端不支持的 algorithm_key。",
        missing_data_reason=f"unsupported_algorithm_key:{config.algorithm_key}",
    )


def _default_attribution(result: MonitoringMetricResult) -> tuple[MonitoringAttribution, str, str]:
    if result.status == "disabled" or result.level in {"ok", "audit", "disabled"}:
        return (
            "not_applicable",
            "当前指标没有需要归因的阻断问题。",
            "保持现有配置，继续观察后续真实运行样本。",
        )

    reason = result.missing_data_reason
    if reason.startswith("unsupported_algorithm_key"):
        return (
            "configuration_issue",
            "当前指标配置了后端未注册的 algorithm_key。",
            "在后端监控配置里恢复默认算法，或先注册新的指标算法再切换。",
        )

    if reason in {
        "no_skill_generation_attempt_events",
        "no_successful_chat_records",
        "no_runtime_persona_item_usage",
    }:
        return (
            "missing_runtime_event",
            "当前窗口缺少运行时事件日志，不能判断真实质量。",
            "执行一次对应真实流程：生成 Skill、完成聊天，或让运行态记录 persona item 使用。",
        )

    if reason in {
        "no_confirmed_question_or_keep_correct_samples",
        "no_low_confidence_candidates",
        "no_uncertain_item_actions",
        "no_correct_actions",
    }:
        return (
            "history_data_issue",
            "当前窗口缺少可复算的用户确认、纠错或低置信样本。",
            "用真实追问/确认/纠错样本补齐金标准；不要用 AI 自评分冒充准确率。",
        )

    if result.metric_key == "runtime_unsupported_memory_rate" and result.numerator > 0:
        return (
            "real_runtime_bug",
            "已有无证据链或禁用策略的 persona item 进入 chat/Skill 运行态。",
            "先修复运行态过滤和证据链，再重新生成 Skill 或重新聊天验证。",
        )

    if result.problem_sample_ids:
        if result.metric_key in {
            "memory_extraction_verified_pass_rate",
            "user_confirmation_pass_rate",
            "incorrect_memory_correction_rate",
        }:
            return (
                "history_data_issue",
                "问题样本集中在人工确认、纠错或历史分类链路。",
                "逐条打开 problem_sample_ids，检查 target_group/library_key、raw_source 和用户动作是否一致。",
            )
        return (
            "real_runtime_bug",
            "当前指标已经有可定位的问题样本。",
            "优先修复 problem_sample_ids 指向的样本链路，再复跑该单项指标。",
        )

    if result.status in {"insufficient_data", "insufficient_ground_truth"}:
        return (
            "history_data_issue",
            "数据不足导致指标不能给出严格结论。",
            "补充真实样本或临时把该指标改成 audit_only，不要把缺数据当通过。",
        )

    if result.status == "blocked":
        return (
            "mixed",
            "该指标处于阻断状态，但缺少更细样本定位。",
            "先检查 missing_data_reason，再检查最近监控事件和写入策略。",
        )

    return (
        "mixed",
        "需要结合样本和配置继续判断。",
        "检查指标配置、样本 id、近期事件日志和对应模块写入规则。",
    )


ATTRIBUTION_ALGORITHMS: dict[str, AttributionAlgorithm] = {
    "metric_attribution_v1": _default_attribution,
}


def _apply_attribution(result: MonitoringMetricResult) -> MonitoringMetricResult:
    try:
        policy = get_feature_policy("monitoring_attribution")
    except Exception:
        policy = None

    if policy is not None and not policy.enabled:
        return result.model_copy(
            update={
                "attribution": "not_applicable",
                "attribution_note": "监控归因模块已在 feature policy 中关闭。",
                "action_hint": "如需自动归因，请重新开启 monitoring_attribution。",
            }
        )

    algorithm_key = policy.algorithm_key if policy is not None else "metric_attribution_v1"
    algorithm = ATTRIBUTION_ALGORITHMS.get(algorithm_key)
    if algorithm is None:
        return result.model_copy(
            update={
                "attribution": "configuration_issue",
                "attribution_note": f"监控归因 algorithm_key 未注册：{algorithm_key}",
                "action_hint": "在 feature policies 中恢复 metric_attribution_v1，或注册新的归因算法。",
            }
        )

    attribution, note, hint = algorithm(result)
    return result.model_copy(
        update={
            "attribution": attribution,
            "attribution_note": note,
            "action_hint": hint,
        }
    )


def _memory_extraction_verified_pass_rate(config: MonitoringMetricConfig, profile_id: UUID | None) -> MonitoringMetricResult:
    questions = [
        question
        for question in _all_question_targets(profile_id)
        if _in_window(question.updated_at, config)
        and "classification_succeeded" in question.metadata
    ]
    uncertain_actions = [
        item
        for item in _all_uncertain_items(profile_id)
        if _in_window(item.updated_at, config)
        and item.metadata.get("confirmation_action") in {"keep", "correct"}
    ]
    denominator = len(questions) + len(uncertain_actions)
    def question_passes(question: QuestionTargetSchema) -> bool:
        if config.strictness == "relaxed":
            return _metadata_bool(question.metadata.get("classification_succeeded"))
        if question.status != "resolved" or not _metadata_bool(question.metadata.get("classification_succeeded")):
            return False
        if not _metadata_bool(question.metadata.get("target_match_succeeded")):
            return False
        if config.strictness == "strict":
            return bool(question.metadata.get("persona_item_ids"))
        return True

    def action_passes(item: UncertainItemSchema) -> bool:
        if config.strictness == "relaxed":
            return item.status == "resolved"
        if item.status != "resolved" or not _metadata_bool(item.metadata.get("classification_succeeded")):
            return False
        if config.strictness == "strict":
            return _metadata_int(item.metadata.get("new_persona_items")) > 0 and isinstance(
                item.metadata.get("confirmation_raw_source_id"), str
            )
        return _metadata_int(item.metadata.get("new_persona_items")) > 0

    question_pass = [question for question in questions if question_passes(question)]
    action_pass = [item for item in uncertain_actions if action_passes(item)]
    sample_ids = [f"question:{question.id}" for question in question_pass]
    sample_ids.extend(f"uncertain:{item.id}" for item in action_pass)
    problem_ids = [
        f"question:{question.id}"
        for question in questions
        if question not in question_pass
    ]
    problem_ids.extend(f"uncertain:{item.id}" for item in uncertain_actions if item not in action_pass)
    if denominator == 0:
        return _result(
            config=config,
            numerator=0,
            denominator=0,
            status="insufficient_ground_truth",
            calculation_note="没有用户确认后的可验证样本，不能把 AI 自评分当作真实抽取准确率。",
            missing_data_reason="no_confirmed_question_or_keep_correct_samples",
        )
    return _result(
        config=config,
        numerator=len(question_pass) + len(action_pass),
        denominator=denominator,
        status="ok",
        calculation_note="分子=用户确认后分类成功且命中目标库的样本；分母=回答追问或 keep/correct 的人工确认样本。",
        sample_ids=sample_ids,
        problem_sample_ids=problem_ids,
    )


def _low_confidence_interception_rate(config: MonitoringMetricConfig, profile_id: UUID | None) -> MonitoringMetricResult:
    threshold = config.thresholds.get("low_confidence_max", 0.6)
    source_by_id, _active_source_ids = _raw_source_maps(profile_id)
    low_persona = [
        item
        for item in _all_persona_items(profile_id)
        if _in_window(item.updated_at, config) and item.confidence <= threshold
    ]
    low_uncertain = [
        item
        for item in _all_uncertain_items(profile_id)
        if _in_window(item.updated_at, config) and item.confidence <= threshold
    ]
    def low_item_leaked(item: PersonaItemSchema) -> bool:
        if not _persona_item_has_valid_evidence(item, source_by_id):
            return False
        if config.strictness == "relaxed":
            return item.status == "active"
        if config.strictness == "strict":
            return item.status in {"active", "candidate", "rejected_until_confirmed"}
        return item.status in {"active", "candidate"}

    leaked_persona = [item for item in low_persona if low_item_leaked(item)]
    intercepted_persona = [item for item in low_persona if item not in leaked_persona]
    numerator = len(low_uncertain) + len(intercepted_persona)
    denominator = len(low_uncertain) + len(low_persona)
    if denominator == 0:
        return _result(
            config=config,
            numerator=0,
            denominator=0,
            status="insufficient_data",
            calculation_note="当前窗口内没有低置信候选样本。",
            missing_data_reason="no_low_confidence_candidates",
        )
    return _result(
        config=config,
        numerator=numerator,
        denominator=denominator,
        status="ok",
        calculation_note="分子=进入 uncertain/question 或未进入运行态的低置信样本；分母=低置信 persona/uncertain 样本。",
        sample_ids=[f"uncertain:{item.id}" for item in low_uncertain] + [f"persona:{item.id}" for item in intercepted_persona],
        problem_sample_ids=[f"persona:{item.id}" for item in leaked_persona],
    )


def _user_confirmation_pass_rate(config: MonitoringMetricConfig, profile_id: UUID | None) -> MonitoringMetricResult:
    actions = [
        item
        for item in _all_uncertain_items(profile_id)
        if _in_window(item.updated_at, config) and isinstance(item.metadata.get("confirmation_action"), str)
    ]
    def action_passes(item: UncertainItemSchema) -> bool:
        action = item.metadata.get("confirmation_action")
        if action not in {"keep", "correct"} or item.status != "resolved":
            return False
        if config.strictness == "relaxed":
            return True
        if config.strictness == "strict":
            return _metadata_bool(item.metadata.get("classification_succeeded")) and _metadata_int(
                item.metadata.get("new_persona_items")
            ) > 0
        return _metadata_bool(item.metadata.get("classification_succeeded")) or isinstance(
            item.metadata.get("confirmation_raw_source_id"), str
        )

    passed = [item for item in actions if action_passes(item)]
    if not actions:
        return _result(
            config=config,
            numerator=0,
            denominator=0,
            status="insufficient_data",
            calculation_note="当前窗口内没有用户确认动作。",
            missing_data_reason="no_uncertain_item_actions",
        )
    return _result(
        config=config,
        numerator=len(passed),
        denominator=len(actions),
        status="ok",
        calculation_note="分子=keep/correct 且 resolved 的确认项；分母=keep/correct/downrank/hide/forget 全部动作。",
        sample_ids=[f"uncertain:{item.id}:{item.metadata.get('confirmation_action')}" for item in passed],
        problem_sample_ids=[f"uncertain:{item.id}:{item.metadata.get('confirmation_action')}" for item in actions if item not in passed],
    )


def _incorrect_memory_correction_rate(config: MonitoringMetricConfig, profile_id: UUID | None) -> MonitoringMetricResult:
    corrections = [
        item
        for item in _all_uncertain_items(profile_id)
        if _in_window(item.updated_at, config) and item.metadata.get("confirmation_action") == "correct"
    ]
    def correction_passes(item: UncertainItemSchema) -> bool:
        has_raw_source = isinstance(item.metadata.get("confirmation_raw_source_id"), str) and bool(
            str(item.metadata.get("confirmation_raw_source_id")).strip()
        )
        if item.status != "resolved" or item.metadata.get("use_policy") != "use_corrected_claim":
            return False
        if config.strictness == "relaxed":
            return has_raw_source
        if config.strictness == "strict":
            return (
                has_raw_source
                and isinstance(item.metadata.get("corrected_claim"), str)
                and _metadata_bool(item.metadata.get("classification_succeeded"))
                and _metadata_int(item.metadata.get("new_persona_items")) > 0
            )
        return has_raw_source and isinstance(item.metadata.get("corrected_claim"), str)

    passed = [item for item in corrections if correction_passes(item)]
    if not corrections:
        return _result(
            config=config,
            numerator=0,
            denominator=0,
            status="insufficient_data",
            calculation_note="当前窗口内没有 correct 纠错动作。",
            missing_data_reason="no_correct_actions",
        )
    return _result(
        config=config,
        numerator=len(passed),
        denominator=len(corrections),
        status="ok",
        calculation_note="分子=correct 后保存修正 raw_source 且 use_policy=use_corrected_claim 的样本；分母=所有 correct 动作。",
        sample_ids=[f"uncertain:{item.id}" for item in passed],
        problem_sample_ids=[f"uncertain:{item.id}" for item in corrections if item not in passed],
    )


def _chat_record_has_valid_retrieval(record: ChatRecord, config: MonitoringMetricConfig) -> bool:
    source_by_id, _active_source_ids = _raw_source_maps(record.profile_id)
    item_by_id = {item.id: item for item in _all_persona_items(record.profile_id)}
    if not record.used_persona_item_ids and not record.used_raw_source_ids:
        return False
    if config.strictness == "relaxed":
        return True
    if config.strictness == "strict" and not record.used_persona_item_ids:
        return False
    for item_id in record.used_persona_item_ids:
        item = item_by_id.get(item_id)
        if item is None or not _persona_item_has_valid_evidence(item, source_by_id):
            return False
    for source_id in record.used_raw_source_ids:
        source = source_by_id.get(source_id)
        if source is None or source.deleted_at is not None or source.profile_id != record.profile_id:
            return False
    return True


def _chat_retrieval_hit_rate(config: MonitoringMetricConfig, profile_id: UUID | None) -> MonitoringMetricResult:
    records = [
        record
        for record in _all_chat_records(profile_id)
        if _in_window(record.created_at, config)
        and record.model_call_status in {"success", "local"}
        and bool(record.assistant_message.strip())
    ]
    hits = [record for record in records if _chat_record_has_valid_retrieval(record, config)]
    if not records:
        return _result(
            config=config,
            numerator=0,
            denominator=0,
            status="insufficient_data",
            calculation_note="当前窗口内没有成功聊天记录。",
            missing_data_reason="no_successful_chat_records",
        )
    return _result(
        config=config,
        numerator=len(hits),
        denominator=len(records),
        status="ok",
        calculation_note="分子=成功聊天且命中有效 persona/raw evidence；分母=成功或本地成功聊天记录。",
        sample_ids=[f"chat:{record.id}" for record in hits],
        problem_sample_ids=[f"chat:{record.id}" for record in records if record not in hits],
    )


def _skill_generation_success_rate(config: MonitoringMetricConfig, profile_id: UUID | None) -> MonitoringMetricResult:
    events = [
        event
        for event in list_monitoring_events(event_type="skill_generation", profile_id=profile_id, limit=10_000)
        if _in_window(event.created_at, config)
    ]
    def skill_event_passes(event: object) -> bool:
        status_value = getattr(event, "status", None)
        metadata = getattr(event, "metadata", {})
        if status_value != "success":
            return False
        if config.strictness == "relaxed":
            return True
        markdown_present = metadata.get("skill_markdown_present") is True
        if config.strictness == "strict":
            return markdown_present and _metadata_int(metadata.get("evidence_unit_count")) > 0
        return markdown_present

    passed = [event for event in events if skill_event_passes(event)]
    if not events:
        return _result(
            config=config,
            numerator=0,
            denominator=0,
            status="insufficient_data",
            calculation_note="没有 Skill 生成尝试日志；保存过的版本不能代表尝试分母。",
            missing_data_reason="no_skill_generation_attempt_events",
        )
    return _result(
        config=config,
        numerator=len(passed),
        denominator=len(events),
        status="ok",
        calculation_note="分子=按当前 strictness 判定成功的 Skill 生成尝试；relaxed=无异常，normal=有 markdown，strict=有 markdown 且有 evidence unit；分母=Skill 生成尝试日志。",
        sample_ids=[f"event:{event.id}" for event in passed],
        problem_sample_ids=[f"event:{event.id}" for event in events if event not in passed],
    )


def _runtime_unsupported_memory_rate(config: MonitoringMetricConfig, profile_id: UUID | None) -> MonitoringMetricResult:
    source_by_id, _active_source_ids = _raw_source_maps(profile_id)
    item_by_id = {item.id: item for item in _all_persona_items(profile_id)}
    records = [
        record
        for record in _all_chat_records(profile_id)
        if _in_window(record.created_at, config)
    ]
    runtime_item_ids: list[UUID] = []
    for record in records:
        runtime_item_ids.extend(record.used_persona_item_ids)

    events = [
        event
        for event in list_monitoring_events(profile_id=profile_id, limit=10_000)
        if event.event_type in {"chat_skill_usage", "skill_generation"} and _in_window(event.created_at, config)
    ]
    for event in events:
        runtime_item_ids.extend(event.used_persona_item_ids)

    unsupported_ids: list[str] = []
    supported_count = 0
    for item_id in runtime_item_ids:
        item = item_by_id.get(item_id)
        if item is None or not _persona_item_has_valid_evidence(item, source_by_id):
            unsupported_ids.append(f"persona:{item_id}")
        else:
            supported_count += 1
    denominator = supported_count + len(unsupported_ids)
    if denominator == 0:
        return _result(
            config=config,
            numerator=0,
            denominator=0,
            status="insufficient_data",
            calculation_note="当前窗口内没有可统计的运行态 persona item 使用记录。",
            missing_data_reason="no_runtime_persona_item_usage",
        )
    return _result(
        config=config,
        numerator=len(unsupported_ids),
        denominator=denominator,
        status="ok",
        calculation_note="分子=进入 chat/Skill runtime 但证据链无效或策略禁用的 persona_items；分母=运行态使用的 persona_items。",
        sample_ids=[f"persona:{item_id}" for item_id in runtime_item_ids if f"persona:{item_id}" not in unsupported_ids],
        problem_sample_ids=unsupported_ids,
    )


ALGORITHMS: dict[str, dict[str, MetricAlgorithm]] = {
    "memory_extraction_verified_pass_rate": {
        "confirmed_target_match_v1": _memory_extraction_verified_pass_rate,
        "confirmed_action_proxy_v1": _memory_extraction_verified_pass_rate,
    },
    "low_confidence_interception_rate": {
        "uncertainty_gate_v1": _low_confidence_interception_rate,
        "confidence_threshold_only_v1": _low_confidence_interception_rate,
    },
    "user_confirmation_pass_rate": {
        "confirmation_action_v1": _user_confirmation_pass_rate,
    },
    "incorrect_memory_correction_rate": {
        "correction_action_v1": _incorrect_memory_correction_rate,
    },
    "chat_retrieval_hit_rate": {
        "chat_record_usage_v1": _chat_retrieval_hit_rate,
    },
    "skill_generation_success_rate": {
        "skill_attempt_event_v1": _skill_generation_success_rate,
    },
    "runtime_unsupported_memory_rate": {
        "runtime_evidence_chain_v1": _runtime_unsupported_memory_rate,
    },
}


def calculate_metric(metric_key: str, profile_id: UUID | None = None) -> MonitoringMetricResult:
    config = next((item for item in list_metric_configs() if item.metric_key == metric_key), None)
    if config is None:
        raise KeyError(metric_key)
    if not config.enabled:
        return _apply_attribution(_disabled_result(config))
    algorithm = ALGORITHMS.get(config.metric_key, {}).get(config.algorithm_key)
    if algorithm is None:
        return _apply_attribution(_unsupported_algorithm_result(config))
    try:
        return _apply_attribution(algorithm(config, profile_id))
    except Exception as exc:
        return _apply_attribution(
            _result(
                config=config,
                numerator=0,
                denominator=0,
                status="blocked",
                calculation_note="该指标计算失败，只阻断当前指标，不影响其他监控模块。",
                missing_data_reason=f"{type(exc).__name__}:{str(exc)[:240]}",
                attribution="real_runtime_bug",
                attribution_note="指标算法运行时异常。",
                action_hint="检查当前 metric_key 的算法实现、输入数据和配置阈值。",
            )
        )


def build_monitoring_report(profile_id: UUID | None = None) -> MonitoringReport:
    results = [calculate_metric(config.metric_key, profile_id=profile_id) for config in list_metric_configs()]
    active_levels = [result.level for result in results if result.level not in {"disabled", "audit"}]
    if "blocker" in active_levels:
        overall = "blocker"
    elif "warning" in active_levels:
        overall = "warning"
    elif active_levels and all(level == "ok" for level in active_levels):
        overall = "ok"
    else:
        overall = "unknown"
    summary = Counter(result.level for result in results)
    summary["total"] = len(results)
    return MonitoringReport(
        generated_at=_now(),
        profile_id=profile_id,
        overall_level=overall,
        summary=dict(summary),
        metrics=results,
    )
