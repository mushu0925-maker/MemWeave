from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.schemas.raw_source import RawSourceSchema
from app.schemas.skill_generation import SkillEvidenceUnit


DEFAULT_EVIDENCE_EXTENSION_SETTINGS: dict[str, Any] = {
    "enabled": True,
    "strictness": "strict",
    "max_extensions": 2,
    "max_chars": 260,
}


@dataclass(frozen=True)
class EvidenceExtension:
    unit_id: str
    source_id: UUID
    quote: str
    extended_quote: str


@dataclass(frozen=True)
class EvidenceExtensionResult:
    applied: bool = False
    reason: str = ""
    extensions: list[EvidenceExtension] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def _source_text(source: RawSourceSchema) -> str:
    return source.pii_masked_text or source.extracted_text or source.original_text


def _split_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[。！？!?])\s*|\n+", text) if part.strip()]


def _extend_quote_from_text(quote: str, source_text: str, max_chars: int) -> str:
    quote = " ".join(quote.split())
    if not quote:
        return ""
    normalized_source = " ".join(source_text.split())
    if quote not in normalized_source:
        return ""
    sentences = _split_sentences(normalized_source)
    for index, sentence in enumerate(sentences):
        if quote in sentence:
            selected = [sentence]
            if index + 1 < len(sentences):
                selected.append(sentences[index + 1])
            extended = "".join(selected).strip()
            return extended[:max_chars].rstrip()
    start = normalized_source.find(quote)
    if start < 0:
        return ""
    return normalized_source[start : start + max_chars].rstrip()


def build_same_source_evidence_extensions(
    *,
    selected_units: list[SkillEvidenceUnit],
    sources_by_id: dict[UUID, RawSourceSchema],
    settings: dict[str, Any] | None = None,
) -> EvidenceExtensionResult:
    config = {**DEFAULT_EVIDENCE_EXTENSION_SETTINGS, **(settings or {})}
    if not config["enabled"]:
        return EvidenceExtensionResult(applied=False, reason="evidence_extension_disabled")

    extensions: list[EvidenceExtension] = []
    for unit in selected_units:
        if unit.source_id is None or not unit.evidence_quote:
            continue
        source = sources_by_id.get(unit.source_id)
        if source is None:
            continue
        extended = _extend_quote_from_text(
            unit.evidence_quote,
            _source_text(source),
            int(config["max_chars"]),
        )
        if not extended or extended == unit.evidence_quote or len(extended) <= len(unit.evidence_quote) + 4:
            continue
        extensions.append(
            EvidenceExtension(
                unit_id=unit.unit_id,
                source_id=unit.source_id,
                quote=unit.evidence_quote,
                extended_quote=extended,
            )
        )
        if len(extensions) >= int(config["max_extensions"]):
            break

    if not extensions:
        return EvidenceExtensionResult(applied=False, reason="no_same_source_extension")
    return EvidenceExtensionResult(
        applied=True,
        reason="same_source_evidence_extended",
        extensions=extensions,
        metadata={"strictness": config["strictness"]},
    )
