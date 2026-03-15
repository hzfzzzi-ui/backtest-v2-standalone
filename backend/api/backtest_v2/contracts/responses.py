from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HistoryListItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    exp_id: str
    label: str
    created_at: str | None = None
    has_manifest: bool = False
    has_core_artifacts: bool = False
    perf: dict[str, Any] = Field(default_factory=dict)


class MobileExperimentSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    exp_id: str
    title: str
    subtitle: str = ""
    tags: list[str] = Field(default_factory=list)
    status: str | None = None
    cagr: float | None = None
    sharpe: float | None = None
    max_drawdown: float | None = None
    total_return: float | None = None
    trades: int | None = None
    signal_date: str | None = None
