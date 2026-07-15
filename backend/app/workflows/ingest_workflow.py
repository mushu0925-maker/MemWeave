from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.core.security import mask_pii
from app.schemas.ingest import IngestRequest, IngestResponse
from app.schemas.memory import SourceType
from app.schemas.persona_classification import PersonaLibraryClassificationResult
from app.schemas.persona_item import PersonaItemCreate, PersonaItemSchema
from app.schemas.raw_source import RawSourceCreate, RawSourceSchema
from app.services.distillation_plugin_store import can_distillation_write
from app.services.persona_core_libraries import PERSONA_LIBRARY_DEFINITIONS
from app.services.persona_input_classifier import classify_persona_source
from app.services.persona_item_store import save_persona_items
from app.services.monitoring_store import record_monitoring_event
from app.services.persona_mapping import library_group_from_category, status_from_classification
from app.services.profile_store import get_profile, touch_profile
from app.services.raw_source_store import save_raw_source, update_raw_source_content
from app.services.source_segment_store import ensure_source_segments_for_raw_source, list_extracted_segments
from app.services.media_extraction import ExtractedSource, StoredUpload
from app.services.voice_feature_service import create_voice_feature_question
from app.workflows.uncertainty_workflow import create_uncertainty_from_coverage_warnings


@dataclass(frozen=True)
class IngestClassificationFailure(Exception):
    """A-M 分类失败，但 raw_source 已经保存；API 层负责把它映射成 HTTP 422。"""

    status: str
    reason: str
    provider: str
    model_name: str | None
    notes: list[str]
    raw_source: RawSourceSchema
    plugin_metadata: dict[str, Any]
    candidate_library_keys: list[str]

    def to_http_detail(self) -> dict[str, Any]:
        return {
            "message": "A-M 分类失败，但原数据已保留，可之后重新提取。",
            "raw_source_id": str(self.raw_source.id),
            "model_call_status": self.status,
            "model_call_reason": self.reason,
            "model_provider": self.provider,
            "model_name": self.model_name,
            "notes": self.notes,
            "plugin_metadata": self.plugin_metadata,
            "candidate_library_keys": self.candidate_library_keys,
        }


def _persona_item_payloads(
    *,
    profile_id: UUID,
    raw_source: RawSourceSchema,
    classification: PersonaLibraryClassificationResult,
    extraction_method: str,
    model_name: str | None,
) -> list[PersonaItemCreate]:
    """把 AI 分类结果转成可保存的 persona_items；这里不生成任何本地保底条目。"""

    payloads: list[PersonaItemCreate] = []
    for item in classification.items:
        definition = PERSONA_LIBRARY_DEFINITIONS.get(item.library_key)
        if definition is None:
            continue
        payloads.append(
            PersonaItemCreate(
                profile_id=profile_id,
                source_id=raw_source.id,
                library_group=library_group_from_category(definition.category, item.library_key),
                library_key=item.library_key,
                signal=item.signal,
                evidence_quote=item.evidence_quote,
                evidence_time_range=item.time_scope,
                confidence=item.confidence,
                stability=item.stability,
                subject_scope=item.subject_scope,
                write_target=item.write_target,
                risk=item.risk,
                prompt_snippet=item.prompt_snippet,
                extraction_method=extraction_method,
                model_name=model_name,
                status=status_from_classification(
                    write_target=item.write_target,
                    risk=item.risk,
                    confidence=item.confidence,
                    stability=item.stability,
                ),
                metadata={
                    "evidence_relation": item.evidence_relation,
                    "usage": item.usage,
                    "tags": item.tags,
                    "priority": item.priority,
                    "classification_status": extraction_method,
                },
            )
        )
    return payloads


