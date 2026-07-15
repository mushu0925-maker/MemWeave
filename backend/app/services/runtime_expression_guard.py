from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DEFAULT_EXPRESSION_GUARD_SETTINGS: dict[str, Any] = {
    "enabled": True,
    "strictness": "strict",
    "rewrite_unsupported_generic_soothing": True,
}

BANNED_GENERIC_PHRASES = [
    "深呼吸",
    "喘口气",
    "喝点水",
    "别想太多",
    "我一直都在",
    "你值得更好",
]


@dataclass(frozen=True)
class ExpressionGuardResult:
    applied: bool = False
    reason: str = ""
    blocked_terms: list[str] = field(default_factory=list)
    guidance: list[str] = field(default_factory=list)
    rewritten_text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def expression_guard_prompt_block(settings: dict[str, Any] | None = None) -> str:
    config = {**DEFAULT_EXPRESSION_GUARD_SETTINGS, **(settings or {})}
    if not config["enabled"]:
        return ""
    if config.get("strictness") == "audit_only":
        return "runtime_expression_guard: audit only; report unsupported generic soothing but do not rewrite."
    if config.get("strictness") == "relaxed":
        return ""
    return "\n".join(
        [
            "runtime_expression_guard:",
            "- Do not add generic soothing actions unless the selected evidence explicitly supports them.",
            "- Unsupported generic phrases include: 深呼吸, 喘口气, 喝点水, 别想太多, 我一直都在, 你值得更好.",
            "- Prefer evidence-backed actions, exact quotes, or low-pressure clarification.",
        ]
    )


def _phrase_supported(phrase: str, runtime_pack: str) -> bool:
    evidence_runtime_pack = runtime_pack.split("runtime_expression_guard:", 1)[0]
    if phrase == "喝点水" and ("不用喝也行" in evidence_runtime_pack or "水放旁边" in evidence_runtime_pack):
        return False
    return phrase in evidence_runtime_pack


def _phrase_rejected_in_text(phrase: str, text: str) -> bool:
    return any(
        marker in text
        for marker in [
            f"不要{phrase}",
            f"不用{phrase}",
            f"别{phrase}",
            f"不能{phrase}",
            f"不建议{phrase}",
            f"不是让你{phrase}",
            f"不是让对方{phrase}",
            f"别让你{phrase}",
            f"不靠{phrase}",
        ]
    )


def enforce_expression_guard(
    *,
    runtime_pack: str,
    assistant_text: str,
    settings: dict[str, Any] | None = None,
) -> ExpressionGuardResult:
    config = {**DEFAULT_EXPRESSION_GUARD_SETTINGS, **(settings or {})}
    if not config["enabled"]:
        return ExpressionGuardResult(applied=False, reason="expression_guard_disabled")
    if config.get("strictness") == "audit_only":
        return ExpressionGuardResult(applied=False, reason="expression_guard_audit_only", metadata={"strictness": config["strictness"]})
    if config.get("strictness") == "relaxed":
        return ExpressionGuardResult(applied=False, reason="expression_guard_relaxed", metadata={"strictness": config["strictness"]})

    blocked = [
        phrase
        for phrase in BANNED_GENERIC_PHRASES
        if phrase in assistant_text
        and not _phrase_rejected_in_text(phrase, assistant_text)
        and not _phrase_supported(phrase, runtime_pack)
    ]
    if not blocked:
        return ExpressionGuardResult(applied=False, reason="no_expression_overreach")

    rewritten = assistant_text
    replacements: list[tuple[str, str]] = []
    for phrase in blocked:
        replacements.extend(
            [
                (f"你现在可以先{phrase}一下，", ""),
                (f"你现在先{phrase}一下，", ""),
                (f"你可以先{phrase}一下，", ""),
                (f"你先{phrase}一下，", ""),
                (f"先{phrase}一下，", ""),
                (f"{phrase}一下，", ""),
                (f"你现在可以先{phrase}一下。", ""),
                (f"你现在先{phrase}一下。", ""),
                (f"你可以先{phrase}一下。", ""),
                (f"你先{phrase}一下。", ""),
                (f"先{phrase}一下。", ""),
                (f"{phrase}一下。", ""),
                (f"你现在可以先{phrase}，", ""),
                (f"你现在先{phrase}，", ""),
                (f"你可以先{phrase}，", ""),
                (f"你先{phrase}，", ""),
                (f"先{phrase}，", ""),
                (f"{phrase}，", ""),
                (f"你现在可以先{phrase}。", ""),
                (f"你现在先{phrase}。", ""),
                (f"你可以先{phrase}。", ""),
                (f"你先{phrase}。", ""),
                (f"先{phrase}。", ""),
                (f"{phrase}。", ""),
                (f"你现在可以先{phrase}", ""),
                (f"你现在先{phrase}", ""),
                (f"你可以先{phrase}", ""),
                (f"你先{phrase}", ""),
                (f"先{phrase}", ""),
                (phrase, ""),
            ]
        )
    for old, new in replacements:
        rewritten = rewritten.replace(old, new)
    rewritten = (
        rewritten.replace("，，", "，")
        .replace("，。", "。")
        .replace(" 。", "。")
        .replace("  ", " ")
        .strip(" ，。")
    )
    if not rewritten or rewritten in {"你", "你先", "可以先"}:
        rewritten = "我先按现有证据低压回应，不补资料外动作。"

    return ExpressionGuardResult(
        applied=True,
        reason="unsupported_generic_expression_rewritten",
        blocked_terms=blocked,
        guidance=["不要补资料外的通用安抚动作；优先使用证据里的原话、步骤或低压确认。"],
        rewritten_text=rewritten,
        metadata={"strictness": config["strictness"]},
    )
