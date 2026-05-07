from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _StrictPublicModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PublicExperimentRunRequest(_StrictPublicModel):
    preset: str = "G1-G4"
    asset_scope: str | None = None
    config_json: dict[str, Any] | None = None
    baseline_id: str | None = None
    execution_contract_ref: dict[str, Any] | None = None
    fast_mode: bool | None = None


class ExecutionPreviewRequest(_StrictPublicModel):
    config_json: dict[str, Any]
    exp_id: str
    asset_scope: str | None = None
    as_of_date: str | None = None
    top_n: int = 10


__all__ = ["ExecutionPreviewRequest", "PublicExperimentRunRequest"]
