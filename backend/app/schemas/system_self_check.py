from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


SystemCheckStatus = Literal["pass", "warning", "fail", "blocked"]


class SystemSelfCheckItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=160)
    status: SystemCheckStatus
    summary: str = Field(default="", max_length=1000)
    detail: str = Field(default="", max_length=1500)
    action: str = Field(default="", max_length=1000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SystemSelfCheckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    app_name: str
    environment: str
    api_prefix: str
    overall_status: SystemCheckStatus
    checks: list[SystemSelfCheckItem] = Field(default_factory=list)
    required_routes: dict[str, bool] = Field(default_factory=dict)
    summary: dict[str, int] = Field(default_factory=dict)
