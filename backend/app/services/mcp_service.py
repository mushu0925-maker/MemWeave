from __future__ import annotations

from typing import Any
from uuid import UUID

from app.services.data_integrity_service import build_data_integrity_report
from app.services.monitoring_store import record_monitoring_event
from app.services.profile_store import list_profiles
from app.services.raw_source_store import list_raw_sources
from app.services.runtime_persona_items import list_runtime_persona_items
from app.services.skill_version_store import list_skill_versions

MCP_PROTOCOL_VERSION = "2025-06-18"


class McpToolError(ValueError):
    pass


MCP_TOOLS: list[dict[str, Any]] = [
    {
        "name": "profiles.list",
        "title": "List active profiles",
        "description": "List active memory profiles with basic non-sensitive metadata.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "raw_sources.summaries",
        "title": "List raw source summaries",
        "description": "Return raw source summaries for one profile without full source text.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "profile_id": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "required": ["profile_id"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "persona_items.runtime_safe",
        "title": "List runtime-safe persona items",
        "description": "Return only persona items that pass runtime policy and live evidence-chain checks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "profile_id": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            "required": ["profile_id"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "skill_versions.list",
        "title": "List saved Skill versions",
        "description": "List saved runtime Skill artifact versions for one profile.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "profile_id": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "required": ["profile_id"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "integrity.report",
        "title": "Read data integrity report",
        "description": "Return the current non-mutating data integrity report.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
]


def mcp_initialize() -> dict[str, Any]:
    return {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "serverInfo": {"name": "memweave", "version": "0.1.0"},
        "capabilities": {"tools": {}},
    }


def list_mcp_tools() -> dict[str, Any]:
    return {"tools": MCP_TOOLS}


def _uuid_arg(arguments: dict[str, Any], key: str) -> UUID:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise McpToolError(f"Missing required string argument: {key}")
    try:
        return UUID(value)
    except ValueError as exc:
        raise McpToolError(f"Invalid UUID argument: {key}") from exc


def _limit_arg(arguments: dict[str, Any], default: int, maximum: int) -> int:
    raw_value = arguments.get("limit", default)
    if not isinstance(raw_value, int):
        raise McpToolError("Argument limit must be an integer")
    return max(1, min(maximum, raw_value))


def _text_result(summary: str, structured: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": summary}],
        "structuredContent": structured,
    }


def _raw_excerpt(text: str, max_chars: int = 240) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "..."


def _masked_raw_source_excerpt(source: Any, max_chars: int = 240) -> tuple[str, str]:
    masked_text = str(getattr(source, "pii_masked_text", "") or "").strip()
    if masked_text:
        return _raw_excerpt(masked_text, max_chars=max_chars), "pii_masked_text"
    metadata = getattr(source, "metadata", {}) or {}
    fallback_parts = [
        f"{getattr(source, 'source_type', 'raw_source')} source",
        f"file={getattr(source, 'file_name', None) or metadata.get('stored_file_name') or 'none'}",
        f"mime={getattr(source, 'mime_type', None) or metadata.get('content_type') or 'unknown'}",
        f"extraction_status={metadata.get('extraction_status') or 'unknown'}",
    ]
    return _raw_excerpt("; ".join(fallback_parts), max_chars=max_chars), "metadata_only"


def call_mcp_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    args = arguments or {}
    profile_id: UUID | None = None
    try:
        if name == "profiles.list":
            profiles = list_profiles()
            structured = {
                "profiles": [
                    {
                        "id": str(profile.id),
                        "display_name": profile.display_name,
                        "relationship": profile.relationship,
                        "description": profile.description,
                        "boundary_count": len(profile.boundaries),
                        "updated_at": profile.updated_at.isoformat(),
                    }
                    for profile in profiles
                ]
            }
            result = _text_result(f"Returned {len(profiles)} active profiles.", structured)
        elif name == "raw_sources.summaries":
            profile_id = _uuid_arg(args, "profile_id")
            limit = _limit_arg(args, default=20, maximum=100)
            sources = list_raw_sources(profile_id)[:limit]
            structured = {
                "profile_id": str(profile_id),
                "raw_sources": [
                    {
                        "id": str(source.id),
                        "source_type": source.source_type,
                        "file_name": source.file_name,
                        "mime_type": source.mime_type,
                        "content_hash": source.content_hash,
                        "text_excerpt": _masked_raw_source_excerpt(source)[0],
                        "text_excerpt_source": _masked_raw_source_excerpt(source)[1],
                        "metadata_keys": sorted(source.metadata.keys()),
                        "created_at": source.created_at.isoformat(),
                    }
                    for source in sources
                ],
            }
            result = _text_result(f"Returned {len(sources)} raw source summaries.", structured)
        elif name == "persona_items.runtime_safe":
            profile_id = _uuid_arg(args, "profile_id")
            limit = _limit_arg(args, default=50, maximum=200)
            items = list_runtime_persona_items(profile_id)[:limit]
            structured = {
                "profile_id": str(profile_id),
                "persona_items": [
                    {
                        "id": str(item.id),
                        "source_id": str(item.source_id) if item.source_id else None,
                        "library_group": item.library_group,
                        "library_key": item.library_key,
                        "signal": item.signal,
                        "evidence_quote": item.evidence_quote,
                        "confidence": item.confidence,
                        "stability": item.stability,
                        "subject_scope": item.subject_scope,
                        "write_target": item.write_target,
                        "risk": item.risk,
                        "status": item.status,
                        "created_at": item.created_at.isoformat(),
                    }
                    for item in items
                ],
            }
            result = _text_result(f"Returned {len(items)} runtime-safe persona items.", structured)
        elif name == "skill_versions.list":
            profile_id = _uuid_arg(args, "profile_id")
            limit = _limit_arg(args, default=20, maximum=50)
            versions = list_skill_versions(profile_id, limit=limit)
            structured = {
                "profile_id": str(profile_id),
                "skill_versions": [
                    {
                        "id": str(version.id),
                        "title": version.title,
                        "notes": version.notes,
                        "source_generation_version": version.source_generation_version,
                        "evidence_unit_count": version.evidence_unit_count,
                        "audit_count": version.audit_count,
                        "question_backlog_count": version.question_backlog_count,
                        "created_at": version.created_at.isoformat(),
                    }
                    for version in versions
                ],
            }
            result = _text_result(f"Returned {len(versions)} saved Skill versions.", structured)
        elif name == "integrity.report":
            report = build_data_integrity_report()
            structured = report.model_dump(mode="json")
            result = _text_result(
                f"Integrity report has {report.summary.get('total', 0)} issues.",
                {"report": structured},
            )
        else:
            raise McpToolError(f"Unknown MCP tool: {name}")
    except Exception as exc:
        record_monitoring_event(
            event_type="mcp_tool_call",
            status="failed",
            profile_id=profile_id,
            subject_id=name,
            workflow="mcp.tools.call",
            provider="mcp",
            error=str(exc),
            metadata={"arguments": args},
        )
        raise

    record_monitoring_event(
        event_type="mcp_tool_call",
        status="success",
        profile_id=profile_id,
        subject_id=name,
        workflow="mcp.tools.call",
        provider="mcp",
        output_summary=result["content"][0]["text"],
        metadata={"arguments": args},
    )
    return result
