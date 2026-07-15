from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.schemas.monitoring import MonitoringEvent, MonitoringEventStatus, MonitoringEventType
from app.schemas.monitoring import MonitoringMetricConfig, MonitoringMetricConfigUpdate
from app.services.local_database import read_json_file, update_json_file

MONITORING_CONFIG_STORE_FILE = "monitoring_settings.json"
MONITORING_EVENT_STORE_FILE = "monitoring_events.json"


def _now() -> datetime:
    return datetime.now(UTC)


def _default_metric_config(
    *,
    metric_key: str,
    name: str,
    description: str,
    algorithm_key: str,
    strictness: str = "normal",
    direction: str = "higher_is_better",
    thresholds: dict[str, float] | None = None,
    fail_policy: str = "warn",
) -> MonitoringMetricConfig:
    return MonitoringMetricConfig(
        metric_key=metric_key,
        name=name,
        description=description,
        algorithm_key=algorithm_key,
        strictness=strictness,  # type: ignore[arg-type]
        direction=direction,  # type: ignore[arg-type]
        thresholds=thresholds or {},
        fail_policy=fail_policy,  # type: ignore[arg-type]
        updated_at=_now(),
    )


DEFAULT_METRIC_CONFIGS: dict[str, MonitoringMetricConfig] = {
    "memory_extraction_verified_pass_rate": _default_metric_config(
        metric_key="memory_extraction_verified_pass_rate",
        name="记忆抽取人工验证通过率",
        description="只使用用户确认后的样本，不把 AI 自评分当真实准确率。",
        algorithm_key="confirmed_target_match_v1",
        thresholds={"warning_min_rate": 0.7, "blocker_min_rate": 0.5},
        fail_policy="warn",
    ),
    "low_confidence_interception_rate": _default_metric_config(
        metric_key="low_confidence_interception_rate",
        name="低置信记忆拦截率",
        description="低置信或不确定候选被拦截到 uncertain/question，且没有进入运行态的比例。",
        algorithm_key="uncertainty_gate_v1",
        thresholds={"low_confidence_max": 0.6, "warning_min_rate": 0.9, "blocker_min_rate": 0.75},
        fail_policy="fail_closed",
    ),
    "user_confirmation_pass_rate": _default_metric_config(
        metric_key="user_confirmation_pass_rate",
        name="用户确认通过率",
        description="keep/correct 后成功解决的确认项占所有确认动作的比例。",
        algorithm_key="confirmation_action_v1",
        thresholds={"warning_min_rate": 0.6, "blocker_min_rate": 0.35},
        fail_policy="warn",
    ),
    "incorrect_memory_correction_rate": _default_metric_config(
        metric_key="incorrect_memory_correction_rate",
        name="错误记忆修正率",
        description="correct 动作中成功保留修正 raw_source 并生成或关联修正结果的比例。",
        algorithm_key="correction_action_v1",
        thresholds={"warning_min_rate": 0.8, "blocker_min_rate": 0.5},
        fail_policy="warn",
    ),
    "chat_retrieval_hit_rate": _default_metric_config(
        metric_key="chat_retrieval_hit_rate",
        name="聊天检索命中率",
        description="成功聊天中命中 persona item 或 raw source，且引用证据有效的比例。",
        algorithm_key="chat_record_usage_v1",
        thresholds={"warning_min_rate": 0.75, "blocker_min_rate": 0.5},
        fail_policy="warn",
    ),
    "skill_generation_success_rate": _default_metric_config(
        metric_key="skill_generation_success_rate",
        name="Skill 生成成功率",
        description="Skill 生成尝试中成功生成运行包的比例，分母来自生成尝试日志。",
        algorithm_key="skill_attempt_event_v1",
        thresholds={"warning_min_rate": 0.9, "blocker_min_rate": 0.7},
        fail_policy="fail_closed",
    ),
    "runtime_unsupported_memory_rate": _default_metric_config(
        metric_key="runtime_unsupported_memory_rate",
        name="无证据记忆进入运行态比例",
        description="进入 chat/Skill runtime 的 persona_items 中证据链断裂或策略禁用的比例。",
        algorithm_key="runtime_evidence_chain_v1",
        strictness="strict",
        direction="lower_is_better",
        thresholds={"warning_max_rate": 0.0, "blocker_max_rate": 0.0},
        fail_policy="fail_closed",
    ),
}


def _read_config_records() -> dict[str, Any]:
    records = read_json_file(MONITORING_CONFIG_STORE_FILE, {})
    if isinstance(records, dict):
        return records
    return {}


def _read_event_records() -> list[dict[str, Any]]:
    records = read_json_file(MONITORING_EVENT_STORE_FILE, [])
    if isinstance(records, list):
        return records
    return []


def _coerce_config_records(records: Any) -> dict[str, Any]:
    return records if isinstance(records, dict) else {}


def _coerce_event_records(records: Any) -> list[dict[str, Any]]:
    return records if isinstance(records, list) else []


def _update_config_records(updater: Any) -> dict[str, Any]:
    return update_json_file(MONITORING_CONFIG_STORE_FILE, {}, lambda records: updater(_coerce_config_records(records)))


def _update_event_records(updater: Any) -> list[dict[str, Any]]:
    return update_json_file(MONITORING_EVENT_STORE_FILE, [], lambda records: updater(_coerce_event_records(records)))