def classify_raw_source(
    raw_source: RawSourceSchema,
) -> tuple[PersonaLibraryClassificationResult, dict[str, object], str, str | None]:
    """调用当前配置模型分类 raw_source；失败时保留原数据并抛出业务异常。"""

    classification = classify_persona_source(
        source_type=raw_source.source_type,
        metadata={
            **raw_source.metadata,
            "raw_source_id": str(raw_source.id),
            "profile_id": str(raw_source.profile_id) if raw_source.profile_id else None,
        },
        content=raw_source.pii_masked_text or raw_source.extracted_text or raw_source.original_text,
    )
    diagnostics: dict[str, object] = {
        "classifier_provider": classification.provider,
        "classifier_model_call_status": classification.model_call_status,
        "classifier_model_call_reason": classification.model_call_reason,
        "classifier_model_name": classification.model_name,
        "candidate_library_keys": classification.candidate_library_keys,
        "notes": classification.notes,
        "coverage_warnings": classification.coverage_warnings,
        "plugin_metadata": classification.plugin_metadata,
    }
    if classification.model_call_status != "success" or classification.result is None:
        raise IngestClassificationFailure(
            status=classification.model_call_status,
            reason=classification.model_call_reason,
            provider=classification.provider,
            model_name=classification.model_name,
            notes=classification.notes,
            raw_source=raw_source,
            plugin_metadata=classification.plugin_metadata,
            candidate_library_keys=classification.candidate_library_keys,
        )

    return (
        classification.result,
        diagnostics,
        classification.model_call_reason,
        classification.model_name,
    )


def save_classification_persona_items(
    *,
    raw_source: RawSourceSchema,
    classification: PersonaLibraryClassificationResult,
    extraction_method: str,
    model_name: str | None,
) -> list[PersonaItemSchema]:
    """把分类结果写入 A-M 个人库；没有 profile 时只保留 raw_source。"""

    if raw_source.profile_id is None:
        return []
    if not can_distillation_write("persona_item"):
        return []

    persona_items = save_persona_items(
        _persona_item_payloads(
            profile_id=raw_source.profile_id,
            raw_source=raw_source,
            classification=classification,
            extraction_method=extraction_method,
            model_name=model_name,
        )
    )
    touch_profile(raw_source.profile_id)
    return persona_items


def classify_raw_source_into_persona_items(
    raw_source: RawSourceSchema,
) -> tuple[PersonaLibraryClassificationResult, list[PersonaItemSchema], dict[str, object]]:
    """完整的 raw_source -> persona_items 编排，供 ingest 和 reextract 复用。"""

    try:
        classification_result, diagnostics, extraction_method, model_name = classify_raw_source(raw_source)
        persona_items = save_classification_persona_items(
            raw_source=raw_source,
            classification=classification_result,
            extraction_method=extraction_method,
            model_name=model_name,
        )
        if not can_distillation_write("persona_item"):
            diagnostics["persona_item_write_skipped"] = True
            diagnostics["persona_item_write_skip_reason"] = "distillation_plugin_write_rules_block_persona_item"
        persist_uncertainty_from_diagnostics(raw_source=raw_source, diagnostics=diagnostics)
    except IngestClassificationFailure as exc:
        if can_distillation_write("monitoring_event"):
            record_monitoring_event(
                event_type="distillation",
                status="failed",
                profile_id=raw_source.profile_id,
                raw_source_id=raw_source.id,
                subject_id=str(raw_source.id),
                workflow="raw_source_classification",
                provider=exc.provider,
                model_name=exc.model_name,
                input_summary=(raw_source.pii_masked_text or raw_source.extracted_text or raw_source.original_text)[:1000],
                output_summary="classification_failed",
                error=exc.reason,
                metadata={
                    "profile_id": str(raw_source.profile_id) if raw_source.profile_id else None,
                    "raw_source_id": str(raw_source.id),
                    "notes": exc.notes,
                    "model_call_status": exc.status,
                    "model_call_reason": exc.reason,
                    "model_provider": exc.provider,
                    "model_name": exc.model_name,
                    "candidate_library_keys": exc.candidate_library_keys,
                    "plugin_metadata": exc.plugin_metadata,
                    "new_persona_item_ids": [],
                    "new_persona_items": 0,
                },
            )
        raise
    if can_distillation_write("monitoring_event"):
        record_monitoring_event(
            event_type="distillation",
            status="success",
            profile_id=raw_source.profile_id,
            raw_source_id=raw_source.id,
            subject_id=str(raw_source.id),
            workflow="raw_source_classification",
            provider=str(diagnostics.get("classifier_provider") or ""),
            model_name=model_name,
            input_summary=(raw_source.pii_masked_text or raw_source.extracted_text or raw_source.original_text)[:1000],
            output_summary=f"persona_items={len(persona_items)},coverage_warnings={len(diagnostics.get('coverage_warnings') or [])}",
            used_persona_item_ids=[item.id for item in persona_items],
            used_raw_source_ids=[raw_source.id],
            metadata={
                "profile_id": str(raw_source.profile_id) if raw_source.profile_id else None,
                "raw_source_id": str(raw_source.id),
                "persona_item_count": len(persona_items),
                "new_persona_items": len(persona_items),
                "new_persona_item_ids": [str(item.id) for item in persona_items],
                "coverage_warning_count": len(diagnostics.get("coverage_warnings") or []),
                "candidate_library_keys": diagnostics.get("candidate_library_keys") or [],
                "model_call_status": diagnostics.get("classifier_model_call_status"),
                "model_call_reason": diagnostics.get("classifier_model_call_reason"),
                "model_provider": diagnostics.get("classifier_provider"),
                "model_name": model_name,
                "plugin_metadata": diagnostics.get("plugin_metadata") or {},
            },
        )
    return classification_result, persona_items, diagnostics


