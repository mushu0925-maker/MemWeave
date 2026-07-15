from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable

from app.schemas.clarification import QuestionTargetCreate, UncertainItemCreate
from app.schemas.memory_completion import MemoryCompletionGap, MemoryCompletionRequest, MemoryCompletionResponse
from app.services.feature_policy_store import can_write, get_feature_policy
from app.services.monitoring_store import record_monitoring_event
from app.services.profile_store import get_profile
from app.services.raw_source_store import get_raw_source
from app.services.uncertainty_store import save_question_target, save_uncertain_item


CompletionAlgorithm = Callable[[MemoryCompletionRequest], list[MemoryCompletionGap]]

TIME_TERMS = ("今天", "昨天", "明天", "去年", "今年", "小时候", "冬天", "夏天", "晚上", "早上", "周末", "那天", "那次")
PLACE_TERMS = ("家", "学校", "医院", "公园", "餐厅", "车站", "店", "房间", "城市", "北京", "上海", "广州", "深圳")
PEOPLE_TERMS = ("他", "她", "TA", "ta", "妈妈", "爸爸", "朋友", "同学", "老师", "我们", "他们", "她们")
EVENT_TERMS = ("发生", "一起", "聊天", "吵架", "分开", "见面", "送", "说", "做", "陪", "提醒", "照顾")
FEELING_TERMS = ("难过", "开心", "害怕", "生气", "委屈", "安心", "失望", "痛苦", "担心", "感动", "不确定")
EVIDENCE_TERMS = ("原话", "照片", "截图", "录音", "日记", "信", "记录", "证据", "我记得", "他说", "她说")


def _now() -> datetime:
    return datetime.now(UTC)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term.lower() in text.lower() for term in terms)


def _gap(field: str, reason: str, question: str, expected_evidence_type: str) -> MemoryCompletionGap:
    return MemoryCompletionGap(
        field=field,  # type: ignore[arg-type]
        severity="high" if field in {"event", "evidence_source"} else "medium",
        reason=reason,
        question=question,
        expected_evidence_type=expected_evidence_type,
    )


def _field_gap_v1(payload: MemoryCompletionRequest) -> list[MemoryCompletionGap]:
    text = payload.text.strip()
    gaps: list[MemoryCompletionGap] = []
    if not _contains_any(text, TIME_TERMS):
        gaps.append(
            _gap(
                "time",
                "这段事件记忆没有明确时间线索。",
                "这件事大概发生在什么时候？可以是年份、季节、某天晚上，或你能想起的相对时间。",
                "time_or_relative_time",
            )
        )
    if not _contains_any(text, PLACE_TERMS):
        gaps.append(
            _gap(
                "place",
                "这段事件记忆没有明确地点或场景。",
                "这件事大概发生在哪里？如果地点不确定，可以描述当时的场景。",
                "place_or_scene",
            )
        )
    if not _contains_any(text, PEOPLE_TERMS):
        gaps.append(
            _gap(
                "people",
                "这段事件记忆没有明确参与人物。",
                "这件事里有哪些人？谁说了话，谁做了动作？",
                "people_and_roles",
            )
        )
    if not _contains_any(text, EVENT_TERMS) or len(text) < 20:
        gaps.append(
            _gap(
                "event",
                "事件动作不够具体，暂时不能沉淀为稳定事实。",
                "能不能补一个具体动作或对话：TA 当时做了什么、说了什么、你们后来怎样？",
                "concrete_action_or_dialogue",
            )
        )
    if not _contains_any(text, FEELING_TERMS):
        gaps.append(
            _gap(
                "user_feeling",
                "用户当时的感受没有明确标注，难以区分事实、记忆和感受。",
                "你当时是什么感受？这是事实记录、你的感受，还是你对 TA 的推测？",
                "fact_memory_feeling_or_inference",
            )
        )
    if not _contains_any(text, EVIDENCE_TERMS):
        gaps.append(
            _gap(
                "evidence_source",
                "缺少证据来源或原话线索，后续不能当作客观事实。",
                "这段记忆有没有原话、照片、聊天记录、日记，或者你非常确定的细节可以支持？",
                "quote_artifact_or_reliable_detail",
            )
        )
    return gaps


COMPLETION_ALGORITHMS: dict[str, CompletionAlgorithm] = {
    "field_gap_v1": _field_gap_v1,
}


