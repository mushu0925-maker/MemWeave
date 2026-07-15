from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.schemas.history_isolation import (
    HistoryIsolationCandidate,
    HistoryIsolationRequest,
    HistoryIsolationResponse,
    HistoryIsolationSummary,
)
from app.schemas.persona_item import PersonaItemSchema
from app.services.persona_item_store import hide_persona_items_by_ids, list_persona_items
from app.services.raw_source_store import list_raw_sources
from app.services.runtime_gate import list_runtime_gate_decisions

VISIBLE_HISTORY_STATUSES = {"active", "candidate", "rejected_until_confirmed"}
DEFAULT_ISOLATION_REASON = "history_pollution_isolation"


def _now() -> datetime:
    return datetime.now(UTC)


def _candidate_from_item(item: PersonaItemSchema, decision: object) -> HistoryIsolationCandidate:
    return HistoryIsolationCandidate(
        persona_item_id=item.id,
        source_id=item.source_id,
        library=f"{item.library_group}/{item.library_key}",
        signal=item.signal,
        evidence_quote=item.evidence_quote,
        status=item.status,
        verdict=decision.verdict,
        reason=decision.reason,
        reasons=decision.reasons,
        can_skill_input=decision.can_skill_input,
        can_chat_retrieve=decision.can_chat_retrieve,
    )


def _reason_matches(reasons: list[str], filters: list[str]) -> bool:
    clean_filters = [item.strip() for item in filters if item.strip()]
    if not clean_filters:
        return True
    return any(filter_text in reason for filter_text in clean_filters for reason in reasons)


def _select_candidates(profile_id: UUID, payload: HistoryIsolationRequest) -> tuple[int, int, list[HistoryIsolationCandidate]]:
    items = list_persona_items(profile_id, include_hidden=True)
    sources = list_raw_sources(profile_id, include_deleted=True)
    sources_by_id = {source.id: source for source in sources}
    decisions = list_runtime_gate_decisions(items, sources_by_id=sources_by_id)
    items_by_id = {item.id: item for item in items}
    target_verdicts = set(payload.target_verdicts)
    candidates: list[HistoryIsolationCandidate] = []

    for decision in decisions:
        item = items_by_id.get(decision.persona_item_id)
        if item is None:
            continue
        if item.status not in VISIBLE_HISTORY_STATUSES:
            continue
        if decision.verdict not in target_verdicts:
            continue
        if not _reason_matches(decision.reasons, payload.target_reasons):
            continue
        candidates.append(_candidate_from_item(item, decision))

    candidates.sort(key=lambda item: (item.verdict, item.reason, item.library, str(item.persona_item_id)))
    return len(items), len(sources), candidates[: payload.max_items]


def preview_history_pollution_isolation(
    profile_id: UUID,
    payload: HistoryIsolationRequest | None = None,
) -> HistoryIsolationResponse:
    request = payload or HistoryIsolationRequest()
    request = request.model_copy(update={"dry_run": True})
    total_items, raw_count, candidates = _select_candidates(profile_id, request)
    generated_at = _now()
    return HistoryIsolationResponse(
        summary=HistoryIsolationSummary(
            profile_id=profile_id,
            generated_at=generated_at,
            dry_run=True,
            applied=False,
            total_persona_items=total_items,
            candidate_count=len(candidates),
            hidden_count=0,
            raw_sources_before=raw_count,
            raw_sources_after=raw_count,
            target_verdicts=request.target_verdicts,
            target_reasons=request.target_reasons,
            max_items=request.max_items,
        ),
        candidates=candidates,
    )


def apply_history_pollution_isolation(
    profile_id: UUID,
    payload: HistoryIsolationRequest | None = None,
) -> HistoryIsolationResponse:
    request = payload or HistoryIsolationRequest(dry_run=False)
    request = request.model_copy(update={"dry_run": False})
    total_items, raw_before, candidates = _select_candidates(profile_id, request)
    generated_at = _now()
    ids_to_hide = {candidate.persona_item_id for candidate in candidates}
    extra_metadata = {
        candidate.persona_item_id: {
            "history_isolation": True,
            "history_isolation_at": generated_at.isoformat(),
            "history_isolation_updated_by": request.updated_by,
            "history_isolation_verdict": candidate.verdict,
            "history_isolation_reason": candidate.reason,
            "history_isolation_reasons": candidate.reasons,
            "history_isolation_policy": "hide_not_delete_keep_raw_source",
        }
        for candidate in candidates
    }
    hidden_count = hide_persona_items_by_ids(
        ids_to_hide,
        reason=DEFAULT_ISOLATION_REASON,
        extra_metadata_by_id=extra_metadata,
    )
    raw_after = len(list_raw_sources(profile_id, include_deleted=True))
    return HistoryIsolationResponse(
        summary=HistoryIsolationSummary(
            profile_id=profile_id,
            generated_at=generated_at,
            dry_run=False,
            applied=True,
            total_persona_items=total_items,
            candidate_count=len(candidates),
            hidden_count=hidden_count,
            raw_sources_before=raw_before,
            raw_sources_after=raw_after,
            target_verdicts=request.target_verdicts,
            target_reasons=request.target_reasons,
            max_items=request.max_items,
        ),
        candidates=candidates,
    )
