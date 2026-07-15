from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.schemas.library_plugin import (
    LibraryPluginCatalog,
    LibraryPluginDefinition,
    LibraryPluginPolicy,
    LibraryPluginPolicyUpdate,
    LibraryPluginRegistryResponse,
    PersonaLibraryDefinitionPayload,
)
from app.services.local_database import read_json_file, update_json_file
from app.services.persona_core_libraries import (
    PERSONA_LIBRARY_DEFINITIONS,
    PERSONA_LIBRARY_REGISTRY,
    PersonaLibraryDefinition,
)

LIBRARY_PLUGIN_STORE_FILE = "library_plugin_policy.json"
DEFAULT_LIBRARY_PLUGIN_KEY = "am_persona_v1"
REQUIRED_AM_LIBRARY_KEYS = (
    "fact_direct_quotes",
    "fact_uncertain_claims",
    "relationship_exit_strategy",
    "boundary_fact_invention",
)


def _now() -> datetime:
    return datetime.now(UTC)


def _all_registry_keys() -> list[str]:
    return [definition.key for definition in PERSONA_LIBRARY_REGISTRY]


def _registry_categories(keys: list[str]) -> list[str]:
    categories: list[str] = []
    allowed = set(keys)
    for definition in PERSONA_LIBRARY_REGISTRY:
        if definition.key not in allowed:
            continue
        if definition.category not in categories:
            categories.append(definition.category)
    return categories


DEFAULT_LIBRARY_PLUGINS: dict[str, LibraryPluginDefinition] = {
    DEFAULT_LIBRARY_PLUGIN_KEY: LibraryPluginDefinition(
        plugin_key=DEFAULT_LIBRARY_PLUGIN_KEY,
        name="A-M 人格知识库 V1",
        version="v1",
        description="当前正式 A-M persona libraries。raw_sources 是证据源，persona_items 是结构化解释，Skill 是运行态产物。",
        algorithm_key="am_persona_registry_v1",
        allowed_library_keys=_all_registry_keys(),
        categories=_registry_categories(_all_registry_keys()),
        library_count=len(PERSONA_LIBRARY_REGISTRY),
    )
}


DEFAULT_LIBRARY_POLICY = LibraryPluginPolicy(
    selected_plugin_key=DEFAULT_LIBRARY_PLUGIN_KEY,
    enabled=True,
    strictness="strict",
    allowed_library_keys_override=None,
    min_required_library_keys=list(REQUIRED_AM_LIBRARY_KEYS),
    metadata={"source_of_truth": "raw_sources_plus_persona_libraries"},
    updated_at=_now(),
)


def _read_record() -> dict[str, Any]:
    record = read_json_file(LIBRARY_PLUGIN_STORE_FILE, DEFAULT_LIBRARY_POLICY.model_dump(mode="json"))
    if isinstance(record, dict):
        return record
    return DEFAULT_LIBRARY_POLICY.model_dump(mode="json")


def _write_policy(policy: LibraryPluginPolicy) -> None:
    update_json_file(LIBRARY_PLUGIN_STORE_FILE, {}, lambda _record: policy.model_dump(mode="json"))


def _policy_from_record(record: dict[str, Any]) -> LibraryPluginPolicy:
    return LibraryPluginPolicy.model_validate(record)


def _definition_payload(definition: PersonaLibraryDefinition) -> PersonaLibraryDefinitionPayload:
    return PersonaLibraryDefinitionPayload(
        key=definition.key,
        category=definition.category,
        label=definition.label,
        purpose=definition.purpose,
        extraction_targets=list(definition.extraction_targets),
        retrieval_triggers=list(definition.retrieval_triggers),
        prompt_budget=definition.prompt_budget,
        default_usage=definition.default_usage,
    )


def list_library_plugins() -> LibraryPluginRegistryResponse:
    return LibraryPluginRegistryResponse(
        available_plugins=sorted(DEFAULT_LIBRARY_PLUGINS.values(), key=lambda item: item.plugin_key),
        current=get_current_library_policy(),
    )


def get_current_library_policy() -> LibraryPluginPolicy:
    return _policy_from_record(_read_record())


