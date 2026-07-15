from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.schemas.data_integrity import DataIntegrityIssue, DataIntegrityReport, DataIntegrityRepairResponse
from app.services.chat_store import clear_chat_records, delete_chat_records_by_ids, list_all_chat_records
from app.services.persona_item_store import hide_persona_items_by_ids, list_persona_items
from app.services.profile_store import list_profiles
from app.services.raw_source_store import detach_raw_sources_from_profile, list_raw_sources
from app.services.skill_version_store import delete_skill_versions, delete_skill_versions_by_ids, list_all_skill_versions
from app.services.uncertainty_store import (
    delete_question_targets,
    delete_question_targets_by_ids,
    delete_uncertain_items,
    delete_uncertain_items_by_ids,
    list_question_targets,
    list_uncertain_items,
)

INTEGRITY_REPAIR_REASON = "data_integrity_repair"


def _now() -> datetime:
    return datetime.now(UTC)


def _id(value: UUID | None) -> str | None:
    return str(value) if value is not None else None


def _issue(
    *,
    issue_type: str,
    severity: str,
    record_type: str,
    record_id: str,
    profile_id: str | None = None,
    source_id: str | None = None,
    action: str,
    details: dict[str, Any] | None = None,
) -> DataIntegrityIssue:
    return DataIntegrityIssue(
        type=issue_type,
        severity=severity,  # type: ignore[arg-type]
        record_type=record_type,
        record_id=record_id,
        profile_id=profile_id,
        source_id=source_id,
        action=action,
        details=details or {},
    )


def _summary_diff(before: DataIntegrityReport, after: DataIntegrityReport) -> dict[str, int]:
    keys = sorted(set(before.summary) | set(after.summary))
    diff = {key: after.summary.get(key, 0) - before.summary.get(key, 0) for key in keys}
    diff["total_removed"] = before.summary.get("total", 0) - after.summary.get("total", 0)
    diff["runtime_blockers_removed"] = before.summary.get("severity_runtime_blocker", 0) - after.summary.get(
        "severity_runtime_blocker",
        0,
    )
    return diff


