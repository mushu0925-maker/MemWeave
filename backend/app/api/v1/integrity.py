from __future__ import annotations

from fastapi import APIRouter

from app.schemas.data_integrity import DataIntegrityReport, DataIntegrityRepairResponse
from app.services.data_integrity_service import build_data_integrity_report, repair_data_integrity

router = APIRouter(prefix="/integrity", tags=["integrity"])


@router.get("/report", response_model=DataIntegrityReport)
def read_data_integrity_report() -> DataIntegrityReport:
    return build_data_integrity_report()


@router.post("/repair", response_model=DataIntegrityRepairResponse)
def repair_data_integrity_report() -> DataIntegrityRepairResponse:
    return repair_data_integrity()
