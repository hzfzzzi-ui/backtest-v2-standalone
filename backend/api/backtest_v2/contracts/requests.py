from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _StrictPublicModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PublicExperimentRunRequest(_StrictPublicModel):
    preset: str = "G1-G4"
    config_json: dict[str, Any] | None = None
    fast_mode: bool | None = None


class ExecutionPreviewRequest(_StrictPublicModel):
    config_json: dict[str, Any]
    exp_id: str
    as_of_date: str | None = None
    top_n: int = 10


class ArtifactReadRequest(_StrictPublicModel):
    exp_id: str = Field(min_length=1)
    rel_path: str = Field(min_length=1)


__all__ = ["ArtifactReadRequest", "ExecutionPreviewRequest", "PublicExperimentRunRequest"]
