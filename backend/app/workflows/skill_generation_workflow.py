from __future__ import annotations

from uuid import UUID

from app.domains.skills.generation import SkillGenerationInput, generate_skill_v2_minimal
from app.schemas.skill_generation import SkillGenerationResponse
from app.services.monitoring_store import record_monitoring_event
from app.services.persona_item_store import list_persona_items
from app.services.profile_store import get_profile
from app.services.raw_source_store import list_raw_sources
from app.services.runtime_persona_items import (
    build_runtime_gate_diagnostics,
    list_runtime_boundary_items,
    list_runtime_persona_items,
)
from app.services.uncertainty_store import list_question_targets, list_uncertain_items


def _skill_input_audit(profile_id: UUID) -> dict[str, object]:
    all_items = list_persona_items(profile_id, include_hidden=True)
    runtime_items = list_runtime_persona_items(profile_id)
    boundary_items = list_runtime_boundary_items(profile_id)
    gate_report = build_runtime_gate_diagnostics(profile_id)
    gate_summary = gate_report["summary"]
    return {
        "total_persona_items": len(all_items),
        "runtime_input_persona_items": len(runtime_items),
        "runtime_boundary_constraint_items": len(boundary_items),
        "excluded_persona_items": gate_summary.get("blocked_count", 0),
        "excluded_samples": gate_summary.get("blocked_samples", [])[:50],
        "runtime_gate": gate_summary,
    }


def _merge_runtime_and_boundary_items(profile_id: UUID) -> list:
    items = list_runtime_persona_items(profile_id)
    by_id = {item.id: item for item in items}
    for item in list_runtime_boundary_items(profile_id):
        by_id.setdefault(item.id, item)
    return list(by_id.values())


def generate_skill_for_profile(
    profile_id: UUID,
    *,
    include_audit_units: bool = False,
) -> SkillGenerationResponse:
    """Generate a V2 Skill preview from existing A-M libraries without mutating source data."""

    get_profile(profile_id)
    input_audit = _skill_input_audit(profile_id)
    persona_items = _merge_runtime_and_boundary_items(profile_id)
    raw_sources = list_raw_sources(profile_id, include_deleted=True)
    uncertain_items = list_uncertain_items(profile_id, include_closed=True)
    question_targets = list_question_targets(profile_id, include_closed=True)
    try:
        skill = generate_skill_v2_minimal(
            SkillGenerationInput(
                profile_id=profile_id,
                persona_items=persona_items,
                raw_sources=raw_sources,
                uncertain_items=uncertain_items,
                question_targets=question_targets,
                include_audit_units=include_audit_units,
            )
        )
    except Exception as exc:
        record_monitoring_event(
            event_type="skill_generation",
            status="failed",
            profile_id=profile_id,
            subject_id=str(profile_id),
            workflow="generate_skill_for_profile",
            output_summary="skill_generation_failed",
            error=str(exc),
            used_persona_item_ids=[item.id for item in persona_items],
            used_raw_source_ids=[source.id for source in raw_sources],
            metadata={
                "include_audit_units": include_audit_units,
                "persona_item_count": len(persona_items),
                "raw_source_count": len(raw_sources),
                "uncertain_item_count": len(uncertain_items),
                "question_target_count": len(question_targets),
                "input_audit": input_audit,
            },
        )
        raise
    skill = skill.model_copy(
        update={
            "diagnostics": {
                **skill.diagnostics,
                "input_audit": input_audit,
                "runtime_persona_item_ids": [str(item.id) for item in persona_items],
                "used_evidence_persona_item_ids": [str(unit.persona_item_id) for unit in skill.evidence_units],
                "used_evidence_raw_source_ids": [
                    str(unit.source_id) for unit in skill.evidence_units if unit.source_id is not None
                ],
            }
        }
    )
    record_monitoring_event(
        event_type="skill_generation",
        status="success",
        profile_id=profile_id,
        subject_id=str(profile_id),
        workflow="generate_skill_for_profile",
        output_summary=(
            f"evidence_units={len(skill.evidence_units)},audit={len(skill.audit_report)},"
            f"questions={len(skill.question_backlog)}"
        ),
        used_persona_item_ids=[unit.persona_item_id for unit in skill.evidence_units],
        used_raw_source_ids=[source.id for source in raw_sources],
        metadata={
            "include_audit_units": include_audit_units,
            "skill_version": skill.version,
            "skill_markdown_present": bool(skill.skill_markdown.strip()),
            "evidence_unit_count": len(skill.evidence_units),
            "audit_count": len(skill.audit_report),
            "question_backlog_count": len(skill.question_backlog),
            "persona_item_count": len(persona_items),
            "raw_source_count": len(raw_sources),
            "input_audit": input_audit,
            "used_evidence_persona_item_ids": [str(unit.persona_item_id) for unit in skill.evidence_units],
            "used_evidence_raw_source_ids": [
                str(unit.source_id) for unit in skill.evidence_units if unit.source_id is not None
            ],
        },
    )
    return skill
