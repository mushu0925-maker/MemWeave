from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from app.core.security import mask_pii
from app.schemas.clarification import QuestionTargetCreate, QuestionTargetSchema, UncertainItemCreate, UncertainItemSchema
from app.schemas.raw_source import RawSourceCreate, RawSourceSchema
from app.services.ai_gateway import chat_json_result
from app.services.feature_policy_store import can_write, get_feature_policy
from app.services.monitoring_store import record_monitoring_event
from app.services.raw_source_store import save_raw_source
from app.services.uncertainty_store import save_question_target, save_uncertain_item

MIN_CANDIDATE_CHARS = 18
MIN_MEANINGFUL_CHARS = 3
MAX_AI_MESSAGE_CHARS = 1200
MEMORY_CUE_TERMS = (
    "记得",
    "记住",
    "以前",
    "曾经",
    "那次",
    "那天",
    "小时候",
    "一起",
    "他说",
    "她说",
    "ta说",
    "TA说",
    "对我",
    "总是",
    "经常",
    "从来",
)
VALID_CANDIDATE_TYPES = {"fact", "feeling", "inference", "boundary", "mixed"}
VALID_RISK_TYPES = {"unclear", "low_confidence", "conflict", "negative_memory", "sensitive", "unsupported_fact"}
VALID_REASON_TYPES = {"missing", "low_confidence", "conflict", "needs_example", "needs_boundary"}

CandidateType = Literal["fact", "feeling", "inference", "boundary", "mixed"]

CHAT_CANDIDATE_JUDGE_SYSTEM_PROMPT = """
你是“第三者聊天候选记忆判断器”。

你的任务不是聊天，不是安慰用户，也不是扮演 TA。
你只判断用户这句话是否值得进入“待确认记忆区”。

进入待确认区的条件：
- 包含具体人物关系、共同经历、场景、原话、行为、情绪反应、边界要求，或用户心里对 TA 的画像线索。
- 即使是主观感受也可以进入，但必须标记为 feeling 或 inference，不能当事实。
- 负面、痛苦、敏感内容可以进入，但必须标记风险，后续让用户选择保留、纠正、降权、隐藏或遗忘。

不要进入待确认区的内容：
- 乱码、纯问号、纯符号、编码错误、无法读懂的片段。
- 普通寒暄、测试、单纯催促、与 TA 无关的闲聊。
- 没有任何可确认信息的空泛表达。

只输出 JSON 对象，不要输出 Markdown。
字段：
{
  "should_create_candidate": boolean,
  "candidate_type": "fact" | "feeling" | "inference" | "boundary" | "mixed" | "invalid",
  "library_group": "A" | "F" | "I" | "J" | "L",
  "library_key": string,
  "claim": string,
  "why_uncertain": string,
  "risk_type": "unclear" | "low_confidence" | "conflict" | "negative_memory" | "sensitive" | "unsupported_fact",
  "suggested_question": string,
  "question_reason": "missing" | "low_confidence" | "conflict" | "needs_example" | "needs_boundary",
  "expected_evidence_type": string,
  "confidence": number,
  "reject_reason": string
}

要求：
- should_create_candidate=false 时，claim/suggested_question 可以为空，但 reject_reason 必须说明原因。
- should_create_candidate=true 时，claim 必须保守表达为“用户提到/用户感受到/用户推测”，不要写成 TA 的确定事实。
- confidence 范围 0 到 1；第三者聊天候选通常不超过 0.45。
""".strip()


@dataclass(frozen=True)
class ChatCandidateEvidenceResult:
    created: bool
    reason: str
    raw_source: RawSourceSchema | None = None
    uncertain_item: UncertainItemSchema | None = None
    question_target: QuestionTargetSchema | None = None


@dataclass(frozen=True)
class CandidateJudgement:
    should_create_candidate: bool
    reason: str
    provider: str = "local"
    candidate_type: str = "invalid"
    library_group: str = "A"
    library_key: str = "fact_uncertain_claims"
    claim: str = ""
    why_uncertain: str = ""
    risk_type: str = "low_confidence"
    suggested_question: str = ""
    question_reason: str = "needs_example"
    expected_evidence_type: str = "concrete_scene_or_boundary"
    confidence: float = 0.25
    raw_payload: dict[str, Any] | None = None


def _meaningful_character_count(text: str) -> int:
    return sum(1 for char in text if char.isalnum() or "\u4e00" <= char <= "\u9fff")


def _is_repeated_noise(text: str) -> bool:
    compact = "".join(text.split())
    if not compact:
        return True
    if len(set(compact)) <= 2 and len(compact) >= 3:
        return True
    return False


def _basic_invalid_reason(message: str) -> str | None:
    text = message.strip()
    if not text:
        return "empty_message"
    if _meaningful_character_count(text) < MIN_MEANINGFUL_CHARS:
        return "too_few_meaningful_characters"
    if _is_repeated_noise(text):
        return "repeated_noise"
    return None


def _looks_like_candidate_memory(message: str) -> bool:
    text = message.strip()
    if len(text) >= MIN_CANDIDATE_CHARS:
        return True
    return any(term in text for term in MEMORY_CUE_TERMS)


