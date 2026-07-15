from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.schemas.distillation_plugin import (
    DistillationPluginDefinition,
    DistillationPluginPolicy,
    DistillationPluginPolicyUpdate,
    DistillationPluginRegistryResponse,
    DistillationPluginTendency,
    DistillationPluginWriteRules,
)
from app.services.local_database import read_json_file, update_json_file

DISTILLATION_PLUGIN_STORE_FILE = "distillation_plugin_policy.json"
DEFAULT_DISTILLATION_PLUGIN_KEY = "persona_input_dissection_v1"


def _now() -> datetime:
    return datetime.now(UTC)


DEFAULT_DISTILLATION_PLUGINS: dict[str, DistillationPluginDefinition] = {
    DEFAULT_DISTILLATION_PLUGIN_KEY: DistillationPluginDefinition(
        plugin_key=DEFAULT_DISTILLATION_PLUGIN_KEY,
        name="输入资料解剖 Skill V1",
        version="v1",
        description="把 raw_source 中的个人材料拆解为 A-M persona libraries 的当前默认 AI 蒸馏插件。",
        algorithm_key="persona_input_dissection_v1",
        supported_library_plugin_keys=["am_persona_v1"],
        default_tendency=DistillationPluginTendency(
            conservative_mode=True,
            target_profile_only=True,
            max_candidate_libraries=28,
            confidence_cap_single_source=0.68,
            focus_weights={
                "fact_memory": 1.0,
                "language_style": 1.0,
                "boundary_confidence": 1.15,
                "relationship_modes": 1.05,
            },
        ),
        default_write_rules=DistillationPluginWriteRules(
            persona_item=True,
            uncertain_item=True,
            question_target=True,
            monitoring_event=True,
        ),
    )
}


DEFAULT_DISTILLATION_POLICY = DistillationPluginPolicy(
    selected_plugin_key=DEFAULT_DISTILLATION_PLUGIN_KEY,
    enabled=True,
    strictness="strict",
    tendency=DEFAULT_DISTILLATION_PLUGINS[DEFAULT_DISTILLATION_PLUGIN_KEY].default_tendency,
    write_rules=DEFAULT_DISTILLATION_PLUGINS[DEFAULT_DISTILLATION_PLUGIN_KEY].default_write_rules,
    metadata={"source_of_truth": "raw_sources_plus_persona_libraries"},
    updated_at=_now(),
)


def _read_record() -> dict[str, Any]:
    record = read_json_file(DISTILLATION_PLUGIN_STORE_FILE, DEFAULT_DISTILLATION_POLICY.model_dump(mode="json"))
    if isinstance(record, dict):
        return record
    return DEFAULT_DISTILLATION_POLICY.model_dump(mode="json")


def _write_policy(policy: DistillationPluginPolicy) -> None:
    update_json_file(DISTILLATION_PLUGIN_STORE_FILE, {}, lambda _record: policy.model_dump(mode="json"))


def _policy_from_record(record: dict[str, Any]) -> DistillationPluginPolicy:
    return DistillationPluginPolicy.model_validate(record)


def list_distillation_plugins() -> DistillationPluginRegistryResponse:
    return DistillationPluginRegistryResponse(
        available_plugins=sorted(DEFAULT_DISTILLATION_PLUGINS.values(), key=lambda item: item.plugin_key),
        current=get_current_distillation_policy(),
    )


def get_current_distillation_policy() -> DistillationPluginPolicy:
    return _policy_from_record(_read_record())


def update_current_distillation_policy(payload: DistillationPluginPolicyUpdate) -> DistillationPluginPolicy:
    current = get_current_distillation_policy()
    selected_plugin_key = payload.selected_plugin_key or current.selected_plugin_key
    selected_definition = DEFAULT_DISTILLATION_PLUGINS.get(selected_plugin_key)
    plugin_changed = payload.selected_plugin_key is not None and payload.selected_plugin_key != current.selected_plugin_key
    if plugin_changed and selected_definition is not None:
        default_tendency = selected_definition.default_tendency
        default_write_rules = selected_definition.default_write_rules
    else:
        default_tendency = current.tendency
        default_write_rules = current.write_rules
    updated = current.model_copy(
        update={
            "selected_plugin_key": selected_plugin_key,
            "enabled": payload.enabled if payload.enabled is not None else current.enabled,
            "strictness": payload.strictness if payload.strictness is not None else current.strictness,
            "tendency": payload.tendency if payload.tendency is not None else default_tendency,
            "write_rules": payload.write_rules if payload.write_rules is not None else default_write_rules,
            "metadata": payload.metadata if payload.metadata is not None else current.metadata,
            "updated_by": (payload.updated_by or "backend-admin").strip() or "backend-admin",
            "updated_at": _now(),
        }
    )
    _write_policy(updated)
    return updated


def reset_current_distillation_policy() -> DistillationPluginPolicy:
    policy = DEFAULT_DISTILLATION_POLICY.model_copy(update={"updated_at": _now(), "updated_by": "system-reset"})
    _write_policy(policy)
    return policy


def get_distillation_plugin_definition(plugin_key: str) -> DistillationPluginDefinition | None:
    return DEFAULT_DISTILLATION_PLUGINS.get(plugin_key)


def validate_current_distillation_policy() -> tuple[bool, str]:
    policy = get_current_distillation_policy()
    if not policy.enabled:
        return False, "distillation_plugin_disabled"
    if policy.selected_plugin_key not in DEFAULT_DISTILLATION_PLUGINS:
        return False, f"unsupported_distillation_plugin_key:{policy.selected_plugin_key}"
    return True, "ok"


def distillation_plugin_snapshot() -> dict[str, Any]:
    policy = get_current_distillation_policy()
    definition = get_distillation_plugin_definition(policy.selected_plugin_key)
    return {
        "distillation_plugin_key": policy.selected_plugin_key,
        "distillation_plugin_version": definition.version if definition else None,
        "distillation_algorithm_key": definition.algorithm_key if definition else None,
        "distillation_enabled": policy.enabled,
        "distillation_strictness": policy.strictness,
        "distillation_tendency": policy.tendency.model_dump(mode="json"),
        "distillation_write_rules": policy.write_rules.model_dump(mode="json"),
    }


def can_distillation_write(layer: str) -> bool:
    policy = get_current_distillation_policy()
    if not policy.enabled or not hasattr(policy.write_rules, layer):
        return False
    return bool(getattr(policy.write_rules, layer))
