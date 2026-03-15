from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExperimentManifest(BaseModel):
    model_config = ConfigDict(extra="allow")

    exp_id: str = Field(min_length=1)
    experiment_id: str | None = None
    status: str | None = None
    schema_version: str | None = None
    baseline_compare_status: str | None = None
    artifacts: dict[str, str] = Field(default_factory=dict)
    config_snapshots: dict[str, str] = Field(default_factory=dict)
    core_artifacts: dict[str, str] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    stage_pipeline: dict[str, Any] | None = None
    stage_summary: dict[str, Any] | None = None
    compare_refs: dict[str, Any] = Field(default_factory=dict)
    machine_outputs: dict[str, str] = Field(default_factory=dict)
    human_outputs: dict[str, str] = Field(default_factory=dict)
