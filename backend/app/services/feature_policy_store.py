from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status

from app.schemas.feature_policy import FeaturePolicy, FeaturePolicyUpdate, FeatureWriteRules
from app.services.local_database import read_json_file, update_json_file

FEATURE_POLICY_STORE_FILE = "feature_policies.json"


def _now() -> datetime:
    return datetime.now(UTC)


def _policy(
    *,
    feature_key: str,
    name: str,
    description: str,
    algorithm_key: str,
    strictness: str = "normal",
    write_rules: FeatureWriteRules | None = None,
    thresholds: dict[str, float] | None = None,
) -> FeaturePolicy:
    return FeaturePolicy(
        feature_key=feature_key,
        name=name,
        description=description,
        algorithm_key=algorithm_key,
        strictness=strictness,  # type: ignore[arg-type]
        write_rules=write_rules or FeatureWriteRules(),
        thresholds=thresholds or {},
        updated_at=_now(),
    )


DEFAULT_FEATURE_POLICIES: dict[str, FeaturePolicy] = {
    "acceptance_e2e": _policy(
        feature_key="acceptance_e2e",
        name="端到端严苛验收",
        description="通过公开 API 创建干净 profile 并验证 raw_source、persona_items、chat、Skill、monitoring 的完整链路。",
        algorithm_key="api_smoke_v1",
        strictness="strict",
        write_rules=FeatureWriteRules(
            raw_source=True,
            persona_item=True,
            uncertain_item=True,
            question_target=True,
            chat_record=True,
            skill_version=False,
            monitoring_event=True,
        ),
    ),
    "monitoring_attribution": _policy(
        feature_key="monitoring_attribution",
        name="监控 blocker 归因",
        description="把监控问题归类为历史数据、缺运行事件、真实运行 bug 或配置问题。",
        algorithm_key="metric_attribution_v1",
        strictness="strict",
        write_rules=FeatureWriteRules(monitoring_event=True),
    ),
    "chat_quality_validation": _policy(
        feature_key="chat_quality_validation",
        name="聊天质量验收",
        description="只读检查已有聊天记录的证据命中、第三人称边界、空回复和运行态日志，不主动新增聊天。",
        algorithm_key="chat_record_quality_v1",
        strictness="strict",
        write_rules=FeatureWriteRules(monitoring_event=True),
        thresholds={"warning_min_rate": 0.8, "blocker_min_rate": 0.6},
    ),
    "skill_quality_validation": _policy(
        feature_key="skill_quality_validation",
        name="Skill 质量验收",
        description="只读生成 Skill 预览并检查证据链、usage flags、question backlog 和无证据运行态比例，不保存 Skill 版本。",
        algorithm_key="skill_runtime_quality_v1",
        strictness="strict",
        write_rules=FeatureWriteRules(monitoring_event=True),
        thresholds={"warning_min_rate": 0.9, "blocker_min_rate": 0.75},
    ),
    "third_person_candidate": _policy(
        feature_key="third_person_candidate",
        name="第三者聊天候选证据",
        description="第三者聊天中新信息只能先入候选证据，不直接写稳定 persona_items。",
        algorithm_key="ai_judge_v1",
        strictness="strict",
        write_rules=FeatureWriteRules(
            raw_source=True,
            persona_item=False,
            uncertain_item=True,
            question_target=True,
            chat_record=True,
            monitoring_event=True,
        ),
    ),
    "event_memory_completion": _policy(
        feature_key="event_memory_completion",
        name="事件记忆补全",
        description="识别时间、地点、人物、事件、感受和证据缺口，并生成 targeted question。",
        algorithm_key="field_gap_v1",
        strictness="strict",
        write_rules=FeatureWriteRules(
            raw_source=False,
            persona_item=False,
            uncertain_item=True,
            question_target=True,
            monitoring_event=True,
        ),
        thresholds={"minimum_gap_count": 1},
    ),
}


def _read_records() -> dict[str, Any]:
    records = read_json_file(FEATURE_POLICY_STORE_FILE, {})
    if isinstance(records, dict):
        return records
    return {}


def _coerce_records(records: Any) -> dict[str, Any]:
    return records if isinstance(records, dict) else {}


def _update_records(updater: Any) -> dict[str, Any]:
    return update_json_file(FEATURE_POLICY_STORE_FILE, {}, lambda records: updater(_coerce_records(records)))


def _from_record(record: dict[str, Any]) -> FeaturePolicy:
    return FeaturePolicy.model_validate(record)


def list_feature_policies() -> list[FeaturePolicy]:
    def ensure_defaults(records: dict[str, Any]) -> dict[str, Any]:
        for feature_key, policy in DEFAULT_FEATURE_POLICIES.items():
            if feature_key not in records:
                records[feature_key] = policy.model_dump(mode="json")
        return records

    records = _update_records(ensure_defaults)
    return sorted((_from_record(record) for record in records.values()), key=lambda item: item.feature_key)


def get_feature_policy(feature_key: str) -> FeaturePolicy:
    for policy in list_feature_policies():
        if policy.feature_key == feature_key:
            return policy
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature policy not found")


def update_feature_policy(feature_key: str, payload: FeaturePolicyUpdate) -> FeaturePolicy:
    current = get_feature_policy(feature_key)
    updated = current.model_copy(
        update={
            "enabled": payload.enabled if payload.enabled is not None else current.enabled,
            "algorithm_key": payload.algorithm_key if payload.algorithm_key is not None else current.algorithm_key,
            "strictness": payload.strictness if payload.strictness is not None else current.strictness,
            "write_rules": payload.write_rules if payload.write_rules is not None else current.write_rules,
            "thresholds": payload.thresholds if payload.thresholds is not None else current.thresholds,
            "metadata": payload.metadata if payload.metadata is not None else current.metadata,
            "updated_by": (payload.updated_by or "backend").strip() or "backend",
            "updated_at": _now(),
        }
    )
    _update_records(lambda records: {**records, feature_key: updated.model_dump(mode="json")})
    return updated


def reset_feature_policy(feature_key: str) -> FeaturePolicy:
    if feature_key not in DEFAULT_FEATURE_POLICIES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature policy not found")
    policy = DEFAULT_FEATURE_POLICIES[feature_key].model_copy(update={"updated_at": _now(), "updated_by": "system-reset"})
    _update_records(lambda records: {**records, feature_key: policy.model_dump(mode="json")})
    return policy


def feature_enabled(feature_key: str) -> bool:
    return get_feature_policy(feature_key).enabled


def can_write(feature_key: str, layer: str) -> bool:
    policy = get_feature_policy(feature_key)
    if not policy.enabled:
        return False
    if not hasattr(policy.write_rules, layer):
        return False
    return bool(getattr(policy.write_rules, layer))
