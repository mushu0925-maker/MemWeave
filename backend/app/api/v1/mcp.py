from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.schemas.mcp import McpJsonRpcRequest
from app.services.mcp_service import McpToolError, call_mcp_tool, list_mcp_tools, mcp_initialize

router = APIRouter(prefix="/mcp", tags=["mcp"])


def _success(request_id: str | int | None, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: str | int | None, code: int, message: str, data: Any | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
    if data is not None:
        payload["error"]["data"] = data
    return payload


@router.post("")
def handle_mcp_request(payload: McpJsonRpcRequest) -> dict[str, Any]:
    if payload.jsonrpc != "2.0":
        return _error(payload.id, -32600, "Invalid JSON-RPC version")

    if payload.method == "initialize":
        return _success(payload.id, mcp_initialize())
    if payload.method == "tools/list":
        return _success(payload.id, list_mcp_tools())
    if payload.method == "tools/call":
        params = payload.params or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str) or not name:
            return _error(payload.id, -32602, "tools/call requires string params.name")
        if not isinstance(arguments, dict):
            return _error(payload.id, -32602, "tools/call params.arguments must be an object")
        try:
            return _success(payload.id, call_mcp_tool(name, arguments))
        except McpToolError as exc:
            return _error(payload.id, -32602, str(exc))
        except Exception as exc:
            return _error(payload.id, -32000, "MCP tool execution failed", {"error": str(exc)})

    return _error(payload.id, -32601, f"Unknown MCP method: {payload.method}")
