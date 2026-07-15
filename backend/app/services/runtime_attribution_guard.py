from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DEFAULT_ATTRIBUTION_GUARD_SETTINGS: dict[str, Any] = {
    "enabled": True,
    "strictness": "strict",
    "rewrite_user_template_as_target_style": True,
}


@dataclass(frozen=True)
class AttributionGuardResult:
    applied: bool = False
    reason: str = ""
    blocked_terms: list[str] = field(default_factory=list)
    guidance: list[str] = field(default_factory=list)
    rewritten_text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def attribution_guard_prompt_block(settings: dict[str, Any] | None = None) -> str:
    config = {**DEFAULT_ATTRIBUTION_GUARD_SETTINGS, **(settings or {})}
    if not config["enabled"]:
        return ""
    if config.get("strictness") == "audit_only":
        return "runtime_attribution_guard: audit only; report attribution risk but do not rewrite."
    if config.get("strictness") == "relaxed":
        return ""
    return "\n".join(
        [
            "runtime_attribution_guard:",
            "- Keep attribution precise: user-written templates are user preferences, not target-person quotes or style.",
            "- Avoid even negative restatements like 'cannot be the target person's catchphrase' when the user asks about a template.",
            "- Prefer: '不能。那是你自己写的回应模板，不是林晚说过的话。'",
        ]
    )


def _template_question_context(message: str, assistant_text: str) -> bool:
    combined = "\n".join([message, assistant_text])
    return ("口头禅" in combined or "语言风格" in combined or "原话" in combined) and (
        "模板" in combined or "用户希望" in combined or "你自己写" in combined
    )


def enforce_attribution_guard(
    *,
    message: str,
    assistant_text: str,
    settings: dict[str, Any] | None = None,
) -> AttributionGuardResult:
    config = {**DEFAULT_ATTRIBUTION_GUARD_SETTINGS, **(settings or {})}
    if not config["enabled"]:
        return AttributionGuardResult(applied=False, reason="attribution_guard_disabled")
    if config.get("strictness") == "audit_only":
        return AttributionGuardResult(applied=False, reason="attribution_guard_audit_only", metadata={"strictness": config["strictness"]})
    if config.get("strictness") == "relaxed":
        return AttributionGuardResult(applied=False, reason="attribution_guard_relaxed", metadata={"strictness": config["strictness"]})
    if not config["rewrite_user_template_as_target_style"]:
        return AttributionGuardResult(applied=False, reason="attribution_rewrite_disabled")
    if not _template_question_context(message, assistant_text):
        return AttributionGuardResult(applied=False, reason="no_template_attribution_context")

    blocked = [
        phrase
        for phrase in ["林晚的口头禅", "林晚常说", "目标人物原话", "林晚语言风格"]
        if phrase in assistant_text
    ]
    if not blocked:
        return AttributionGuardResult(applied=False, reason="no_attribution_overreach")

    return AttributionGuardResult(
        applied=True,
        reason="user_template_attribution_rewritten",
        blocked_terms=blocked,
        guidance=["用户模板只能归为用户偏好；不要复述成目标人物口头禅、原话或语言风格。"],
        rewritten_text="不能。那是你自己写的回应模板，不是林晚说过的话，也不能当成她的语言风格。",
        metadata={"strictness": config["strictness"]},
    )