def build_data_integrity_report() -> DataIntegrityReport:
    active_profiles = {profile.id for profile in list_profiles()}
    raw_sources = list_raw_sources(include_deleted=True)
    raw_source_ids = {source.id for source in raw_sources}
    active_raw_source_ids = {source.id for source in raw_sources if source.deleted_at is None}
    raw_source_profile_ids = {source.id: source.profile_id for source in raw_sources}
    persona_items = list_persona_items(include_hidden=True)
    persona_item_ids = {item.id for item in persona_items}
    visible_persona_item_ids = {
        item.id
        for item in persona_items
        if item.status not in {"hidden", "forgotten", "deleted"}
    }
    persona_item_profile_ids = {item.id: item.profile_id for item in persona_items}
    uncertain_items = list_uncertain_items(include_closed=True)
    question_targets = list_question_targets(include_closed=True)
    chat_records = list_all_chat_records()
    skill_versions = list_all_skill_versions()
    issues: list[DataIntegrityIssue] = []

    for source in raw_sources:
        if source.profile_id is not None and source.profile_id not in active_profiles:
            issues.append(
                _issue(
                    issue_type="raw_source_missing_profile",
                    severity="warning",
                    record_type="raw_source",
                    record_id=str(source.id),
                    profile_id=str(source.profile_id),
                    action="detach_raw_source_from_missing_profile",
                )
            )

    for item in persona_items:
        is_isolated = item.status in {"hidden", "forgotten", "deleted"}
        if item.profile_id not in active_profiles:
            if is_isolated:
                issues.append(
                    _issue(
                        issue_type="isolated_persona_item_missing_profile",
                        severity="info",
                        record_type="persona_item",
                        record_id=str(item.id),
                        profile_id=str(item.profile_id),
                        source_id=_id(item.source_id),
                        action="no_runtime_use",
                    )
                )
                continue
            issues.append(
                _issue(
                    issue_type="persona_item_missing_profile",
                    severity="runtime_blocker",
                    record_type="persona_item",
                    record_id=str(item.id),
                    profile_id=str(item.profile_id),
                    source_id=_id(item.source_id),
                    action="hide_persona_item",
                )
            )
        if item.source_id is None:
            if is_isolated:
                issues.append(
                    _issue(
                        issue_type="isolated_persona_item_missing_source_id",
                        severity="info",
                        record_type="persona_item",
                        record_id=str(item.id),
                        profile_id=str(item.profile_id),
                        action="no_runtime_use",
                    )
                )
                continue
            issues.append(
                _issue(
                    issue_type="persona_item_missing_source_id",
                    severity="runtime_blocker",
                    record_type="persona_item",
                    record_id=str(item.id),
                    profile_id=str(item.profile_id),
                    action="hide_persona_item",
                )
            )
            continue
        source_profile_id = raw_source_profile_ids.get(item.source_id)
        if item.source_id not in raw_source_ids:
            if is_isolated:
                issues.append(
                    _issue(
                        issue_type="isolated_persona_item_missing_raw_source",
                        severity="info",
                        record_type="persona_item",
                        record_id=str(item.id),
                        profile_id=str(item.profile_id),
                        source_id=str(item.source_id),
                        action="no_runtime_use",
                    )
                )
                continue
            issues.append(
                _issue(
                    issue_type="persona_item_missing_raw_source",
                    severity="runtime_blocker",
                    record_type="persona_item",
                    record_id=str(item.id),
                    profile_id=str(item.profile_id),
                    source_id=str(item.source_id),
                    action="hide_persona_item",
                )
            )
        elif source_profile_id != item.profile_id:
            if is_isolated:
                issues.append(
                    _issue(
                        issue_type="isolated_persona_item_source_profile_mismatch",
                        severity="info",
                        record_type="persona_item",
                        record_id=str(item.id),
                        profile_id=str(item.profile_id),
                        source_id=str(item.source_id),
                        action="no_runtime_use",
                        details={"raw_source_profile_id": _id(source_profile_id)},
                    )
                )
                continue
            issues.append(
                _issue(
                    issue_type="persona_item_source_profile_mismatch",
                    severity="runtime_blocker",
                    record_type="persona_item",
                    record_id=str(item.id),
                    profile_id=str(item.profile_id),
                    source_id=str(item.source_id),
                    action="hide_persona_item",
                    details={"raw_source_profile_id": _id(source_profile_id)},
                )
            )

    for item in uncertain_items:
        if item.profile_id not in active_profiles:
            issues.append(
                _issue(
                    issue_type="uncertain_item_missing_profile",
                    severity="derived_orphan",
                    record_type="uncertain_item",
                    record_id=str(item.id),
                    profile_id=str(item.profile_id),
                    source_id=_id(item.source_id),
                    action="delete_derived_uncertain_items_for_missing_profile",
                )
            )
        if item.source_id is not None and item.source_id not in raw_source_ids:
            issues.append(
                _issue(
                    issue_type="uncertain_item_missing_raw_source",
                    severity="derived_orphan",
                    record_type="uncertain_item",
                    record_id=str(item.id),
                    profile_id=str(item.profile_id),
                    source_id=str(item.source_id),
                    action="delete_derived_uncertain_items_for_profile",
                )
            )

    for question in question_targets:
        if question.profile_id not in active_profiles:
            issues.append(
                _issue(
                    issue_type="question_target_missing_profile",
                    severity="derived_orphan",
                    record_type="question_target",
                    record_id=str(question.id),
                    profile_id=str(question.profile_id),
                    source_id=_id(question.source_id),
                    action="delete_derived_question_targets_for_missing_profile",
                )
            )
        if question.source_id is not None and question.source_id not in raw_source_ids:
            issues.append(
                _issue(
                    issue_type="question_target_missing_raw_source",
                    severity="derived_orphan",
                    record_type="question_target",
                    record_id=str(question.id),
                    profile_id=str(question.profile_id),
                    source_id=str(question.source_id),
                    action="delete_derived_question_targets_for_profile",
                )
            )

    for record in chat_records:
        if record.profile_id not in active_profiles:
            issues.append(
                _issue(
                    issue_type="chat_record_missing_profile",
                    severity="derived_orphan",
                    record_type="chat_record",
                    record_id=str(record.id),
                    profile_id=str(record.profile_id),
                    action="delete_derived_chat_record",
                )
            )
            continue
        broken_persona_ids = [
            item_id
            for item_id in record.used_persona_item_ids
            if item_id not in visible_persona_item_ids or persona_item_profile_ids.get(item_id) != record.profile_id
        ]
        broken_raw_ids = [
            source_id
            for source_id in record.used_raw_source_ids
            if source_id not in active_raw_source_ids or raw_source_profile_ids.get(source_id) != record.profile_id
        ]
        if broken_persona_ids or broken_raw_ids:
            issues.append(
                _issue(
                    issue_type="chat_record_broken_runtime_reference",
                    severity="runtime_blocker",
                    record_type="chat_record",
                    record_id=str(record.id),
                    profile_id=str(record.profile_id),
                    action="delete_derived_chat_record",
                    details={
                        "broken_persona_item_ids": [str(item_id) for item_id in broken_persona_ids],
                        "broken_raw_source_ids": [str(source_id) for source_id in broken_raw_ids],
                    },
                )
            )

    for version in skill_versions:
        if version.profile_id not in active_profiles:
            issues.append(
                _issue(
                    issue_type="skill_version_missing_profile",
                    severity="derived_orphan",
                    record_type="skill_version",
                    record_id=str(version.id),
                    profile_id=str(version.profile_id),
                    action="delete_derived_skill_version",
                )
            )
            continue
        broken_units = []
        for unit in version.skill_json.evidence_units:
            if unit.persona_item_id not in persona_item_ids:
                broken_units.append(
                    {
                        "unit_id": unit.unit_id,
                        "persona_item_id": str(unit.persona_item_id),
                        "source_id": _id(unit.source_id),
                        "reason": "missing_persona_item",
                    }
                )
                continue
            if persona_item_profile_ids.get(unit.persona_item_id) != version.profile_id:
                broken_units.append(
                    {
                        "unit_id": unit.unit_id,
                        "persona_item_id": str(unit.persona_item_id),
                        "source_id": _id(unit.source_id),
                        "reason": "persona_item_profile_mismatch",
                    }
                )
                continue
            if (unit.usage.can_retrieve or unit.usage.can_generate_style or unit.usage.can_state_as_fact) and (
                unit.source_id is None
                or unit.source_id not in active_raw_source_ids
                or raw_source_profile_ids.get(unit.source_id) != version.profile_id
            ):
                broken_units.append(
                    {
                        "unit_id": unit.unit_id,
                        "persona_item_id": str(unit.persona_item_id),
                        "source_id": _id(unit.source_id),
                        "reason": "runtime_unit_missing_live_raw_source",
                    }
                )
        if broken_units:
            issues.append(
                _issue(
                    issue_type="skill_version_broken_runtime_reference",
                    severity="runtime_blocker",
                    record_type="skill_version",
                    record_id=str(version.id),
                    profile_id=str(version.profile_id),
                    action="delete_derived_skill_version",
                    details={"broken_units": broken_units[:50], "broken_unit_count": len(broken_units)},
                )
            )

    summary = Counter(issue.type for issue in issues)
    summary["total"] = len(issues)
    for severity in ("info", "warning", "runtime_blocker", "derived_orphan"):
        summary[f"severity_{severity}"] = sum(1 for issue in issues if issue.severity == severity)
    return DataIntegrityReport(
        generated_at=_now(),
        summary=dict(summary),
        issues=sorted(issues, key=lambda issue: (issue.severity, issue.type, issue.record_type, issue.record_id)),
    )


