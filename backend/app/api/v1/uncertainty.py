from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.schemas.clarification import (
    QuestionAnswerRequest,
    QuestionAnswerResponse,
    QuestionTargetSchema,
    UncertainItemActionRequest,
    UncertainItemActionResponse,
    UncertainItemSchema,
)
from app.services.profile_store import get_profile
from app.services.uncertainty_store import list_question_targets, list_uncertain_items
from app.workflows.question_answer_workflow import answer_question_target
from app.workflows.uncertainty_action_workflow import apply_uncertain_item_action

router = APIRouter(tags=["uncertainty"])


@router.get("/uncertain-items", response_model=list[UncertainItemSchema])
def read_uncertain_items(
    profile_id: UUID | None = Query(default=None),
    include_closed: bool = Query(default=False),
) -> list[UncertainItemSchema]:
    if profile_id is not None:
        get_profile(profile_id)
    return list_uncertain_items(profile_id, include_closed=include_closed)


@router.get("/question-targets", response_model=list[QuestionTargetSchema])
def read_question_targets(
    profile_id: UUID | None = Query(default=None),
    include_closed: bool = Query(default=False),
) -> list[QuestionTargetSchema]:
    if profile_id is not None:
        get_profile(profile_id)
    return list_question_targets(profile_id, include_closed=include_closed)


@router.post("/question-targets/{question_id}/answer", response_model=QuestionAnswerResponse)
def submit_question_target_answer(question_id: UUID, payload: QuestionAnswerRequest) -> QuestionAnswerResponse:
    return answer_question_target(question_id, payload)


@router.post("/uncertain-items/{item_id}/action", response_model=UncertainItemActionResponse)
def submit_uncertain_item_action(item_id: UUID, payload: UncertainItemActionRequest) -> UncertainItemActionResponse:
    return apply_uncertain_item_action(item_id, payload)
