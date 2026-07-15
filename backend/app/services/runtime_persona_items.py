from __future__ import annotations

from uuid import UUID

from app.schemas.persona_item import PersonaItemSchema
from app.services.persona_item_store import list_persona_items
from app.services.raw_source_store import list_raw_sources
from app.services.runtime_gate import (
    list_runtime_gate_decisions,
    runtime_allowed_item_ids,
    runtime_gate_report,
    runtime_gate_summary,
)
from app.services.source_segment_store import list_source_segments


def _segments_by_source_id(profile_id: UUID) -> dict[UUID, list[object]]:
    grouped: dict[UUID, list[object]] = {}
    for segment in list_source_segments(profile_id=profile_id):
        grouped.setdefault(segment.raw_source_id, []).append(segment)
    return grouped


def _is_boundary_item(item: PersonaItemSchema) -> bool:
    return item.library_group == "L" or item.write_target == "boundary_only" or item.risk == "safety_boundary"


def list_runtime_persona_items(profile_id: UUID) -> list[PersonaItemSchema]:
    """Return persona items that pass the runtime gate for Skill input."""

    items = list_persona_items(profile_id)
    sources_by_id = {source.id: source for source in list_raw_sources(profile_id, include_deleted=True)}
    decisions = list_runtime_gate_decisions(
        items,
        sources_by_id=sources_by_id,
        segments_by_source_id=_segments_by_source_id(profile_id),  # type: ignore[arg-type]
    )
    allowed_ids = runtime_allowed_item_ids(decisions)
    return [item for item in items if item.id in allowed_ids]


def list_chat_runtime_persona_items(profile_id: UUID) -> list[PersonaItemSchema]:
    """Return only persona items that are allowed in chat top context."""

    items = list_persona_items(profile_id)
    sources_by_id = {source.id: source for source in list_raw_sources(profile_id, include_deleted=True)}
    decisions = list_runtime_gate_decisions(
        items,
        sources_by_id=sources_by_id,
        segments_by_source_id=_segments_by_source_id(profile_id),  # type: ignore[arg-type]
    )
    allowed_ids = runtime_allowed_item_ids(decisions, for_chat=True)
    return [item for item in items if item.id in allowed_ids]


def list_runtime_boundary_items(profile_id: UUID) -> list[PersonaItemSchema]:
    """Return confirmed boundary items as constraints, not style/fact evidence."""

    items = [item for item in list_persona_items(profile_id) if _is_boundary_item(item)]
    sources_by_id = {source.id: source for source in list_raw_sources(profile_id, include_deleted=True)}
    decisions = list_runtime_gate_decisions(
        items,
        sources_by_id=sources_by_id,
        segments_by_source_id=_segments_by_source_id(profile_id),  # type: ignore[arg-type]
    )
    allowed_ids = {decision.persona_item_id for decision in decisions if decision.verdict != "rejected"}
    return [item for item in items if item.id in allowed_ids]


def build_runtime_gate_diagnostics(profile_id: UUID) -> dict[str, object]:
    """Return a full runtime gate report without mutating persona items."""

    items = list_persona_items(profile_id, include_hidden=True)
    sources_by_id = {source.id: source for source in list_raw_sources(profile_id, include_deleted=True)}
    decisions = list_runtime_gate_decisions(
        items,
        sources_by_id=sources_by_id,
        segments_by_source_id=_segments_by_source_id(profile_id),  # type: ignore[arg-type]
    )
    return {
        "summary": runtime_gate_summary(decisions),
        "decisions": runtime_gate_report(decisions),
    }