def _clip(text: str, limit: int) -> str:
    stripped = " ".join(text.strip().split())
    if len(stripped) <= limit:
        return stripped
    return f"{stripped[: limit - 1]}…"


def _coerce_bool(value: Any) -> bool:
    return value is True


def _coerce_str(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) else default


def _coerce_float(value: Any, default: float, *, minimum: float = 0.0, maximum: float = 1.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return min(max(number, minimum), maximum)


def _judge_candidate_with_ai(message: str) -> CandidateJudgement:
    basic_invalid = _basic_invalid_reason(message)
    if basic_invalid:
        return CandidateJudgement(should_create_candidate=False, reason=basic_invalid)
    if not _looks_like_candidate_memory(message):
        return CandidateJudgement(should_create_candidate=False, reason="no_memory_cue")

    user_prompt = f"""
请判断下面这句第三者聊天中的用户输入，是否值得进入待确认记忆区。

用户输入：
{_clip(message, MAX_AI_MESSAGE_CHARS)}
""".strip()
    result = chat_json_result(CHAT_CANDIDATE_JUDGE_SYSTEM_PROMPT, user_prompt)
    if result.error or not result.payload:
        return CandidateJudgement(
            should_create_candidate=False,
            reason=f"ai_judgement_unavailable:{result.error or 'empty_payload'}",
            provider=result.provider,
        )

    payload = result.payload
    should_create = _coerce_bool(payload.get("should_create_candidate"))
    reject_reason = _coerce_str(payload.get("reject_reason"), "ai_rejected")
    if not should_create:
        return CandidateJudgement(
            should_create_candidate=False,
            reason=f"ai_rejected:{reject_reason}",
            provider=result.provider,
            raw_payload=payload,
        )

    candidate_type = _coerce_str(payload.get("candidate_type"), "mixed")
    if candidate_type not in VALID_CANDIDATE_TYPES:
        candidate_type = "mixed"
    library_group = _coerce_str(payload.get("library_group"), "A")
    if library_group not in {"A", "F", "I", "J", "L"}:
        library_group = "A"
    library_key = _coerce_str(payload.get("library_key"), "fact_uncertain_claims") or "fact_uncertain_claims"
    risk_type = _coerce_str(payload.get("risk_type"), "low_confidence")
    if risk_type not in VALID_RISK_TYPES:
        risk_type = "low_confidence"
    question_reason = _coerce_str(payload.get("question_reason"), "needs_example")
    if question_reason not in VALID_REASON_TYPES:
        question_reason = "needs_example"

    claim = _coerce_str(payload.get("claim"))
    if not claim:
        claim = f"用户在第三者聊天中提到：{message}"
    why_uncertain = _coerce_str(payload.get("why_uncertain"))
    if not why_uncertain:
        why_uncertain = "来自第三者聊天中的用户补充，尚未经过用户确认和 A-M 分类，不能直接作为 TA 的确定事实或稳定人格结论。"
    suggested_question = _coerce_str(payload.get("suggested_question"))
    if not suggested_question:
        suggested_question = "这段记忆你希望系统怎样使用？可以保留、纠正、降权、隐藏或遗忘；如果保留，请补一个具体场景、时间、地点、原话或边界。"
    expected_evidence_type = _coerce_str(payload.get("expected_evidence_type"), "concrete_scene_or_boundary")

    return CandidateJudgement(
        should_create_candidate=True,
        reason="ai_approved",
        provider=result.provider,
        candidate_type=candidate_type,
        library_group=library_group,
        library_key=_clip(library_key, 80),
        claim=_clip(claim, 500),
        why_uncertain=_clip(why_uncertain, 500),
        risk_type=risk_type,
        suggested_question=_clip(suggested_question, 500),
        question_reason=question_reason,
        expected_evidence_type=_clip(expected_evidence_type, 120),
        confidence=_coerce_float(payload.get("confidence"), 0.25, maximum=0.45),
        raw_payload=payload,
    )


def create_candidate_evidence_from_chat(
    *,
    profile_id: UUID,
    user_message: str,
    chat_record_id: UUID,
    assistant_message: str,
    chat_mode: Literal["direct", "third_person"] = "third_person",
) -> ChatCandidateEvidenceResult:
    """第三者聊天中的用户补充先进入 raw_source + 待确认区，不直接生成 persona_items。"""

    policy = get_feature_policy("third_person_candidate")
    if not policy.enabled:
        return ChatCandidateEvidenceResult(created=False, reason="feature_policy_disabled")

    message = user_message.strip()
    judgement = _judge_candidate_with_ai(message)
    if not judgement.should_create_candidate:
        return ChatCandidateEvidenceResult(created=False, reason=judgement.reason)

    raw_source = None
    if can_write("third_person_candidate", "raw_source"):
        pii_result = mask_pii(message)
        raw_source = save_raw_source(
            RawSourceCreate(
                profile_id=profile_id,
                source_type="chat",
                original_text=message,
                extracted_text=message,
                pii_masked_text=pii_result.content,
                metadata={
                    "source": "third_person_chat_candidate",
                    "chat_record_id": str(chat_record_id),
                    "chat_mode": chat_mode,
                    "candidate_policy": "raw_source_and_uncertain_item_only",
                    "pii_masking_applied": True,
                    "pii_replacements": pii_result.replacements,
                    "candidate_judgement_provider": judgement.provider,
                    "candidate_type": judgement.candidate_type,
                    "candidate_judgement_reason": judgement.reason,
                    "feature_policy_key": policy.feature_key,
                    "algorithm_key": policy.algorithm_key,
                    "strictness": policy.strictness,
                    "assistant_reply_excerpt": _clip(assistant_message, 300),
                },
            )
        )

    uncertain_item = None
    if can_write("third_person_candidate", "uncertain_item"):
        uncertain_item = save_uncertain_item(
            UncertainItemCreate(
                profile_id=profile_id,
                source_id=raw_source.id if raw_source else None,
                library_group=judgement.library_group,  # type: ignore[arg-type]
                library_key=judgement.library_key,
                claim=judgement.claim,
                why_uncertain=judgement.why_uncertain,
                risk_type=judgement.risk_type,  # type: ignore[arg-type]
                suggested_question=judgement.suggested_question,
                confirmation_options=["keep", "correct", "downrank", "hide", "forget"],
                confidence=judgement.confidence,
                metadata={
                    "source": "third_person_chat_candidate",
                    "chat_record_id": str(chat_record_id),
                    "chat_mode": chat_mode,
                    "candidate_policy": "needs_user_confirmation_before_persona_item",
                    "candidate_judgement_provider": judgement.provider,
                    "candidate_type": judgement.candidate_type,
                    "candidate_judgement_reason": judgement.reason,
                    "raw_source_preserved": raw_source is not None,
                    "feature_policy_key": policy.feature_key,
                    "algorithm_key": policy.algorithm_key,
                    "strictness": policy.strictness,
                },
            )
        )

    question_target = None
    if can_write("third_person_candidate", "question_target"):
        question_target = save_question_target(
            QuestionTargetCreate(
                profile_id=profile_id,
                source_id=raw_source.id if raw_source else None,
                uncertain_item_id=uncertain_item.id if uncertain_item else None,
                target_group=judgement.library_group,  # type: ignore[arg-type]
                target_library_key=judgement.library_key,
                reason=judgement.question_reason,  # type: ignore[arg-type]
                question=judgement.suggested_question,
                example_answer="例如：那次大概是什么时候、在哪里、TA 说了什么、你当时是什么感受、哪些部分不能让 AI 编造。",
                priority=70,
                expected_evidence_type=judgement.expected_evidence_type,
                metadata={
                    "source": "third_person_chat_candidate",
                    "chat_record_id": str(chat_record_id),
                    "chat_mode": chat_mode,
                    "candidate_judgement_provider": judgement.provider,
                    "candidate_type": judgement.candidate_type,
                    "candidate_judgement_reason": judgement.reason,
                    "feature_policy_key": policy.feature_key,
                    "algorithm_key": policy.algorithm_key,
                    "strictness": policy.strictness,
                },
            )
        )

    if can_write("third_person_candidate", "monitoring_event"):
        record_monitoring_event(
            event_type="confirmation",
            status="success" if raw_source or uncertain_item or question_target else "skipped",
            profile_id=profile_id,
            raw_source_id=raw_source.id if raw_source else None,
            chat_record_id=chat_record_id,
            subject_id=str(chat_record_id),
            workflow="third_person_candidate",
            provider=judgement.provider,
            input_summary=message,
            output_summary=judgement.claim,
            used_raw_source_ids=[raw_source.id] if raw_source else [],
            metadata={
                "feature_policy_key": policy.feature_key,
                "algorithm_key": policy.algorithm_key,
                "strictness": policy.strictness,
                "write_rules": policy.write_rules.model_dump(mode="json"),
                "created_raw_source": raw_source is not None,
                "created_uncertain_item": uncertain_item is not None,
                "created_question_target": question_target is not None,
                "candidate_type": judgement.candidate_type,
                "risk_type": judgement.risk_type,
            },
        )

    if not raw_source and not uncertain_item and not question_target:
        return ChatCandidateEvidenceResult(created=False, reason="write_rules_blocked_all_candidate_outputs")

    return ChatCandidateEvidenceResult(
        created=True,
        reason=(
            f"{judgement.reason}:"
            f"raw_source={str(raw_source is not None).lower()}:"
            f"uncertain_item={str(uncertain_item is not None).lower()}:"
            f"question_target={str(question_target is not None).lower()}"
        ),
        raw_source=raw_source,
        uncertain_item=uncertain_item,
        question_target=question_target,
    )


def create_candidate_evidence_from_third_person_chat(
    *,
    profile_id: UUID,
    user_message: str,
    chat_record_id: UUID,
    assistant_message: str,
) -> ChatCandidateEvidenceResult:
    return create_candidate_evidence_from_chat(
        profile_id=profile_id,
        user_message=user_message,
        chat_record_id=chat_record_id,
        assistant_message=assistant_message,
        chat_mode="third_person",
    )
