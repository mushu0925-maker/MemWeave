from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from app.schemas.clarification import (
    ConfirmationOption,
    QuestionTargetCreate,
    QuestionTargetReason,
    QuestionTargetSchema,
    UncertainItemCreate,
    UncertainItemSchema,
    UncertainRiskType,
)
from app.schemas.persona_item import LibraryGroup
from app.schemas.raw_source import RawSourceSchema
from app.services.uncertainty_store import save_question_target, save_uncertain_item

VALID_LIBRARY_GROUPS: set[str] = set("ABCDEFGHIJKLM")
VALID_RISK_TYPES: set[str] = {
    "unclear",
    "low_confidence",
    "conflict",
    "negative_memory",
    "sensitive",
    "unsupported_fact",
}
VALID_CONFIRMATION_OPTIONS: set[str] = {"keep", "correct", "downrank", "hide", "forget"}


@dataclass(frozen=True)
class UncertaintyCreationResult:
    uncertain_items: list[UncertainItemSchema] = field(default_factory=list)
    question_targets: list[QuestionTargetSchema] = field(default_factory=list)
    skipped_warnings: list[str] = field(default_factory=list)

    def diagnostics(self) -> dict[str, object]:
        return {
            "persisted_uncertain_items": len(self.uncertain_items),
            "persisted_question_targets": len(self.question_targets),
            "uncertain_item_ids": [str(item.id) for item in self.uncertain_items],
            "question_target_ids": [str(item.id) for item in self.question_targets],
            "uncertainty_skipped_warnings": self.skipped_warnings,
        }


def _first_library_key(warning: dict[str, Any]) -> str:
    keys = warning.get("expected_library_keys")
    if isinstance(keys, list):
        for key in keys:
            if isinstance(key, str) and key.strip():
                return key.strip()[:80]
    category = warning.get("category")
    if isinstance(category, str) and category.strip():
        return category.strip()[:80]
    return "unknown"


def _risk_type(warning: dict[str, Any]) -> UncertainRiskType:
    value = warning.get("risk_type")
    if isinstance(value, str) and value in VALID_RISK_TYPES:
        return value  # type: ignore[return-value]
    return "unclear"


def _confirmation_options(warning: dict[str, Any]) -> list[ConfirmationOption]:
    options = warning.get("confirmation_options")
    if not isinstance(options, list):
        return ["keep", "correct", "downrank", "hide", "forget"]
    filtered = [
        option
        for option in options
        if isinstance(option, str) and option in VALID_CONFIRMATION_OPTIONS
    ]
    return filtered[:5] or ["keep", "correct", "downrank", "hide", "forget"]


def _question_reason(warning: dict[str, Any], risk_type: str) -> QuestionTargetReason:
    if risk_type == "conflict":
        return "conflict"
    if risk_type == "low_confidence":
        return "low_confidence"
    if risk_type in {"sensitive", "negative_memory", "unsupported_fact"}:
        return "needs_boundary"
    if warning.get("type") == "missing_evidence_supported_category":
        return "missing"
    return "needs_example"


def _warning_text(warning: dict[str, Any], key: str, fallback: str = "") -> str:
    value = warning.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _create_pair_from_warning(
    *,
    raw_source: RawSourceSchema,
    warning: dict[str, Any],
) -> tuple[UncertainItemSchema, QuestionTargetSchema]:
    if raw_source.profile_id is None:
        raise ValueError("raw_source has no profile_id")

    group_value = warning.get("library_group")
    if not isinstance(group_value, str) or group_value not in VALID_LIBRARY_GROUPS:
        raise ValueError("invalid library_group")
    library_group = group_value  # type: ignore[assignment]
    library_key = _first_library_key(warning)
    risk_type = _risk_type(warning)
    label = _warning_text(warning, "label", library_key)
    category = _warning_text(warning, "category", "")
    question = _warning_text(
        warning,
        "suggested_question",
        f"关于 {label}，是否有更具体的场景、原话或边界需要补充？",
    )

    metadata = {
        "source": "coverage_warning",
        "coverage_warning": warning,
        "category": category,
    }
    uncertain = save_uncertain_item(
        UncertainItemCreate(
            profile_id=raw_source.profile_id,
            source_id=raw_source.id,
            library_group=library_group,  # type: ignore[arg-type]
            library_key=library_key,
            claim=f"原文存在 {label} 线索，但模型未输出对应 A-M 条目。",
            why_uncertain="这是覆盖不足诊断，不是已确认画像；需要用户补充具体证据或边界后再写入 persona_items。",
            risk_type=risk_type,
            suggested_question=question,
            confirmation_options=_confirmation_options(warning),
            confidence=0.35,
            metadata=metadata,
        )
    )
    question_target = save_question_target(
        QuestionTargetCreate(
            profile_id=raw_source.profile_id,
            source_id=raw_source.id,
            uncertain_item_id=uncertain.id,
            target_group=library_group,  # type: ignore[arg-type]
            target_library_key=library_key,
            reason=_question_reason(warning, risk_type),
            question=question,
            priority=70,
            expected_evidence_type="具体场景、原话、行为证据或边界说明",
            metadata=metadata,
        )
    )
    return uncertain, question_target


def create_uncertainty_from_coverage_warnings(
    raw_source: RawSourceSchema,
    coverage_warnings: list[dict[str, Any]],
) -> UncertaintyCreationResult:
    """把 coverage_warnings 落成待确认数据；不生成正式 persona_items。"""

    if raw_source.profile_id is None or not coverage_warnings:
        return UncertaintyCreationResult()

    uncertain_items: list[UncertainItemSchema] = []
    question_targets: list[QuestionTargetSchema] = []
    skipped: list[str] = []

    for index, warning in enumerate(coverage_warnings):
        try:
            uncertain, question = _create_pair_from_warning(
                raw_source=raw_source,
                warning=warning,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            skipped.append(f"coverage_warning[{index}]: {exc}")
            continue
        uncertain_items.append(uncertain)
        question_targets.append(question)

    return UncertaintyCreationResult(
        uncertain_items=uncertain_items,
        question_targets=question_targets,
        skipped_warnings=skipped,
    )