def complete_event_memory(payload: MemoryCompletionRequest) -> MemoryCompletionResponse:
    get_profile(payload.profile_id)
    if payload.source_id is not None:
        source = get_raw_source(payload.source_id)
        if source.profile_id != payload.profile_id:
            raise ValueError("source_profile_mismatch")

    policy = get_feature_policy("event_memory_completion")
    algorithm = COMPLETION_ALGORITHMS.get(policy.algorithm_key)
    if algorithm is None:
        return MemoryCompletionResponse(
            created_at=_now(),
            feature_policy=policy,
            algorithm_key=policy.algorithm_key,
            strictness=policy.strictness,
            profile_id=payload.profile_id,
            source_id=payload.source_id,
            dry_run=payload.dry_run,
            write_decisions={},
            diagnostics={"blocked": True, "reason": f"unsupported_algorithm_key:{policy.algorithm_key}"},
        )

    gaps = algorithm(payload) if policy.enabled else []
    minimum_gap_count = int(policy.thresholds.get("minimum_gap_count", 1))
    if len(gaps) < minimum_gap_count:
        gaps = []

    write_decisions = {
        "raw_source": can_write("event_memory_completion", "raw_source") and not payload.dry_run,
        "persona_item": can_write("event_memory_completion", "persona_item") and not payload.dry_run,
        "uncertain_item": can_write("event_memory_completion", "uncertain_item") and not payload.dry_run,
        "question_target": can_write("event_memory_completion", "question_target") and not payload.dry_run,
        "monitoring_event": can_write("event_memory_completion", "monitoring_event") and not payload.dry_run,
    }

    uncertain_item_ids = []
    question_target_ids = []
    for gap in gaps:
        uncertain_item = None
        if write_decisions["uncertain_item"]:
            uncertain_item = save_uncertain_item(
                UncertainItemCreate(
                    profile_id=payload.profile_id,
                    source_id=payload.source_id,
                    library_group="A",
                    library_key="fact_shared_memories",
                    claim=f"事件记忆缺少 {gap.field}：{payload.text[:220]}",
                    why_uncertain=gap.reason,
                    risk_type="unclear",
                    suggested_question=gap.question,
                    confirmation_options=["keep", "correct", "downrank", "hide", "forget"],
                    confidence=0.25,
                    metadata={
                        "source": "event_memory_completion",
                        "gap_field": gap.field,
                        "algorithm_key": policy.algorithm_key,
                        "strictness": policy.strictness,
                        **payload.metadata,
                    },
                )
            )
            uncertain_item_ids.append(uncertain_item.id)
        if write_decisions["question_target"]:
            question = save_question_target(
                QuestionTargetCreate(
                    profile_id=payload.profile_id,
                    source_id=payload.source_id,
                    uncertain_item_id=uncertain_item.id if uncertain_item else None,
                    target_group="A",
                    target_library_key="fact_shared_memories",
                    reason="missing",
                    question=gap.question,
                    example_answer="尽量补充时间、地点、人物、原话、当时感受和可验证证据；不确定的部分可以直接说不确定。",
                    priority=85 if gap.severity == "high" else 65,
                    expected_evidence_type=gap.expected_evidence_type,
                    metadata={
                        "source": "event_memory_completion",
                        "gap_field": gap.field,
                        "algorithm_key": policy.algorithm_key,
                        "strictness": policy.strictness,
                        **payload.metadata,
                    },
                )
            )
            question_target_ids.append(question.id)

    monitoring_event_id = None
    if write_decisions["monitoring_event"]:
        event = record_monitoring_event(
            event_type="confirmation",
            status="success",
            profile_id=payload.profile_id,
            raw_source_id=payload.source_id,
            subject_id=str(payload.source_id or payload.profile_id),
            workflow="event_memory_completion",
            input_summary=payload.text[:1000],
            output_summary=f"gaps={len(gaps)},questions={len(question_target_ids)}",
            metadata={
                "algorithm_key": policy.algorithm_key,
                "strictness": policy.strictness,
                "gap_fields": [gap.field for gap in gaps],
                "dry_run": payload.dry_run,
            },
        )
        monitoring_event_id = event.id

    return MemoryCompletionResponse(
        created_at=_now(),
        feature_policy=policy,
        algorithm_key=policy.algorithm_key,
        strictness=policy.strictness,
        profile_id=payload.profile_id,
        source_id=payload.source_id,
        dry_run=payload.dry_run,
        gaps=gaps,
        uncertain_item_ids=uncertain_item_ids,
        question_target_ids=question_target_ids,
        monitoring_event_id=monitoring_event_id,
        write_decisions=write_decisions,
        diagnostics={
            "policy_enabled": policy.enabled,
            "minimum_gap_count": minimum_gap_count,
            "gap_count": len(gaps),
            "persona_item_write_allowed": write_decisions["persona_item"],
            "raw_source_write_allowed": write_decisions["raw_source"],
        },
    )
