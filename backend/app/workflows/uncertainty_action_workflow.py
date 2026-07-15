from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.core.security import mask_pii
from app.schemas.clarification import ConfirmationOption
from app.schemas.clarification import QuestionTargetStatus
from app.schemas.clarification import UncertainItemActionRequest
from app.schemas.clarification import UncertainItemActionResponse
from app.schemas.clarification import UncertainItemSchema
from app.schemas.clarification import UncertainItemStatus
from app.schemas.persona_classification import PersonaLibraryClassificationResult
from app.schemas.persona_item import PersonaItemSchema
from app.schemas.raw_source import RawSourceCreate
from app.schemas.raw_source import RawSourceSchema
from app.services.profile_store import get_profile, touch_profile
from app.services.raw_source_store import save_raw_source
from app.services.monitoring_store import record_monitoring_event
from app.services.uncertainty_store import (
    get_uncertain_item,
    list_question_targets_for_uncertain_item,
    update_question_target,
    update_uncertain_item,
)
from app.workflows.ingest_workflow import IngestClassificationFailure
from app.workflows.ingest_workflow import classify_raw_source_into_persona_items


ACTION_STATUS: dict[ConfirmationOption, UncertainItemStatus] = {
    "keep": "resolved",
    "correct": "resolved",
    "downrank": "resolved",
    "hide": "hidden",
    "forget": "forgotten",
}

ACTION_USE_POLICY: dict[ConfirmationOption, str] = {
    "keep": "usable_evidence",
    "correct": "use_corrected_claim",
    "downrank": "low_confidence_context_only",
    "hide": "exclude_from_chat_and_skill_keep_for_audit",
    "forget": "do_not_use_for_chat_or_skill",
}

ACTION_QUESTION_STATUS: dict[ConfirmationOption, QuestionTargetStatus] = {
    "keep": "resolved",
    "correct": "resolved",
    "downrank": "resolved",
    "hide": "dismissed",
    "forget": "dismissed",
}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _confirmed_claim_text(
    item: UncertainItemSchema,
    payload: UncertainItemActionRequest,
    corrected_claim: str | None,
) -> str | None:
    if payload.action == "correct":
        return corrected_claim
    if payload.action == "keep":
        return item.claim.strip()
    return None


def _save_confirmed_raw_source(
    *,
    item: UncertainItemSchema,
    payload: UncertainItemActionRequest,
    confirmed_claim: str,
    corrected_claim: str | None,
    note: str | None,
) -> tuple[RawSourceSchema, dict[str, int]]:
    pii_result = mask_pii(confirmed_claim)
    raw_source = save_raw_source(
        RawSourceCreate(
            profile_id=item.profile_id,
            source_type="manual_override",
            original_text=confirmed_claim,
            extracted_text=confirmed_claim,
            pii_masked_text=pii_result.content,
            metadata={
                **payload.metadata,
                "source": "uncertain_item_action",
                "uncertain_item_id": str(item.id),
                "uncertain_item_source_id": str(item.source_id) if item.source_id else None,
                "uncertain_item_persona_item_id": str(item.persona_item_id) if item.persona_item_id else None,
                "confirmation_action": payload.action,
                "use_policy": ACTION_USE_POLICY[payload.action],
                "original_uncertain_claim": item.claim,
                "confirmed_claim": confirmed_claim,
                "corrected_claim": corrected_claim,
                "user_note": note,
                "target_group": item.library_group,
                "target_library_key": item.library_key,
                "risk_type": item.risk_type,
                "why_uncertain": item.why_uncertain,
            },
        )
    )
    return raw_source, pii_result.replacements


def _action_metadata(
    payload: UncertainItemActionRequest,
    *,
    raw_source: RawSourceSchema | None,
    persona_items: list[PersonaItemSchema],
    classification_succeeded: bool,
    classification_failure: dict[str, Any] | None,
) -> dict[str, Any]:
    action = payload.action
    classified_targets = [f"{item.library_group}/{item.library_key}" for item in persona_items]
    metadata: dict[str, Any] = {
        **payload.metadata,
        "confirmation_action": action,
        "action_result": ACTION_STATUS[action],
        "use_policy": ACTION_USE_POLICY[action],
        "handled_at": _now_iso(),
        "raw_source_preserved": True,
        "raw_source_created": raw_source is not None,
        "confirmation_raw_source_id": str(raw_source.id) if raw_source else None,
        "classification_attempted": raw_source is not None,
        "classification_succeeded": classification_succeeded,
        "persona_items_created": bool(persona_items),
        "new_persona_items": len(persona_items),
        "persona_item_ids": [str(item.id) for item in persona_items],
        "classified_targets": classified_targets,
        "skill_regeneration_triggered": False,
    }
    if classification_failure is not None:
        metadata["classification_failure"] = classification_failure
    corrected_claim = _clean_optional_text(payload.corrected_claim)
    note = _clean_optional_text(payload.note)
    if corrected_claim is not None:
        metadata["corrected_claim"] = corrected_claim
    if note is not None:
        metadata["user_note"] = note
    return metadata


