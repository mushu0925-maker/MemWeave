from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.core.security import mask_pii
from app.schemas.clarification import QuestionAnswerRequest, QuestionAnswerResponse
from app.schemas.clarification import UncertainItemSchema
from app.schemas.raw_source import RawSourceCreate
from app.services.monitoring_store import record_monitoring_event
from app.services.profile_store import get_profile, touch_profile
from app.services.raw_source_store import save_raw_source
from app.services.uncertainty_store import (
    get_question_target,
    get_uncertain_item,
    update_question_target,
    update_uncertain_item,
)
from app.workflows.ingest_workflow import IngestClassificationFailure, classify_raw_source_into_persona_items


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _metadata_for_answer(question_id: UUID, payload: QuestionAnswerRequest) -> dict[str, Any]:
    metadata = dict(payload.metadata)
    metadata.update(
        {
            "source": "question_target_answer",
            "question_target_id": str(question_id),
        }
    )
    return metadata


def _load_uncertain_item(item_id: UUID | None) -> UncertainItemSchema | None:
    if item_id is None:
        return None
    try:
        return get_uncertain_item(item_id)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            return None
        raise


def _items_match_question_target(
    *,
    persona_items: list[Any],
    target_group: str,
    target_library_key: str,
) -> bool:
    return any(
        item.library_group == target_group and item.library_key == target_library_key
        for item in persona_items
    )


def _classified_targets(persona_items: list[Any]) -> list[str]:
    return [f"{item.library_group}/{item.library_key}" for item in persona_items]


