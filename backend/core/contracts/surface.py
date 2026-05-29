from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExperimentSurfaceSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    exp_id: str
    label: str
    status: str | None = None
    created_at: str | None = None
    baseline_compare_status: str | None = None
    runtime_route: str | None = None
    execution_shell: str | None = None
    effective_execution_start_date: str | None = None
    asset_scope: str | None = None
    asset_profile_id: str | None = None
    market_profile_id: str | None = None
    execution_profile_id: str | None = None
    asset_context: dict[str, Any] = Field(default_factory=dict)


class ExperimentLazySurfaceSection(BaseModel):
    model_config = ConfigDict(extra="allow")

    section: str
    available: bool = True
    inline: bool = False
    endpoint: str | None = None
    data: Any | None = None


class ExperimentSurface(BaseModel):
    model_config = ConfigDict(extra="allow")

    summary: ExperimentSurfaceSummary
    perf: dict[str, Any] = Field(default_factory=dict)
    audit: dict[str, Any] = Field(default_factory=dict)
    asset_context: dict[str, Any] = Field(default_factory=dict)
    machine_outputs: dict[str, str] = Field(default_factory=dict)
    human_outputs: dict[str, str] = Field(default_factory=dict)
    lazy_sections: dict[str, ExperimentLazySurfaceSection] = Field(default_factory=dict)


class ExecutionPreview(BaseModel):
    model_config = ConfigDict(extra="allow")

    orders: list[dict[str, Any]] = Field(default_factory=list)
    target_weights: list[dict[str, Any]] = Field(default_factory=list)
    cash_usage: dict[str, Any] = Field(default_factory=dict)
    risk_flags: list[dict[str, Any] | str] = Field(default_factory=list)
    freshness: dict[str, Any] = Field(default_factory=dict)
    as_of_date: str | None = None


__all__ = [
    "ExecutionPreview",
    "ExperimentLazySurfaceSection",
    "ExperimentSurface",
    "ExperimentSurfaceSummary",
]