def persist_uncertainty_from_diagnostics(
    *,
    raw_source: RawSourceSchema,
    diagnostics: dict[str, object],
) -> None:
    """把覆盖不足诊断写入不确定项和追问目标；不写 persona_items。"""

    coverage_warnings = diagnostics.get("coverage_warnings")
    if not isinstance(coverage_warnings, list):
        return
    if not can_distillation_write("uncertain_item") or not can_distillation_write("question_target"):
        diagnostics.update(
            {
                "uncertainty_write_skipped": True,
                "uncertainty_write_skip_reason": "distillation_plugin_write_rules_block_uncertain_or_question",
            }
        )
        return
    warning_dicts = [warning for warning in coverage_warnings if isinstance(warning, dict)]
    result = create_uncertainty_from_coverage_warnings(raw_source, warning_dicts)
    diagnostics.update(result.diagnostics())


def _attach_segment_diagnostics(raw_source: RawSourceSchema, diagnostics: dict[str, Any]) -> None:
    source_segments = ensure_source_segments_for_raw_source(raw_source)
    extracted_segments = list_extracted_segments(raw_source_id=raw_source.id)
    diagnostics["source_segment_count"] = len(source_segments)
    diagnostics["source_segment_ids"] = [str(segment.id) for segment in source_segments]
    diagnostics["extracted_segment_count"] = len(extracted_segments)
    diagnostics["segment_attribution_status"] = "pending"


def _image_extraction_unavailable(raw_source: RawSourceSchema) -> bool:
    return (
        raw_source.source_type == "image"
        and str(raw_source.metadata.get("extraction_status") or "") in {"disabled", "not_configured", "failed"}
    )


