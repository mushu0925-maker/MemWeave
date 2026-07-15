from __future__ import annotations

from fastapi import APIRouter

from app.schemas.quality_validation import QualityValidationRequest, QualityValidationResponse
from app.services.quality_validation_service import validate_chat_quality, validate_skill_quality

router = APIRouter(prefix="/quality-validation", tags=["quality_validation"])


@router.post("/chat", response_model=QualityValidationResponse)
def validate_chat_quality_endpoint(payload: QualityValidationRequest) -> QualityValidationResponse:
    return validate_chat_quality(payload)


@router.post("/skill", response_model=QualityValidationResponse)
def validate_skill_quality_endpoint(payload: QualityValidationRequest) -> QualityValidationResponse:
    return validate_skill_quality(payload)
