from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class McpJsonRpcRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    jsonrpc: str = "2.0"
    id: str | int | None = None
    method: str = Field(min_length=1, max_length=120)
    params: dict[str, Any] | None = None