def repair_data_integrity() -> DataIntegrityRepairResponse:
    before = build_data_integrity_report()
    missing_profile_ids: set[UUID] = set()
    persona_item_ids_to_hide: set[UUID] = set()
    derived_profile_ids_to_clear: set[UUID] = set()
    uncertain_item_ids_to_delete: set[UUID] = set()
    question_target_ids_to_delete: set[UUID] = set()
    chat_record_ids_to_delete: set[UUID] = set()
    skill_version_ids_to_delete: set[UUID] = set()
    actions: list[dict[str, Any]] = []

    for issue in before.issues:
        if issue.type == "raw_source_missing_profile" and issue.profile_id is not None:
            missing_profile_ids.add(UUID(issue.profile_id))
        if issue.record_type == "persona_item" and issue.record_id and issue.severity == "runtime_blocker":
            persona_item_ids_to_hide.add(UUID(issue.record_id))
        if issue.record_type == "uncertain_item" and issue.record_id:
            uncertain_item_ids_to_delete.add(UUID(issue.record_id))
        if issue.record_type == "question_target" and issue.record_id:
            question_target_ids_to_delete.add(UUID(issue.record_id))
        if issue.record_type == "chat_record" and issue.record_id:
            chat_record_ids_to_delete.add(UUID(issue.record_id))
        if issue.record_type == "skill_version" and issue.record_id:
            skill_version_ids_to_delete.add(UUID(issue.record_id))
        if issue.record_type in {"uncertain_item", "question_target"} and issue.profile_id is not None and issue.type.endswith("_missing_profile"):
            derived_profile_ids_to_clear.add(UUID(issue.profile_id))

    repaired_counts: dict[str, int] = {}
    detached = 0
    for profile_id in missing_profile_ids:
        detached += detach_raw_sources_from_profile(profile_id, reason=INTEGRITY_REPAIR_REASON)
    repaired_counts["raw_sources_detached"] = detached
    if detached:
        actions.append(
            {
                "action": "detach_raw_sources_from_missing_profiles",
                "count": detached,
                "policy": "non_destructive_raw_source_preservation",
            }
        )
    repaired_counts["persona_items_hidden"] = hide_persona_items_by_ids(
        persona_item_ids_to_hide,
        reason=INTEGRITY_REPAIR_REASON,
    )
    if repaired_counts["persona_items_hidden"]:
        actions.append(
            {
                "action": "hide_broken_persona_items",
                "count": repaired_counts["persona_items_hidden"],
                "record_ids": [str(item_id) for item_id in sorted(persona_item_ids_to_hide, key=str)[:50]],
                "policy": "hide_not_delete_persona_items",
            }
        )

    uncertain_deleted = delete_uncertain_items_by_ids(uncertain_item_ids_to_delete)
    questions_deleted = delete_question_targets_by_ids(question_target_ids_to_delete)
    chat_deleted = delete_chat_records_by_ids(chat_record_ids_to_delete)
    versions_deleted = delete_skill_versions_by_ids(skill_version_ids_to_delete)
    for profile_id in derived_profile_ids_to_clear:
        uncertain_deleted += delete_uncertain_items(profile_id)
        questions_deleted += delete_question_targets(profile_id)
        chat_deleted += clear_chat_records(profile_id)
        versions_deleted += delete_skill_versions(profile_id)
    repaired_counts["uncertain_items_deleted"] = uncertain_deleted
    repaired_counts["question_targets_deleted"] = questions_deleted
    repaired_counts["chat_records_deleted"] = chat_deleted
    repaired_counts["skill_versions_deleted"] = versions_deleted
    for action, count, ids in (
        ("delete_derived_uncertain_items", uncertain_deleted, uncertain_item_ids_to_delete),
        ("delete_derived_question_targets", questions_deleted, question_target_ids_to_delete),
        ("delete_derived_chat_records", chat_deleted, chat_record_ids_to_delete),
        ("delete_derived_skill_versions", versions_deleted, skill_version_ids_to_delete),
    ):
        if count:
            actions.append(
                {
                    "action": action,
                    "count": count,
                    "record_ids": [str(item_id) for item_id in sorted(ids, key=str)[:50]],
                    "policy": "derived_records_can_be_removed_after_source_or_profile_loss",
                }
            )
    after = build_data_integrity_report()
    diff = _summary_diff(before, after)

    return DataIntegrityRepairResponse(
        report_before=before,
        report_after=after,
        repaired_counts=repaired_counts,
        diff=diff,
        actions=actions,
    )