def build_ingest_response_for_raw_source(
    raw_source: RawSourceSchema,
    *,
    pii_summary: dict[str, int],
    routing_suffix: str,
) -> IngestResponse:
    """Classify a persisted raw_source and return the standard ingest response."""

    try:
        classification_result, persona_items, diagnostics = classify_raw_source_into_persona_items(raw_source)
    except IngestClassificationFailure as exc:
        if _image_extraction_unavailable(raw_source):
            diagnostics = {
                "classifier_provider": exc.provider,
                "classifier_model_call_status": exc.status,
                "classifier_model_call_reason": exc.reason,
                "classifier_model_name": exc.model_name,
                "candidate_library_keys": exc.candidate_library_keys,
                "notes": exc.notes,
                "plugin_metadata": exc.plugin_metadata,
                "classification_status": "skipped_after_unavailable_image_extraction",
                "classification_failure_preserved_raw_source": True,
                "extraction_status": raw_source.metadata.get("extraction_status"),
                "extraction_provider": raw_source.metadata.get("extraction_provider"),
                "extraction_error": raw_source.metadata.get("extraction_error"),
                "extraction_hint": raw_source.metadata.get("extraction_hint"),
            }
            _attach_segment_diagnostics(raw_source, diagnostics)
            return IngestResponse(
                raw_source=raw_source,
                persona_items=[],
                sanitized_content=raw_source.pii_masked_text,
                pii_summary=pii_summary,
                routing_key=f"{raw_source.source_type}:{routing_suffix}",
                persona_library_classification=None,
                diagnostics=diagnostics,
            )
        raise
    _attach_segment_diagnostics(raw_source, diagnostics)
    voice_question = create_voice_feature_question(raw_source)
    if voice_question is not None:
        diagnostics["voice_feature_question_target_id"] = str(voice_question.id)
        diagnostics["voice_feature_target_group"] = voice_question.target_group
        diagnostics["voice_feature_target_library_key"] = voice_question.target_library_key
        diagnostics["voice_feature_safety"] = raw_source.metadata.get("voice_feature_safety", "")

    return IngestResponse(
        raw_source=raw_source,
        persona_items=persona_items,
        sanitized_content=raw_source.pii_masked_text,
        pii_summary=pii_summary,
        routing_key=f"{raw_source.source_type}:{routing_suffix}",
        persona_library_classification=classification_result,
        diagnostics=diagnostics,
    )


def ingest_payload(
    *,
    payload: IngestRequest,
    original_text: str,
    routing_suffix: str,
) -> IngestResponse:
    """ingest 主流程：先保存原数据，再分类，再写 persona_items。"""

    if payload.profile_id is not None:
        get_profile(payload.profile_id)

    pii_result = mask_pii(payload.raw_content)
    file_path_value = payload.metadata.get("stored_file_path") or payload.metadata.get("file_path")
    file_name_value = payload.metadata.get("filename") or payload.metadata.get("stored_file_name")
    mime_type_value = payload.metadata.get("content_type")
    raw_source = save_raw_source(
        RawSourceCreate(
            profile_id=payload.profile_id,
            source_type=payload.source_type,
            original_text=original_text,
            extracted_text=payload.raw_content,
            pii_masked_text=pii_result.content,
            file_path=str(file_path_value or "") or None,
            file_name=str(file_name_value or "") or None,
            mime_type=str(mime_type_value or "") or None,
            metadata=payload.metadata,
        )
    )

    return build_ingest_response_for_raw_source(
        raw_source,
        pii_summary=pii_result.replacements,
        routing_suffix=routing_suffix,
    )


def _uploaded_placeholder_content(
    *,
    source_type: SourceType,
    filename: str | None,
    content_type: str,
    size_bytes: int,
    notes: str,
) -> str:
    lines = [
        f"Uploaded {source_type} source.",
        f"Original filename: {filename or 'untitled'}",
        f"Content type: {content_type}",
        f"Size bytes: {size_bytes}",
        "Extraction status: pending raw-first processing.",
    ]
    if notes.strip():
        lines.extend(["", "Uploader notes:", notes.strip()])
    return "\n".join(lines)


