from __future__ import annotations

from backend.api.backtest_v2.contracts.manifest import ExperimentManifest
from backend.api.backtest_v2.contracts.responses import HistoryListItem, MobileExperimentSummary
from backend.api.backtest_v2.contracts.surface import (
    ExecutionPreview,
    ExperimentLazySurfaceSection,
    ExperimentSurface,
    ExperimentSurfaceSummary,
)
from backend.core.contracts import manifest as core_manifest
from backend.core.contracts import responses as core_responses
from backend.core.contracts import surface as core_surface


def test_api_query_contracts_reexport_core_owner() -> None:
    assert ExperimentManifest is core_manifest.ExperimentManifest
    assert HistoryListItem is core_responses.HistoryListItem
    assert MobileExperimentSummary is core_responses.MobileExperimentSummary
    assert ExecutionPreview is core_surface.ExecutionPreview
    assert ExperimentLazySurfaceSection is core_surface.ExperimentLazySurfaceSection
    assert ExperimentSurface is core_surface.ExperimentSurface
    assert ExperimentSurfaceSummary is core_surface.ExperimentSurfaceSummary


def test_api_query_contracts_expose_pydantic_schema() -> None:
    manifest_schema = ExperimentManifest.model_json_schema()
    history_schema = HistoryListItem.model_json_schema()
    mobile_schema = MobileExperimentSummary.model_json_schema()
    surface_schema = ExperimentSurface.model_json_schema()
    execution_preview_schema = ExecutionPreview.model_json_schema()

    assert manifest_schema["title"] == "ExperimentManifest"
    assert "exp_id" in manifest_schema.get("required", [])
    assert history_schema["title"] == "HistoryListItem"
    assert {"exp_id", "label"}.issubset(set(history_schema.get("required", [])))
    assert mobile_schema["title"] == "MobileExperimentSummary"
    assert {"exp_id", "title"}.issubset(set(mobile_schema.get("required", [])))
    assert surface_schema["title"] == "ExperimentSurface"
    assert "summary" in surface_schema.get("required", [])
    assert execution_preview_schema["title"] == "ExecutionPreview"