def answer_question_target(question_id: UUID, payload: QuestionAnswerRequest) -> QuestionAnswerResponse:
    """用户回答待确认问题时，先保存 raw_source，再走现有 A-M 分类流程。"""

    question = get_question_target(question_id)
    if question.status != "open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Question target is not open",
        )

    get_profile(question.profile_id)
    uncertain_item = _load_uncertain_item(question.uncertain_item_id)
    answer_text = payload.answer_text.strip()
    if not answer_text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Answer text is required")
    pii_result = mask_pii(answer_text)
    raw_source = save_raw_source(
        RawSourceCreate(
            profile_id=question.profile_id,
            source_type="interview",
            original_text=answer_text,
            extracted_text=answer_text,
            pii_masked_text=pii_result.content,
            metadata={
                **_metadata_for_answer(question_id, payload),
                "uncertain_item_id": str(question.uncertain_item_id) if question.uncertain_item_id else None,
                "original_question_source_id": str(question.source_id) if question.source_id else None,
                "target_group": question.target_group,
                "target_library_key": question.target_library_key,
                "question": question.question,
                "reason": question.reason,
                "expected_evidence_type": question.expected_evidence_type,
            },
        )
    )

    try:
        classification, persona_items, diagnostics = classify_raw_source_into_persona_items(raw_source)
    except IngestClassificationFailure as exc:
        updated_question = update_question_target(
            question_id,
            metadata_updates={
                "last_answer_raw_source_id": str(raw_source.id),
                "last_answered_at": _now_iso(),
                "classification_succeeded": False,
                "target_match_required": True,
                "target_match_succeeded": False,
                "question_target_status": "open",
                "classification_failure": exc.to_http_detail(),
            },
        )
        record_monitoring_event(
            event_type="confirmation",
            status="failed",
            profile_id=question.profile_id,
            raw_source_id=raw_source.id,
            subject_id=str(question.id),
            workflow="question_target_answer",
            provider=exc.provider,
            model_name=exc.model_name,
            input_summary=answer_text[:1000],
            output_summary="classification_failed",
            error=exc.reason,
            used_raw_source_ids=[raw_source.id],
            metadata={
                "question_target_id": str(question.id),
                "uncertain_item_id": str(question.uncertain_item_id) if question.uncertain_item_id else None,
                "target_group": question.target_group,
                "target_library_key": question.target_library_key,
                "classification_succeeded": False,
                "target_match_required": True,
                "target_match_succeeded": False,
                "question_target_status": updated_question.status,
            },
        )
        return QuestionAnswerResponse(
            raw_source=raw_source,
            persona_items=[],
            question_target=updated_question,
            uncertain_item=uncertain_item,
            persona_library_classification=None,
            classification_succeeded=False,
            diagnostics={
                **exc.to_http_detail(),
                "pii_summary": pii_result.replacements,
                "question_target_status": updated_question.status,
            },
        )

    persona_item_ids = [str(item.id) for item in persona_items]
    target_matched = _items_match_question_target(
        persona_items=persona_items,
        target_group=question.target_group,
        target_library_key=question.target_library_key,
    )
    classified_targets = _classified_targets(persona_items)
    question_metadata = {
            "answer_raw_source_id": str(raw_source.id),
            "answered_at": _now_iso(),
            "classification_succeeded": True,
            "persona_item_ids": persona_item_ids,
            "new_persona_items": len(persona_items),
            "target_match_required": True,
            "target_match_succeeded": target_matched,
            "target_group": question.target_group,
            "target_library_key": question.target_library_key,
            "classified_targets": classified_targets,
        }
    if not target_matched:
        question_metadata["target_match_failure"] = "classification_did_not_hit_question_target"
    updated_question = update_question_target(
        question_id,
        status="resolved" if target_matched else "open",
        metadata_updates=question_metadata,
    )
    updated_uncertain_item = uncertain_item
    if uncertain_item is not None and target_matched:
        updated_uncertain_item = update_uncertain_item(
            uncertain_item.id,
            status="resolved",
            metadata_updates={
                "resolved_by_question_target_id": str(question_id),
                "answer_raw_source_id": str(raw_source.id),
                "persona_item_ids": persona_item_ids,
                "new_persona_items": len(persona_items),
                "target_match_required": True,
                "target_match_succeeded": True,
                "target_group": question.target_group,
                "target_library_key": question.target_library_key,
                "classified_targets": classified_targets,
                "resolved_at": _now_iso(),
            },
        )
    elif uncertain_item is not None:
        updated_uncertain_item = update_uncertain_item(
            uncertain_item.id,
            metadata_updates={
                "last_question_target_id": str(question_id),
                "last_answer_raw_source_id": str(raw_source.id),
                "last_persona_item_ids": persona_item_ids,
                "new_persona_items": len(persona_items),
                "target_match_required": True,
                "target_match_succeeded": False,
                "target_match_failure": "classification_did_not_hit_question_target",
                "target_group": question.target_group,
                "target_library_key": question.target_library_key,
                "classified_targets": classified_targets,
            },
        )

    touch_profile(question.profile_id)
    record_monitoring_event(
        event_type="confirmation",
        status="success" if target_matched else "blocked",
        profile_id=question.profile_id,
        raw_source_id=raw_source.id,
        subject_id=str(question.id),
        workflow="question_target_answer",
        provider=str(diagnostics.get("classifier_provider") or ""),
        model_name=str(diagnostics.get("classifier_model_name") or "") or None,
        input_summary=answer_text[:1000],
        output_summary=f"target_matched={str(target_matched).lower()},persona_items={len(persona_items)}",
        used_persona_item_ids=[item.id for item in persona_items],
        used_raw_source_ids=[raw_source.id],
        metadata={
            "question_target_id": str(question.id),
            "uncertain_item_id": str(question.uncertain_item_id) if question.uncertain_item_id else None,
            "target_group": question.target_group,
            "target_library_key": question.target_library_key,
            "classification_succeeded": True,
            "target_match_required": True,
            "target_match_succeeded": target_matched,
            "classified_targets": classified_targets,
            "persona_item_ids": persona_item_ids,
            "new_persona_items": len(persona_items),
            "question_target_status": updated_question.status,
            "uncertain_item_status": updated_uncertain_item.status if updated_uncertain_item else None,
        },
    )
    return QuestionAnswerResponse(
        raw_source=raw_source,
        persona_items=persona_items,
        question_target=updated_question,
        uncertain_item=updated_uncertain_item,
        persona_library_classification=classification,
        classification_succeeded=True,
        diagnostics={
            **diagnostics,
            "pii_summary": pii_result.replacements,
            "new_persona_items": len(persona_items),
            "target_match_succeeded": target_matched,
            "target_match_required": True,
            "target_group": question.target_group,
            "target_library_key": question.target_library_key,
            "classified_targets": classified_targets,
            "question_target_status": updated_question.status,
            "uncertain_item_status": updated_uncertain_item.status if updated_uncertain_item else None,
        },
    )