def update_current_library_policy(payload: LibraryPluginPolicyUpdate) -> LibraryPluginPolicy:
    current = get_current_library_policy()
    updated = current.model_copy(
        update={
            "selected_plugin_key": payload.selected_plugin_key or current.selected_plugin_key,
            "enabled": payload.enabled if payload.enabled is not None else current.enabled,
            "strictness": payload.strictness if payload.strictness is not None else current.strictness,
            "allowed_library_keys_override": (
                payload.allowed_library_keys_override
                if payload.allowed_library_keys_override is not None
                else current.allowed_library_keys_override
            ),
            "min_required_library_keys": (
                payload.min_required_library_keys
                if payload.min_required_library_keys is not None
                else current.min_required_library_keys
            ),
            "metadata": payload.metadata if payload.metadata is not None else current.metadata,
            "updated_by": (payload.updated_by or "backend-admin").strip() or "backend-admin",
            "updated_at": _now(),
        }
    )
    _write_policy(updated)
    return updated


def reset_current_library_policy() -> LibraryPluginPolicy:
    policy = DEFAULT_LIBRARY_POLICY.model_copy(update={"updated_at": _now(), "updated_by": "system-reset"})
    _write_policy(policy)
    return policy


def get_library_plugin_definition(plugin_key: str) -> LibraryPluginDefinition | None:
    return DEFAULT_LIBRARY_PLUGINS.get(plugin_key)


def active_library_keys() -> list[str]:
    policy = get_current_library_policy()
    definition = get_library_plugin_definition(policy.selected_plugin_key)
    if definition is None:
        return []
    configured_keys = policy.allowed_library_keys_override
    if configured_keys is None:
        return list(definition.allowed_library_keys)
    return list(dict.fromkeys(key.strip() for key in configured_keys if key.strip()))


def active_library_definitions() -> list[PersonaLibraryDefinition]:
    keys = active_library_keys()
    return [
        PERSONA_LIBRARY_DEFINITIONS[key]
        for key in keys
        if key in PERSONA_LIBRARY_DEFINITIONS
    ]


def validate_current_library_policy() -> tuple[bool, str]:
    policy = get_current_library_policy()
    if not policy.enabled:
        return False, "library_plugin_disabled"
    if policy.selected_plugin_key not in DEFAULT_LIBRARY_PLUGINS:
        return False, f"unsupported_library_plugin_key:{policy.selected_plugin_key}"
    allowed_keys = active_library_keys()
    if not allowed_keys:
        return False, "library_plugin_has_no_active_keys"
    unknown_keys = sorted(key for key in allowed_keys if key not in PERSONA_LIBRARY_DEFINITIONS)
    if unknown_keys:
        return False, "unsupported_library_key:" + ",".join(unknown_keys[:12])
    missing_required = sorted(key for key in policy.min_required_library_keys if key not in allowed_keys)
    if missing_required:
        return False, "missing_required_library_key:" + ",".join(missing_required[:12])
    return True, "ok"


def current_library_catalog() -> LibraryPluginCatalog:
    policy = get_current_library_policy()
    keys = active_library_keys()
    allowed = set(keys)
    categories: dict[str, list[PersonaLibraryDefinitionPayload]] = {}
    for definition in PERSONA_LIBRARY_REGISTRY:
        if definition.key not in allowed:
            continue
        categories.setdefault(definition.category, []).append(_definition_payload(definition))
    return LibraryPluginCatalog(
        plugin_key=policy.selected_plugin_key,
        enabled=policy.enabled,
        strictness=policy.strictness,
        library_count=sum(len(items) for items in categories.values()),
        categories=categories,
        allowed_library_keys=keys,
        min_required_library_keys=policy.min_required_library_keys,
    )


def library_plugin_snapshot() -> dict[str, Any]:
    policy = get_current_library_policy()
    definition = get_library_plugin_definition(policy.selected_plugin_key)
    keys = active_library_keys()
    return {
        "library_plugin_key": policy.selected_plugin_key,
        "library_plugin_version": definition.version if definition else None,
        "library_algorithm_key": definition.algorithm_key if definition else None,
        "library_enabled": policy.enabled,
        "library_strictness": policy.strictness,
        "library_count": len(keys),
        "library_allowed_keys": keys,
        "library_min_required_keys": policy.min_required_library_keys,
    }
