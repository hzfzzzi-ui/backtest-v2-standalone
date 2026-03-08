from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

from ._utils import _hash_json, sanitize_json


SEMANTIC_CONFIG_SCHEMA_VERSION = "2026-03-08"


class StrictModel(BaseModel):
    class Config:
        extra = "forbid"


class UniverseFiltersConfig(StrictModel):
    exclude_st: bool | None = None
    exclude_delisted: bool | None = None
    exclude_suspended: bool | None = None
    min_list_days: int | None = None
    min_avg_turnover_20d: float | None = None
    price_min: float | None = None
    price_max: float | None = None
    atr_pct_range: str | None = None
    limit_rule: str | None = None


class UniverseConfig(StrictModel):
    start: str | None = None
    end: str | None = None
    benchmark: str | None = None
    symbols: list[str] | None = None
    limit: int | None = None
    price_adj: str | None = None
    filters: UniverseFiltersConfig | None = None


class RegimeFilterConfig(StrictModel):
    enabled: bool | None = None
    regime_threshold: float | None = None
    alpha_m: float | None = None
    alpha_sec: float | None = None
    alpha_i: float | None = None


class RegimeDetectionConfig(StrictModel):
    enabled: bool | None = None
    regime_ma: int | None = None
    regime_filter: RegimeFilterConfig | None = None


class TrendSignalConfig(StrictModel):
    strategy: str | None = None
    fast_ma: int | None = None
    slow_ma: int | None = None
    entry_buffer_pct: float | None = None


class MeanReversionConfig(StrictModel):
    strategy: str | None = None
    rsi_period: int | None = None
    rsi_buy_threshold: float | None = None
    rsi_sell_threshold: float | None = None
    mr_max_hold_days: int | None = None
    mr_stop_loss_pct: float | None = None


class MaSignalConfig(StrictModel):
    fast_ma: int | None = None
    slow_ma: int | None = None
    entry_buffer_pct: float | None = None


class BreakoutSignalConfig(StrictModel):
    breakout_window: int | None = None
    enable_dual_breakout: bool | None = None
    breakout_window_short: int | None = None
    breakout_window_long: int | None = None
    breakout_entry_buffer_pct: float | None = None
    entry_confirm_mode: str | None = None
    entry_delay_mode: str | None = None


class EntryFilterConfig(StrictModel):
    enable_entry_above_slow_ma: bool | None = None
    enable_entry_slow_ma_slope: bool | None = None
    entry_slope_lookback: int | None = None


class RankingConfig(StrictModel):
    momentum_top_pct: float | None = None


class SignalGenerationConfig(StrictModel):
    enabled: bool | None = None
    strategy: str | None = None
    regime_detection: RegimeDetectionConfig | None = None
    trend: TrendSignalConfig | None = None
    mr: MeanReversionConfig | None = None
    sma: MaSignalConfig | None = None
    ema: MaSignalConfig | None = None
    breakout: BreakoutSignalConfig | None = None
    entry_filter: EntryFilterConfig | None = None
    ranking: RankingConfig | None = None


class BenchmarkRegimeConfig(StrictModel):
    enabled: bool | None = None
    fast_period: int | None = None
    slow_period: int | None = None
    slope_window: int | None = None


class StockTrendFilterConfig(StrictModel):
    enabled: bool | None = None
    short_ma: int | None = None
    long_ma: int | None = None


class SectorGateConfig(StrictModel):
    enabled: bool | None = None
    rank_window: int | None = None
    top_pct: float | None = None


class SignalCompositionModuleConfig(StrictModel):
    name: str
    enabled: bool | None = None
    role: str | None = None
    weight: float | None = None
    priority: int | None = None


class SignalCompositionConfig(StrictModel):
    enabled: bool | None = None
    compose_mode: str | None = None
    modules: list[SignalCompositionModuleConfig] | None = None
    score_threshold: float | None = None


class AtrStopConfig(StrictModel):
    enabled: bool | None = None
    k: float | None = None


class TrailingExitConfig(StrictModel):
    enabled: bool | None = None
    k: float | None = None


class TimeExitConfig(StrictModel):
    enabled: bool | None = None
    n_days: int | None = None


class HoldConstraintConfig(StrictModel):
    min_hold_days: int | None = None
    cooldown_days: int | None = None


class TakeProfitConfig(StrictModel):
    enabled: bool | None = None
    mode: str | None = None
    pct: float | None = None
    atr_k: float | None = None


class FixedStopConfig(StrictModel):
    enabled: bool | None = None
    pct: float | None = None


class ToggleConfig(StrictModel):
    enabled: bool | None = None


class ExitRulesConfig(StrictModel):
    enabled: bool | None = None
    signal_reverse: bool | None = None
    atr_stop: AtrStopConfig | None = None
    trailing: TrailingExitConfig | None = None
    time_exit: TimeExitConfig | None = None
    hold_constraint: HoldConstraintConfig | None = None
    take_profit: TakeProfitConfig | None = None
    fixed_stop: FixedStopConfig | None = None
    ma20_exit: ToggleConfig | None = None
    low10_exit: ToggleConfig | None = None


class UniverseFilterConfig(StrictModel):
    min_price: float | None = None


class RiskBudgetConfig(StrictModel):
    enabled: bool | None = None
    dd_reduce_pct: float | None = None
    dd_reduce_scale: float | None = None
    atr_stop_k: float | None = None
    base_portfolio_risk: float | None = None
    min_active_ratio: float | None = None
    dd_scale_10: float | None = None
    dd_scale_15: float | None = None
    dd_fixed_20: float | None = None
    dd_stop_pct: float | None = None
    dd_stop_cooldown_days: int | None = None
    dd_stop_protect_days: int | None = None


