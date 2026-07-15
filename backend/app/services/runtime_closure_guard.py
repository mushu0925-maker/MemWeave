from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


DEFAULT_CLOSURE_GUARD_SETTINGS: dict[str, Any] = {
    "enabled": True,
    "strictness": "strict",
    "trim_templates": True,
}

TAIL_PATTERNS = [
    "明天张嘴就顺了",
    "目前能确定的口头禅是",
    "目前能确定的是",
    "目前可以确定的是",
    "先留意一下",
    "可以留意一下",
    "倒是可以留意一下",
    "我们再一起看看",
    "后面再看",
    "可以再看",
]

SUMMARY_LEAD_PATTERNS = [
    "目前能确定",
    "可以确定",
    "现在能确定",
    "目前来看",
    "倒是可以",
    "所以这个判断",
    "所以目前",
    "更像是",
]


@dataclass(frozen=True)
class ClosureGuardResult:
    applied: bool = False
    reason: str = ""
    blocked_terms: list[str] = field(default_factory=list)
    guidance: list[str] = field(default_factory=list)
    rewritten_text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def closure_guard_prompt_block(settings: dict[str, Any] | None = None) -> str:
    config = {**DEFAULT_CLOSURE_GUARD_SETTINGS, **(settings or {})}
    if not config["enabled"]:
        return ""
    if config.get("strictness") == "audit_only":
        return "runtime_closure_guard: audit only; report unsupported closure tails but do not rewrite."
    if config.get("strictness") == "relaxed":
        return ""
    return "\n".join(
        [
            "runtime_closure_guard:",
            "- End the reply after the evidence-backed point is delivered.",
            "- Do not add a cheerful closing, upbeat summary, or extra follow-up sentence.",
            "- Do not add unsupported tail phrases such as: 明天张嘴就顺了, 目前能确定的口头禅是, 目前可以确定的是, 可以留意一下, 倒是可以留意一下.",
            "- Keep the answer short and stop when the evidence point is complete.",
        ]
    )


def _is_supported_tail(runtime_pack: str, phrase: str) -> bool:
    evidence_runtime_pack = runtime_pack.split("runtime_closure_guard:", 1)[0]
    return phrase in evidence_runtime_pack


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def _truncate_before_tail(text: str, blocked: list[str]) -> str:
    if not blocked:
        return text
    tail_positions = [text.find(phrase) for phrase in blocked if phrase in text]
    if not tail_positions:
        return text
    cutoff = min(tail_positions)
    prefix = text[:cutoff]
    if not prefix.strip():
        return ""

    sentence_boundaries = [prefix.rfind(marker) for marker in ("\n", "。", "！", "!", "？", "?")]
    last_boundary = max(sentence_boundaries)
    if last_boundary >= 0:
        end = last_boundary + 1
        closing_quotes = set("”’\"'》）)]}】")
        while end < len(prefix) and prefix[end] in closing_quotes:
            end += 1
        prefix = prefix[:end]

    return prefix.rstrip(" \t\r\n。！？!?，,、；;：:—-\"'“”‘’")


def _truncate_summary_leads(text: str) -> str:
    matches = [text.find(pattern) for pattern in SUMMARY_LEAD_PATTERNS if pattern in text]
    if not matches:
        return text
    cutoff = min(matches)
    prefix = text[:cutoff]
    return prefix.rstrip(" \t\r\n。！？!?，,、；;：:—-\"'“”‘’")


def enforce_closure_guard(
    *,
    runtime_pack: str,
    assistant_text: str,
    settings: dict[str, Any] | None = None,
) -> ClosureGuardResult:
    config = {**DEFAULT_CLOSURE_GUARD_SETTINGS, **(settings or {})}
    if not config["enabled"]:
        return ClosureGuardResult(applied=False, reason="closure_guard_disabled")
    if config.get("strictness") == "audit_only":
        return ClosureGuardResult(applied=False, reason="closure_guard_audit_only", metadata={"strictness": config["strictness"]})
    if config.get("strictness") == "relaxed":
        return ClosureGuardResult(applied=False, reason="closure_guard_relaxed", metadata={"strictness": config["strictness"]})

    blocked = [phrase for phrase in TAIL_PATTERNS if phrase in assistant_text and not _is_supported_tail(runtime_pack, phrase)]
    if not blocked:
        return ClosureGuardResult(applied=False, reason="no_closure_overreach")

    rewritten = _truncate_before_tail(assistant_text, blocked)
    rewritten = _truncate_summary_leads(rewritten)
    rewritten = _normalize_text(rewritten).strip(" 。")
    if not rewritten:
        rewritten = "我先按现有证据谨慎回应。"

    return ClosureGuardResult(
        applied=True,
        reason="unsupported_closure_tail_rewritten",
        blocked_terms=blocked,
        guidance=["收尾时不要额外补乐观总结、模板化口头禅或再追看一句。"],
        rewritten_text=rewritten,
        metadata={"strictness": config["strictness"]},
    )