def save_raw_first_uploaded_source(
    *,
    source_type: SourceType,
    stored_upload: StoredUpload,
    filename: str | None,
    content_type: str | None,
    notes: str,
    profile_id: UUID | None,
) -> tuple[RawSourceSchema, dict[str, int]]:
    """Create the evidence record before extraction or classification runs."""

    if profile_id is not None:
        get_profile(profile_id)
    normalized_content_type = content_type or "application/octet-stream"
    raw_content = _uploaded_placeholder_content(
        source_type=source_type,
        filename=filename,
        content_type=normalized_content_type,
        size_bytes=stored_upload.size_bytes,
        notes=notes,
    )
    pii_result = mask_pii(raw_content)
    raw_source = save_raw_source(
        RawSourceCreate(
            profile_id=profile_id,
            source_type=source_type,
            original_text=raw_content,
            extracted_text=raw_content,
            file_path=stored_upload.file_path,
            file_name=filename or stored_upload.stored_filename,
            mime_type=normalized_content_type,
            pii_masked_text=pii_result.content,
            metadata={
                "filename": filename,
                "content_type": normalized_content_type,
                "size_bytes": stored_upload.size_bytes,
                "upload_kind": source_type,
                "stored_file_path": stored_upload.file_path,
                "stored_file_name": stored_upload.stored_filename,
                "uploaded_file_sha256": stored_upload.sha256,
                "upload_notes": notes.strip(),
                "raw_first_preserved": True,
                "extraction_status": "pending",
            },
        )
    )
    return raw_source, pii_result.replacements


def ingest_extracted_upload(
    *,
    raw_source: RawSourceSchema,
    extracted: ExtractedSource,
    stored_upload: StoredUpload,
    filename: str | None,
    content_type: str | None,
    notes: str,
) -> IngestResponse:
    normalized_content_type = content_type or "application/octet-stream"
    metadata = {
        **raw_source.metadata,
        **extracted.metadata,
        "stored_file_path": stored_upload.file_path,
        "stored_file_name": stored_upload.stored_filename,
        "uploaded_file_sha256": stored_upload.sha256,
        "upload_notes": notes.strip(),
        "raw_first_preserved": True,
    }
    pii_result = mask_pii(extracted.raw_content)
    updated_source = update_raw_source_content(
        raw_source.id,
        original_text=extracted.raw_content,
        extracted_text=extracted.raw_content,
        pii_masked_text=pii_result.content,
        file_path=stored_upload.file_path,
        file_name=filename or stored_upload.stored_filename,
        mime_type=normalized_content_type,
        metadata=metadata,
    )
    return build_ingest_response_for_raw_source(
        updated_source,
        pii_summary=pii_result.replacements,
        routing_suffix="file",
    )


def uploaded_extraction_failed_response(
    *,
    raw_source: RawSourceSchema,
    error_detail: object,
    status_code: int | None = None,
) -> IngestResponse:
    error_text = str(error_detail)
    metadata = {
        **raw_source.metadata,
        "extraction_status": "failed",
        "extraction_error": error_text,
        "extraction_http_status": status_code,
        "classification_status": "skipped_after_extraction_failure",
        "extraction_failure_preserved_raw_source": True,
    }
    raw_content = (
        f"{raw_source.original_text}\n\n"
        "Extraction failed after the original upload was preserved.\n"
        f"Failure detail: {error_text}"
    )
    pii_result = mask_pii(raw_content)
    updated_source = update_raw_source_content(
        raw_source.id,
        original_text=raw_content,
        extracted_text=raw_content,
        pii_masked_text=pii_result.content,
        file_path=raw_source.file_path,
        file_name=raw_source.file_name,
        mime_type=raw_source.mime_type,
        metadata=metadata,
    )
    diagnostics: dict[str, Any] = {
        "extraction_status": "failed",
        "extraction_error": error_text,
        "extraction_http_status": status_code,
        "classification_status": "skipped_after_extraction_failure",
        "extraction_failure_preserved_raw_source": True,
    }
    _attach_segment_diagnostics(updated_source, diagnostics)
    return IngestResponse(
        raw_source=updated_source,
        persona_items=[],
        sanitized_content=updated_source.pii_masked_text,
        pii_summary=pii_result.replacements,
        routing_key=f"{updated_source.source_type}:file",
        persona_library_classification=None,
        diagnostics=diagnostics,
    )
