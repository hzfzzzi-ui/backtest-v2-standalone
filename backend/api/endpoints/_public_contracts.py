from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _StrictPublicModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PublicBacktestV2ExperimentRequest(_StrictPublicModel):
    preset: str = "G1-G4"
    config_json: dict[str, Any] | None = None
    fast_mode: bool | None = None


class PublicBacktestV2ExecutionPreviewRequest(_StrictPublicModel):
    config_json: dict[str, Any]
    exp_id: str
    as_of_date: str | None = None
    top_n: int = 10


class PublicBacktestV2ArtifactReadRequest(_StrictPublicModel):
    exp_id: str = Field(min_length=1)
    rel_path: str = Field(min_length=1)


def _dump_model(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return dict(payload)
    if hasattr(payload, "model_dump"):
        return dict(payload.model_dump(exclude_none=True))
    if hasattr(payload, "dict"):
        return dict(payload.dict(exclude_none=True))
    return {}


def to_internal_experiment_request(payload: Any):
    from ._experiment_runner_api import BacktestV2ExperimentRequest

    if isinstance(payload, BacktestV2ExperimentRequest):
        return payload
    return BacktestV2ExperimentRequest(**_dump_model(payload))
