from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DEFAULT_BOUNDARY_GUARD_SETTINGS: dict[str, Any] = {
    "enabled": True,
    "strictness": "strict",
    "block_continue_question_overreach": True,
    "rewrite_ambiguous_leave_signal": True,
    "rewrite_hard_stop_reply": True,
}


@dataclass(frozen=True)
class BoundaryGuardResult:
    applied: bool = False
    reason: str = ""
    blocked_terms: list[str] = field(default_factory=list)
    guidance: list[str] = field(default_factory=list)
    rewritten_text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _without_boundary_negations(text: str) -> str:
    cleaned = text
    for marker in [
        "不能继续追问",
        "不继续追问",
        "不要继续追问",
        "别继续追问",
        "不能继续问",
        "不继续问",
        "不要继续问",
        "别继续问",
        "不能追问",
        "不追问",
        "不要追问",
        "别追问",
        "停止追问",
        "停止问",
        "别问了",
        "不能问为什么",
        "不问为什么",
        "不要问为什么",
        "别问为什么",
    ]:
        cleaned = cleaned.replace(marker, "")
    return cleaned


def _boundary_context_present(*, message: str, runtime_pack: str, assistant: str) -> bool:
    combined = "\n".join([message, runtime_pack, assistant])
    return _contains_any(combined, ["别管我", "停一下", "别问了", "边界", "不要继续追问", "别马上走"])


def _hard_stop_context_present(*, message: str, runtime_pack: str, assistant: str) -> bool:
    del runtime_pack
    combined_response = "\n".join([message, assistant])
    return _contains_any(message, ["停一下，别问了", "停一下", "别问了"]) and _contains_any(
        combined_response,
        ["问为什么", "为什么", "还能不能问", "还能问"],
    )


def _natural_hard_stop_reply(config: dict[str, Any]) -> BoundaryGuardResult:
    return BoundaryGuardResult(
        applied=True,
        reason="hard_stop_reply_naturalized",
        blocked_terms=["hard_stop_why_phrase"],
        guidance=["明确停问时，只表达停止和不再追问；不要复述“问为什么”这类被禁止动作。"],
        rewritten_text="不能。你说“停一下，别问了”时，我就停下，不再追问。",
        metadata={"strictness": config["strictness"]},
    )


def boundary_guard_prompt_block(message: str, runtime_pack: str, settings: dict[str, Any] | None = None) -> str:
    config = {**DEFAULT_BOUNDARY_GUARD_SETTINGS, **(settings or {})}
    if not config["enabled"] or not _boundary_context_present(message=message, runtime_pack=runtime_pack, assistant=""):
        return ""
    if config.get("strictness") == "audit_only":
        return "boundary_semantic_guard: audit only; report boundary overreach but do not rewrite."
    if config.get("strictness") == "relaxed":
        return "\n".join(
            [
                "boundary_semantic_guard:",
                "- Respect explicit hard-stop phrases such as 停一下 and 别问了.",
                "- Keep boundary phrases as action constraints, not personality labels.",
            ]
        )
    return "\n".join(
        [
            "boundary_semantic_guard:",
            "- Treat boundary phrases as consent-sensitive action constraints, not personality labels.",
            "- '别管我' plus '希望对方别马上走' only supports: do not leave immediately, stay nearby, lower pressure.",
            "- It does not support: continue questioning, press for details, force closeness, or label the phrase as a pursuit/invitation signal.",
            "- Do not summarize '别管我' as '挽留信号'; say '可能不希望对方马上离开' instead.",
            "- '停一下，别问了' explicitly means stop asking. It overrides style, care, and relationship-distance rules.",
            "- For a direct hard-stop question, say you will stop and will not continue. Do not restate the forbidden why-question phrase.",
            "- If the evidence says the difference is unclear, answer with a low-pressure clarification instead of a binary rule.",
        ]
    )


def enforce_boundary_guard(
    *,
    message: str,
    runtime_pack: str,
    assistant_text: str,
    settings: dict[str, Any] | None = None,
) -> BoundaryGuardResult:
    config = {**DEFAULT_BOUNDARY_GUARD_SETTINGS, **(settings or {})}
    if not config["enabled"]:
        return BoundaryGuardResult(applied=False, reason="boundary_guard_disabled")
    if not _boundary_context_present(message=message, runtime_pack=runtime_pack, assistant=assistant_text):
        return BoundaryGuardResult(applied=False, reason="no_boundary_context")
    if config.get("strictness") == "audit_only":
        return BoundaryGuardResult(applied=False, reason="boundary_guard_audit_only", metadata={"strictness": config["strictness"]})
    if config["rewrite_hard_stop_reply"] and _hard_stop_context_present(
        message=message,
        runtime_pack=runtime_pack,
        assistant=assistant_text,
    ):
        return _natural_hard_stop_reply(config)
    if config.get("strictness") == "relaxed":
        return BoundaryGuardResult(applied=False, reason="boundary_guard_relaxed_no_hard_stop", metadata={"strictness": config["strictness"]})

    rewritten_label_text = assistant_text
    label_rewritten = False
    for term in ["挽留信号", "挽留的信号", "被挽留的信号"]:
        if term in rewritten_label_text:
            rewritten_label_text = rewritten_label_text.replace(term, "可能不希望对方马上离开")
            label_rewritten = True
    if "别管我" in rewritten_label_text and "挽留" in rewritten_label_text:
        rewritten_label_text = rewritten_label_text.replace("挽留", "不希望对方马上离开")
        label_rewritten = True

    blocked_terms: list[str] = []
    overreach_text = _without_boundary_negations(assistant_text)
    if config["block_continue_question_overreach"] and _contains_any(
        overreach_text,
        ["继续追问", "继续问", "追问", "靠近一点", "逼近", "追着问"],
    ):
        blocked_terms.append("continue_question_overreach")

    if not blocked_terms:
        if label_rewritten:
            return BoundaryGuardResult(
                applied=True,
                reason="boundary_label_rewritten",
                blocked_terms=["boundary_label_overcompressed"],
                guidance=["不要把“别管我”压缩成“挽留信号”；改成“不希望对方马上离开/低压陪伴”。"],
                rewritten_text=rewritten_label_text,
                metadata={"strictness": config["strictness"]},
            )
        return BoundaryGuardResult(applied=False, reason="no_boundary_overreach")

    guidance = [
        "不要把“别马上走”推成“继续追问”。",
        "允许表达为：先别离开、降低压力、陪在旁边、等对方愿意再说。",
        "如果用户明确说“停一下，别问了”，必须停止追问。",
    ]
    rewritten = (
        "如果你说“别管我”，我不能直接理解成离开，也不能继续追问。"
        "更稳妥的是先别马上走，降低压力，陪在旁边，等你愿意再说。"
        "如果你明确说“停一下，别问了”，那我就停止追问。"
    )
    return BoundaryGuardResult(
        applied=True,
        reason="boundary_overreach_rewritten",
        blocked_terms=blocked_terms,
        guidance=guidance,
        rewritten_text=rewritten,
        metadata={"strictness": config["strictness"]},
    )
