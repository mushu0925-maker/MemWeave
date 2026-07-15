from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas.ingest import IngestRequest, IngestResponse
from app.services.media_extraction import extract_uploaded_source, source_type_from_upload, store_uploaded_source_stream
from app.workflows.ingest_workflow import (
    IngestClassificationFailure,
    ingest_extracted_upload,
    ingest_payload,
    save_raw_first_uploaded_source,
    uploaded_extraction_failed_response,
)

router = APIRouter(prefix="/ingest", tags=["ingest"])


def _raise_http_failure(exc: IngestClassificationFailure) -> None:
    """路由层只负责把 workflow 的业务失败转换成 HTTP 语义。"""

    raise HTTPException(status_code=422, detail=exc.to_http_detail()) from exc


@router.post("", response_model=IngestResponse)
def ingest_text(payload: IngestRequest) -> IngestResponse:
    try:
        return ingest_payload(payload=payload, original_text=payload.raw_content, routing_suffix="text")
    except IngestClassificationFailure as exc:
        _raise_http_failure(exc)


@router.post("/file", response_model=IngestResponse)
async def ingest_uploaded_file(
    upload: UploadFile = File(...),
    notes: str = Form(default=""),
    profile_id: UUID | None = Form(default=None),
) -> IngestResponse:
    stored_upload = await store_uploaded_source_stream(upload, profile_id=profile_id)
    source_type = source_type_from_upload(upload.content_type, upload.filename)
    raw_source, _pii_summary = save_raw_first_uploaded_source(
        source_type=source_type,  # type: ignore[arg-type]
        stored_upload=stored_upload,
        filename=upload.filename,
        content_type=upload.content_type,
        notes=notes,
        profile_id=profile_id,
    )
    try:
        data = Path(stored_upload.file_path).read_bytes()
        extracted = extract_uploaded_source(
            data,
            filename=upload.filename,
            content_type=upload.content_type,
            notes=notes,
        )
    except HTTPException as exc:
        return uploaded_extraction_failed_response(
            raw_source=raw_source,
            error_detail=exc.detail,
            status_code=exc.status_code,
        )
    except Exception as exc:
        return uploaded_extraction_failed_response(
            raw_source=raw_source,
            error_detail=f"{exc.__class__.__name__}: {exc}",
            status_code=500,
        )
    try:
        return ingest_extracted_upload(
            raw_source=raw_source,
            extracted=extracted,
            stored_upload=stored_upload,
            filename=upload.filename,
            content_type=upload.content_type,
            notes=notes,
        )
    except IngestClassificationFailure as exc:
        _raise_http_failure(exc)
