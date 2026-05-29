from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class BacktestV2ExperimentRequest(BaseModel):
    preset: str = "G1-G4"
    asset_scope: str | None = None
    config_json: dict[str, Any] | None = None
    signal_generation: dict[str, Any] | None = None
    signal_composition: dict[str, Any] | None = None
    symbols: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None
    benchmark: str | None = None
    compare_symbol: str | None = None
    initial_capital: float | None = None
    max_positions: int | None = None
    base_order_value: float | None = None
    univote_lot_mode: str | None = None
    lot_size: int | None = None
    universe_limit: int | None = None
    fast_mode: bool | None = None
    config_path: str | None = None
    config_id: str | None = None
    runtime_config_json: dict[str, Any] | None = None
    workbench_mode: str | None = None
    workbench_config: dict[str, Any] | None = None
    universe_mode: str | None = None
    industries: list[str] | None = None
    price_adj: str | None = None
    enable_strength_rank: bool | None = None
    strength_ma: int | None = None
    strength_top_k_mode: str | None = None
    enable_multifactor_rank: bool | None = None
    mf_topk: int | None = None
    mf_concentrate_topn: int | None = None
    mf_concentrate_scale: float | None = None
    mf_rank_gate_mode: str | None = None
    momentum_top_pct: float | None = None
    baseline_id: str | None = None
    execution_contract_ref: dict[str, Any] | None = None


__all__ = ["BacktestV2ExperimentRequest"]