def _config_from_record(record: dict[str, Any]) -> MonitoringMetricConfig:
    return MonitoringMetricConfig.model_validate(record)


def _event_from_record(record: dict[str, Any]) -> MonitoringEvent:
    return MonitoringEvent.model_validate(record)


def list_metric_configs() -> list[MonitoringMetricConfig]:
    def ensure_defaults(records: dict[str, Any]) -> dict[str, Any]:
        for metric_key, config in DEFAULT_METRIC_CONFIGS.items():
            if metric_key not in records:
                records[metric_key] = config.model_dump(mode="json")
        return records

    records = _update_config_records(ensure_defaults)
    configs = [_config_from_record(record) for record in records.values()]
    return sorted(configs, key=lambda config: config.metric_key)


def get_metric_config(metric_key: str) -> MonitoringMetricConfig:
    for config in list_metric_configs():
        if config.metric_key == metric_key:
            return config
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitoring metric config not found")


def update_metric_config(metric_key: str, payload: MonitoringMetricConfigUpdate) -> MonitoringMetricConfig:
    current = get_metric_config(metric_key)
    updated = current.model_copy(
        update={
            "enabled": payload.enabled if payload.enabled is not None else current.enabled,
            "algorithm_key": payload.algorithm_key if payload.algorithm_key is not None else current.algorithm_key,
            "strictness": payload.strictness if payload.strictness is not None else current.strictness,
            "thresholds": payload.thresholds if payload.thresholds is not None else current.thresholds,
            "window_days": payload.window_days if payload.window_days is not None else current.window_days,
            "sample_limit": payload.sample_limit if payload.sample_limit is not None else current.sample_limit,
            "fail_policy": payload.fail_policy if payload.fail_policy is not None else current.fail_policy,
            "updated_by": (payload.updated_by or "backend-dashboard").strip() or "backend-dashboard",
            "updated_at": _now(),
        }
    )
    _update_config_records(lambda records: {**records, metric_key: updated.model_dump(mode="json")})
    return updated


def reset_metric_config(metric_key: str) -> MonitoringMetricConfig:
    if metric_key not in DEFAULT_METRIC_CONFIGS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitoring metric config not found")
    default = DEFAULT_METRIC_CONFIGS[metric_key].model_copy(update={"updated_at": _now(), "updated_by": "system-reset"})
    _update_config_records(lambda records: {**records, metric_key: default.model_dump(mode="json")})
    return default


def record_monitoring_event(
    *,
    event_type: MonitoringEventType,
    status: MonitoringEventStatus,
    profile_id: UUID | None = None,
    raw_source_id: UUID | None = None,
    chat_record_id: UUID | None = None,
    skill_version_id: UUID | None = None,
    subject_id: str = "",
    workflow: str = "",
    provider: str = "",
    model_name: str | None = None,
    input_summary: str = "",
    output_summary: str = "",
    error: str = "",
    used_persona_item_ids: list[UUID] | None = None,
    used_raw_source_ids: list[UUID] | None = None,
    metadata: dict[str, Any] | None = None,
) -> MonitoringEvent:
    event = MonitoringEvent(
        event_type=event_type,
        status=status,
        profile_id=profile_id,
        raw_source_id=raw_source_id,
        chat_record_id=chat_record_id,
        skill_version_id=skill_version_id,
        subject_id=subject_id,
        workflow=workflow,
        provider=provider,
        model_name=model_name,
        input_summary=input_summary[:1000],
        output_summary=output_summary[:1000],
        error=error[:1000],
        used_persona_item_ids=used_persona_item_ids or [],
        used_raw_source_ids=used_raw_source_ids or [],
        metadata=metadata or {},
        created_at=_now(),
    )
    try:
        _update_event_records(lambda records: [*records, event.model_dump(mode="json")])
    except Exception:
        # Monitoring is a side channel. A log write failure must not break ingest/chat/skill flows.
        return event
    return event


def list_monitoring_events(
    *,
    event_type: MonitoringEventType | None = None,
    status: MonitoringEventStatus | None = None,
    profile_id: UUID | None = None,
    raw_source_id: UUID | None = None,
    chat_record_id: UUID | None = None,
    skill_version_id: UUID | None = None,
    subject_id: str | None = None,
    workflow: str | None = None,
    limit: int = 100,
) -> list[MonitoringEvent]:
    events: list[MonitoringEvent] = []
    subject_filter = subject_id.strip() if subject_id else ""
    workflow_filter = workflow.strip() if workflow else ""
    for record in _read_event_records():
        if event_type is not None and record.get("event_type") != event_type:
            continue
        if status is not None and record.get("status") != status:
            continue
        if profile_id is not None and record.get("profile_id") != str(profile_id):
            continue
        if raw_source_id is not None and record.get("raw_source_id") != str(raw_source_id):
            continue
        if chat_record_id is not None and record.get("chat_record_id") != str(chat_record_id):
            continue
        if skill_version_id is not None and record.get("skill_version_id") != str(skill_version_id):
            continue
        if subject_filter and record.get("subject_id") != subject_filter:
            continue
        if workflow_filter and record.get("workflow") != workflow_filter:
            continue
        events.append(_event_from_record(record))
    return sorted(events, key=lambda event: event.created_at, reverse=True)[:limit]


def get_monitoring_event(event_id: UUID) -> MonitoringEvent:
    for record in _read_event_records():
        if record.get("id") == str(event_id):
            return _event_from_record(record)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitoring event not found")