class MarketFilterConfig(StrictModel):
    enabled: bool | None = None
    slope_ma_period: int | None = None
    slope_window: int | None = None
    bull_multiplier: float | None = None
    light_multiplier: float | None = None
    ema_light_fast: int | None = None
    ema_light_slow: int | None = None


class CostModelConfig(StrictModel):
    commission: str | None = None
    stamp_tax: str | None = None
    slippage: str | None = None
    matching: str | None = None


class PositionRiskConfig(StrictModel):
    enabled: bool | None = None
    max_positions: int | None = None
    single_stock_cap: float | None = None
    industry_cap: float | None = None
    lot: int | None = None
    cash_shortage_policy: str | None = None
    portfolio_mode: str | None = None
    risk_budget: RiskBudgetConfig | None = None
    market_filter: MarketFilterConfig | None = None
    cost_model: CostModelConfig | None = None


class FlowScriptConfig(StrictModel):
    script_id: str | None = None
    description: str | None = None
    recommended_preset: str | None = None


class FrontendSemanticConfig(StrictModel):
    mode: str | None = None
    initial_capital: float | None = None
    strategy_pack: str | None = None
    universe_mode: str | None = None
    industries: list[str] | None = None
    universe: UniverseConfig | None = None
    signal_generation: SignalGenerationConfig | None = None
    benchmark_regime: BenchmarkRegimeConfig | None = None
    stock_trend_filter: StockTrendFilterConfig | None = None
    sector_gate: SectorGateConfig | None = None
    signal_composition: SignalCompositionConfig | None = None
    exit_rules: ExitRulesConfig | None = None
    universe_filter: UniverseFilterConfig | None = None
    position_risk: PositionRiskConfig | None = None
    flow_script: FlowScriptConfig | None = None
    exit_priority: list[str] | None = None


def _build_error(path: str, message: str) -> dict[str, str]:
    return {"path": path, "message": message}


def _normalized_strategy(raw: dict[str, Any]) -> str:
    signal_generation = raw.get("signal_generation") if isinstance(raw.get("signal_generation"), dict) else {}
    candidates = [
        signal_generation.get("strategy"),
        raw.get("strategy_pack"),
    ]
    for value in candidates:
        text = str(value or "").strip().upper()
        if text:
            return text
    return ""


def _validate_semantic_logic(raw: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    signal_generation = raw.get("signal_generation") if isinstance(raw.get("signal_generation"), dict) else {}
    strategy = _normalized_strategy(raw)

    if strategy and not signal_generation:
        errors.append(_build_error("signal_generation", "required when strategy_pack or signal_generation.strategy is set"))
        return errors

    if strategy == "BREAKOUT_TREND" and not isinstance(signal_generation.get("breakout"), dict):
        errors.append(_build_error("signal_generation.breakout", "required for BREAKOUT_TREND"))
    if strategy == "SMA_CROSS" and not isinstance(signal_generation.get("sma"), dict):
        errors.append(_build_error("signal_generation.sma", "required for SMA_CROSS"))
    if strategy == "EMA_CROSS" and not isinstance(signal_generation.get("ema"), dict):
        errors.append(_build_error("signal_generation.ema", "required for EMA_CROSS"))
    if strategy == "REGIME_ROUTER":
        if not isinstance(signal_generation.get("regime_detection"), dict):
            errors.append(_build_error("signal_generation.regime_detection", "required for REGIME_ROUTER"))
        if not isinstance(signal_generation.get("trend"), dict):
            errors.append(_build_error("signal_generation.trend", "required for REGIME_ROUTER"))
        if not isinstance(signal_generation.get("mr"), dict):
            errors.append(_build_error("signal_generation.mr", "required for REGIME_ROUTER"))

    return errors


def validate_semantic_config_json(raw: dict[str, Any]) -> dict[str, Any]:
    try:
        model = FrontendSemanticConfig.parse_obj(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=f"invalid config_json: {exc}") from exc
    normalized = jsonable_dict(model)
    logic_errors = _validate_semantic_logic(normalized)
    if logic_errors:
        raise HTTPException(status_code=400, detail={"message": "invalid config_json", "errors": logic_errors})
    return normalized


def compile_semantic_config_json(
    raw: dict[str, Any],
    *,
    compiled_plan_payload: dict[str, Any] | None = None,
    config_source: str = "config_json",
) -> dict[str, Any]:
    input_config = sanitize_json(dict(raw or {}))
    resolved_input = validate_semantic_config_json(input_config)
    config_hash = _hash_json(input_config)
    provenance = {
        "schema_version": SEMANTIC_CONFIG_SCHEMA_VERSION,
        "config_source": str(config_source or "config_json"),
        "config_hash": config_hash,
    }
    return {
        "input_config": sanitize_json(dict(input_config)),
        "resolved_config": sanitize_json(
            {
                **provenance,
                "config_json": dict(resolved_input),
            }
        ),
        "compiled_plan": sanitize_json(
            {
                **provenance,
                **dict(compiled_plan_payload or {}),
            }
        ),
        "config_hash": config_hash,
        "schema_version": SEMANTIC_CONFIG_SCHEMA_VERSION,
        "config_source": str(config_source or "config_json"),
    }


def jsonable_dict(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_none=True)
    return model.dict(exclude_none=True)
