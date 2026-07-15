from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.local_database import read_json_file, update_json_file

RUNTIME_MODULE_SETTINGS_FILE = "runtime_module_settings.json"


@dataclass(frozen=True)
class RuntimeModuleSettings:
    boundary_guard: dict[str, Any] = field(default_factory=dict)
    expression_guard: dict[str, Any] = field(default_factory=dict)
    closure_guard: dict[str, Any] = field(default_factory=dict)
    attribution_guard: dict[str, Any] = field(default_factory=dict)
    evidence_extension: dict[str, Any] = field(default_factory=dict)


DEFAULT_RUNTIME_MODULE_SETTINGS = RuntimeModuleSettings(
    boundary_guard={
        "enabled": True,
        "strictness": "strict",
        "block_continue_question_overreach": True,
        "rewrite_ambiguous_leave_signal": True,
        "rewrite_hard_stop_reply": True,
    },
    expression_guard={
        "enabled": True,
        "strictness": "strict",
        "rewrite_unsupported_generic_soothing": True,
    },
    closure_guard={
        "enabled": True,
        "strictness": "strict",
        "trim_templates": True,
    },
    attribution_guard={
        "enabled": True,
        "strictness": "strict",
        "rewrite_user_template_as_target_style": True,
    },
    evidence_extension={
        "enabled": True,
        "strictness": "strict",
        "max_extensions": 2,
        "max_chars": 260,
    },
)


def _settings_to_record(settings: RuntimeModuleSettings) -> dict[str, Any]:
    return {
        "boundary_guard": dict(settings.boundary_guard),
        "expression_guard": dict(settings.expression_guard),
        "closure_guard": dict(settings.closure_guard),
        "attribution_guard": dict(settings.attribution_guard),
        "evidence_extension": dict(settings.evidence_extension),
    }


def _coerce_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    return fallback


def _coerce_strictness(value: Any, fallback: str = "strict") -> str:
    if value in {"relaxed", "normal", "strict", "audit_only"}:
        return str(value)
    return fallback


def _coerce_int(value: Any, fallback: int, *, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, number))


def _merge_module(default: dict[str, Any], record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        record = {}
    merged = {**default, **record}
    cleaned: dict[str, Any] = {}
    for key, default_value in default.items():
        value = merged.get(key, default_value)
        if isinstance(default_value, bool):
            cleaned[key] = _coerce_bool(value, default_value)
        elif key == "strictness":
            cleaned[key] = _coerce_strictness(value, str(default_value))
        elif isinstance(default_value, int):
            maximum = 2000 if key == "max_chars" else 20
            cleaned[key] = _coerce_int(value, default_value, minimum=0, maximum=maximum)
        else:
            cleaned[key] = value
    return cleaned


def _settings_from_record(record: dict[str, Any]) -> RuntimeModuleSettings:
    defaults = _settings_to_record(DEFAULT_RUNTIME_MODULE_SETTINGS)
    return RuntimeModuleSettings(
        boundary_guard=_merge_module(defaults["boundary_guard"], record.get("boundary_guard")),
        expression_guard=_merge_module(defaults["expression_guard"], record.get("expression_guard")),
        closure_guard=_merge_module(defaults["closure_guard"], record.get("closure_guard")),
        attribution_guard=_merge_module(defaults["attribution_guard"], record.get("attribution_guard")),
        evidence_extension=_merge_module(defaults["evidence_extension"], record.get("evidence_extension")),
    )


def get_runtime_module_settings() -> RuntimeModuleSettings:
    record = read_json_file(RUNTIME_MODULE_SETTINGS_FILE, {})
    if not isinstance(record, dict):
        return DEFAULT_RUNTIME_MODULE_SETTINGS
    if not record:
        update_json_file(RUNTIME_MODULE_SETTINGS_FILE, {}, lambda _record: _settings_to_record(DEFAULT_RUNTIME_MODULE_SETTINGS))
        return DEFAULT_RUNTIME_MODULE_SETTINGS
    return _settings_from_record(record)


def update_runtime_module_settings(payload: dict[str, Any]) -> RuntimeModuleSettings:
    current = _settings_to_record(get_runtime_module_settings())
    allowed_modules = set(current)
    updates = {
        key: value
        for key, value in payload.items()
        if key in allowed_modules and isinstance(value, dict)
    }
    updated = _settings_from_record({**current, **updates})
    update_json_file(RUNTIME_MODULE_SETTINGS_FILE, {}, lambda _record: _settings_to_record(updated))
    return updated


def reset_runtime_module_settings() -> RuntimeModuleSettings:
    update_json_file(RUNTIME_MODULE_SETTINGS_FILE, {}, lambda _record: _settings_to_record(DEFAULT_RUNTIME_MODULE_SETTINGS))
    return DEFAULT_RUNTIME_MODULE_SETTINGS


def runtime_module_settings_record() -> dict[str, Any]:
    return _settings_to_record(get_runtime_module_settings())