def apply_uncertain_item_action(
    item_id: UUID,
    payload: UncertainItemActionRequest,
) -> UncertainItemActionResponse:
    """Apply a user decision to an uncertain item without mutating raw evidence."""

    item = get_uncertain_item(item_id)
    get_profile(item.profile_id)
    if item.status != "open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Uncertain item action has already been handled",
        )

    corrected_claim = _clean_optional_text(payload.corrected_claim)
    if payload.action == "correct" and corrected_claim is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="corrected_claim is required when action is correct",
        )
    note = _clean_optional_text(payload.note)

    raw_source: RawSourceSchema | None = None
    persona_items: list[PersonaItemSchema] = []
    classification: PersonaLibraryClassificationResult | None = None
    classification_succeeded = False
    classification_diagnostics: dict[str, Any] = {}
    classification_failure: dict[str, Any] | None = None
    pii_summary: dict[str, int] = {}

    confirmed_claim = _confirmed_claim_text(item, payload, corrected_claim)
    if confirmed_claim is not None:
        raw_source, pii_summary = _save_confirmed_raw_source(
            item=item,
            payload=payload,
            confirmed_claim=confirmed_claim,
            corrected_claim=corrected_claim,
            note=note,
        )
        try:
            classification, persona_items, classification_diagnostics = classify_raw_source_into_persona_items(raw_source)
            classification_succeeded = True
        except IngestClassificationFailure as exc:
            classification_diagnostics = exc.to_http_detail()
            classification_failure = classification_diagnostics

    updated_item = update_uncertain_item(
        item.id,
        status=ACTION_STATUS[payload.action],
        metadata_updates=_action_metadata(
            payload,
            raw_source=raw_source,
            persona_items=persona_items,
            classification_succeeded=classification_succeeded,
            classification_failure=classification_failure,
        ),
    )

    question_updates = []
    question_status = ACTION_QUESTION_STATUS[payload.action]
    persona_item_ids = [str(item.id) for item in persona_items]
    classified_targets = [f"{item.library_group}/{item.library_key}" for item in persona_items]
    for question in list_question_targets_for_uncertain_item(item.id):
        question_updates.append(
            update_question_target(
                question.id,
                status=question_status,
                metadata_updates={
                    "closed_by_uncertain_item_action": payload.action,
                    "closed_by_uncertain_item_id": str(item.id),
                    "closed_at": _now_iso(),
                    "use_policy": ACTION_USE_POLICY[payload.action],
                    "raw_source_preserved": True,
                    "confirmation_raw_source_id": str(raw_source.id) if raw_source else None,
                    "classification_attempted": raw_source is not None,
                    "classification_succeeded": classification_succeeded,
                    "persona_item_ids": persona_item_ids,
                    "new_persona_items": len(persona_items),
                    "classified_targets": classified_targets,
                    "target_group": question.target_group,
                    "target_library_key": question.target_library_key,
                },
            )
        )

    touch_profile(item.profile_id)
    record_monitoring_event(
        event_type="confirmation",
        status="success" if updated_item.status in {"resolved", "hidden", "forgotten"} else "blocked",
        profile_id=item.profile_id,
        raw_source_id=raw_source.id if raw_source else item.source_id,
        subject_id=str(item.id),
        workflow="uncertain_item_action",
        input_summary=item.claim,
        output_summary=f"action={payload.action},status={updated_item.status},persona_items={len(persona_items)}",
        used_persona_item_ids=[persona_item.id for persona_item in persona_items],
        used_raw_source_ids=[raw_source.id] if raw_source else ([item.source_id] if item.source_id else []),
        metadata={
            "confirmation_action": payload.action,
            "use_policy": ACTION_USE_POLICY[payload.action],
            "classification_attempted": raw_source is not None,
            "classification_succeeded": classification_succeeded,
            "new_persona_items": len(persona_items),
            "persona_item_ids": persona_item_ids,
            "classified_targets": classified_targets,
            "question_targets_updated": len(question_updates),
            "question_target_ids": [str(question.id) for question in question_updates],
            "corrected_claim_present": corrected_claim is not None,
            "confirmation_raw_source_id": str(raw_source.id) if raw_source else None,
        },
    )
    return UncertainItemActionResponse(
        uncertain_item=updated_item,
        question_targets=question_updates,
        action=payload.action,
        raw_source=raw_source,
        persona_items=persona_items,
        persona_library_classification=classification,
        classification_succeeded=classification_succeeded,
        diagnostics={
            "use_policy": ACTION_USE_POLICY[payload.action],
            "updated_question_targets": len(question_updates),
            "raw_source_preserved": True,
            "confirmation_raw_source_id": str(raw_source.id) if raw_source else None,
            "classification_attempted": raw_source is not None,
            "classification_succeeded": classification_succeeded,
            "classification_diagnostics": classification_diagnostics,
            "classification_failure": classification_failure,
            "pii_summary": pii_summary,
            "persona_items_created": bool(persona_items),
            "new_persona_items": len(persona_items),
            "persona_item_ids": persona_item_ids,
            "classified_targets": classified_targets,
            "question_target_ids": [str(question.id) for question in question_updates],
            "skill_regeneration_triggered": False,
        },
    )
