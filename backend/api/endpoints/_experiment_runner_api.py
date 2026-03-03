from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .backtest_v2_artifacts import stabilize_experiment_result
from ._paths import _bt_root, _results_root
from ._utils import sanitize_json, _sanitize_for_json
from ._job_store import (
    _JOBS,
    _JOBS_LOCK,
    _create_job,
    _update_job,
    _is_cancel_requested,
    _mark_job_canceled,
    _load_job_from_disk,
    _job_payload,
)

router = APIRouter(tags=["backtest_v2"])


class BacktestV2ExperimentRequest(BaseModel):
    preset: str = "G1-G4"
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
    workbench_mode: str | None = None
    workbench_config: dict[str, Any] | None = None
    universe_mode: str = "CUSTOM"
    industries: list[str] = []
    price_adj: str = "hfq"
    # 选股排序参数透传
    enable_strength_rank: bool | None = None
    strength_ma: int | None = None
    strength_top_k_mode: str | None = None
    enable_multifactor_rank: bool | None = None
    mf_topk: int | None = None


def _load_base_config(bt_root: Path) -> dict[str, Any]:
    cfg_path = bt_root / "configs" / "pams_cn_pg.json"
    if not cfg_path.exists():
        raise HTTPException(status_code=500, detail=f"missing config template: {cfg_path}")
    return json.loads(cfg_path.read_text(encoding="utf-8-sig"))


def _to_int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _build_runtime_cfg_from_workbench(
    base_cfg: dict[str, Any],
    body: BacktestV2ExperimentRequest,
    wb_cfg: dict[str, Any],
) -> dict[str, Any]:
    cfg = json.loads(json.dumps(base_cfg))
    universe = cfg.setdefault("universe", {})
    if body.start_date:
        universe["start"] = str(body.start_date)
    if body.end_date:
        universe["end"] = str(body.end_date)
    if body.benchmark:
        universe["benchmark"] = str(body.benchmark)
    if body.symbols:
        universe["symbols"] = list(body.symbols)

    sig = wb_cfg.get("signal_generation") if isinstance(wb_cfg.get("signal_generation"), dict) else {}
    strategy_pack = str(sig.get("strategy") or wb_cfg.get("strategy_pack") or "SMA_CROSS").strip().upper()
    strategy_name_map = {
        "SMA_CROSS": "sma_cross",
        "EMA_CROSS": "ema_cross",
        "ADAPTIVE_REGIME": "adaptive_regime",
        "REGIME_ROUTER": "regime_router",
    }
    strategy_name = strategy_name_map.get(strategy_pack)
    if strategy_name is None:
        return cfg

    # --- REGIME_ROUTER 编译路径 (新结构: regime_detection + trend + mr) ---
    if strategy_name == "regime_router":
        rd = sig.get("regime_detection") if isinstance(sig.get("regime_detection"), dict) else {}
        trend_cfg = sig.get("trend") if isinstance(sig.get("trend"), dict) else {}
        mr_cfg = sig.get("mr") if isinstance(sig.get("mr"), dict) else {}

        trend_name = str(trend_cfg.get("strategy", "SMA_CROSS")).strip().lower()
        trend_name_map = {"sma_cross": "sma_cross", "ema_cross": "ema_cross"}
        resolved_trend = trend_name_map.get(trend_name, "sma_cross")

        order_size = _to_int_or_default(cfg.get("strategy", {}).get("order_size"), 1000)
        strategy = cfg.setdefault("strategy", {})
        strategy["name"] = "regime_router"
        strategy["fast"] = _to_int_or_default(trend_cfg.get("fast_ma"), 5)
        strategy["slow"] = _to_int_or_default(trend_cfg.get("slow_ma"), 20)
        strategy["order_size"] = order_size
        strategy["params"] = {
            "regime_ma": _to_int_or_default(rd.get("regime_ma"), 60),
            "trend_strategy": resolved_trend,
            "trend_params": {
                "fast": strategy["fast"],
                "slow": strategy["slow"],
                "order_size": order_size,
            },
            "mr_strategy": "rsi_reversal",
            "mr_params": {
                "rsi_period": _to_int_or_default(mr_cfg.get("rsi_period"), 6),
                "rsi_buy_threshold": float(mr_cfg.get("rsi_buy_threshold", 20.0)),
                "rsi_sell_threshold": float(mr_cfg.get("rsi_sell_threshold", 80.0)),
                "mr_max_hold_days": _to_int_or_default(mr_cfg.get("mr_max_hold_days"), 5),
                "mr_stop_loss_pct": float(mr_cfg.get("mr_stop_loss_pct", 0.03)),
                "order_size": order_size,
            },
            "order_size": order_size,
        }
        # 可选: 三层趋势过滤器
        rf_raw = rd.get("regime_filter") if isinstance(rd.get("regime_filter"), dict) else {}
        if rf_raw.get("enabled"):
            strategy["params"]["regime_filter"] = {
                "enabled": True,
                "regime_threshold": float(rf_raw.get("regime_threshold", 0.3)),
                "alpha_m": float(rf_raw.get("alpha_m", 2.0)),
                "alpha_sec": float(rf_raw.get("alpha_sec", 2.0)),
                "alpha_i": float(rf_raw.get("alpha_i", 2.0)),
            }
        # fall through to shared exit_rules compilation

    # --- ADAPTIVE_REGIME 向后兼容: 转换为 regime_router ---
    if strategy_name == "adaptive_regime":
        ar_cfg = sig.get("adaptive_regime") if isinstance(sig.get("adaptive_regime"), dict) else {}
        order_size = _to_int_or_default(cfg.get("strategy", {}).get("order_size"), 1000)
        strategy = cfg.setdefault("strategy", {})
        strategy["name"] = "adaptive_regime"
        strategy["fast"] = _to_int_or_default(ar_cfg.get("fast_ma"), 5)
        strategy["slow"] = _to_int_or_default(ar_cfg.get("slow_ma"), 20)
        strategy["order_size"] = order_size
        strategy["params"] = {
            "fast": strategy["fast"],
            "slow": strategy["slow"],
            "order_size": order_size,
            "regime_ma": _to_int_or_default(ar_cfg.get("regime_ma"), 60),
            "rsi_period": _to_int_or_default(ar_cfg.get("rsi_period"), 6),
            "rsi_buy_threshold": float(ar_cfg.get("rsi_buy_threshold", 20.0)),
            "rsi_sell_threshold": float(ar_cfg.get("rsi_sell_threshold", 80.0)),
            "mr_max_hold_days": _to_int_or_default(ar_cfg.get("mr_max_hold_days"), 5),
            "mr_stop_loss_pct": float(ar_cfg.get("mr_stop_loss_pct", 0.03)),
        }
        # fall through to shared exit_rules compilation

    if strategy_name not in ("regime_router", "adaptive_regime"):
        ma_key = "ema" if strategy_pack == "EMA_CROSS" else "sma"
        ma_cfg = sig.get(ma_key) if isinstance(sig.get(ma_key), dict) else {}

        strategy = cfg.setdefault("strategy", {})
        fast = _to_int_or_default(ma_cfg.get("fast_ma"), strategy.get("fast", 5))
        slow = _to_int_or_default(ma_cfg.get("slow_ma"), strategy.get("slow", 20))
        order_size = _to_int_or_default(strategy.get("order_size"), 1000)

        strategy["name"] = strategy_name
        strategy["fast"] = fast
        strategy["slow"] = slow
        strategy["order_size"] = order_size
        entry_filter = sig.get("entry_filter") if isinstance(sig.get("entry_filter"), dict) else {}
        strategy["params"] = {
            **dict(strategy.get("params") or {}),
            "fast": fast,
            "slow": slow,
            "order_size": order_size,
            "signal_class": "TREND",
            "trend_signal_family": "MA_CROSS",
            "ma_type": "EMA" if strategy_name == "ema_cross" else "SMA",
            "enable_entry_above_slow_ma": bool(entry_filter.get("enable_entry_above_slow_ma", False)),
            "enable_entry_slow_ma_slope": bool(entry_filter.get("enable_entry_slow_ma_slope", False)),
            "entry_slope_lookback": int(entry_filter.get("entry_slope_lookback", 5)),
        }

    # ── Shared exit_rules compilation (ALL strategies) ──
    strategy = cfg.setdefault("strategy", {})
    exit_rules = wb_cfg.get("exit_rules") if isinstance(wb_cfg.get("exit_rules"), dict) else {}
    atr_stop = exit_rules.get("atr_stop") if isinstance(exit_rules.get("atr_stop"), dict) else {}
    if atr_stop:
        strategy.setdefault("params", {})["enable_atr_stop"] = bool(atr_stop.get("enabled", False))
        strategy["params"]["atr_stop_k"] = float(atr_stop.get("k", 2.0))
    trailing = exit_rules.get("trailing") if isinstance(exit_rules.get("trailing"), dict) else {}
    if trailing:
        strategy.setdefault("params", {})["enable_atr_trail"] = bool(trailing.get("enabled", False))
        strategy["params"]["atr_trail_k"] = float(trailing.get("k", 3.0))
    time_exit = exit_rules.get("time_exit") if isinstance(exit_rules.get("time_exit"), dict) else {}
    if time_exit:
        strategy["params"]["max_hold_days"] = int(time_exit.get("n_days", 0)) if bool(time_exit.get("enabled", False)) else 0
    hold_constraint = exit_rules.get("hold_constraint") if isinstance(exit_rules.get("hold_constraint"), dict) else {}
    if hold_constraint:
        strategy["params"]["min_hold_days"] = int(hold_constraint.get("min_hold_days", 0))
        strategy["params"]["cooldown_days"] = int(hold_constraint.get("cooldown_days", 0))

    # 止盈 + 固定止损 + ATR止损/移动止盈 → exit config
    take_profit = exit_rules.get("take_profit") if isinstance(exit_rules.get("take_profit"), dict) else {}
    fixed_stop = exit_rules.get("fixed_stop") if isinstance(exit_rules.get("fixed_stop"), dict) else {}
    exit_cfg = cfg.setdefault("exit", {})
    if take_profit:
        exit_cfg["enable_take_profit"] = bool(take_profit.get("enabled", False))
        exit_cfg["take_profit_mode"] = str(take_profit.get("mode", "pct"))
        exit_cfg["take_profit_pct"] = float(take_profit.get("pct", 0.10))
        exit_cfg["take_profit_atr_k"] = float(take_profit.get("atr_k", 3.0))
    if fixed_stop:
        exit_cfg["enable_fixed_stop_loss"] = bool(fixed_stop.get("enabled", False))
        exit_cfg["fixed_stop_loss_pct"] = float(fixed_stop.get("pct", 0.05))
    if atr_stop:
        exit_cfg["enable_atr_stop"] = bool(atr_stop.get("enabled", False))
        exit_cfg["atr_stop_k"] = float(atr_stop.get("k", 2.0))
    if trailing:
        exit_cfg["enable_atr_trail"] = bool(trailing.get("enabled", False))
        exit_cfg["atr_trail_k"] = float(trailing.get("k", 3.0))

    # 风险预算 → risk_budget config
    pos_risk = wb_cfg.get("position_risk") if isinstance(wb_cfg.get("position_risk"), dict) else {}
    rb_cfg = pos_risk.get("risk_budget") if isinstance(pos_risk.get("risk_budget"), dict) else {}
    if rb_cfg:
        risk_budget = cfg.setdefault("risk_budget", {})
        risk_budget["enabled"] = bool(rb_cfg.get("enabled", False))
        risk_budget["base_portfolio_risk"] = float(rb_cfg.get("base_portfolio_risk", 0.06))
        risk_budget["trend_multiplier"] = float(rb_cfg.get("trend_multiplier", 1.0))
        risk_budget["dd_scale_10"] = float(rb_cfg.get("dd_scale_10", 0.8))
        risk_budget["dd_scale_15"] = float(rb_cfg.get("dd_scale_15", 0.6))
        risk_budget["dd_fixed_20"] = float(rb_cfg.get("dd_fixed_20", 0.03))
        risk_budget["dd_stop_pct"] = float(rb_cfg.get("dd_stop_pct", 0.25))
        risk_budget["dd_stop_cooldown_days"] = int(rb_cfg.get("dd_stop_cooldown_days", 120))
        risk_budget["dd_stop_protect_days"] = int(rb_cfg.get("dd_stop_protect_days", 60))
        risk_budget["min_active_ratio"] = float(rb_cfg.get("min_active_ratio", 0.6))
        # atr_stop_k: prefer risk_budget value, fallback to exit_rules.atr_stop.k
        _rb_atr_k = rb_cfg.get("atr_stop_k")
        if _rb_atr_k is not None:
            risk_budget["atr_stop_k"] = float(_rb_atr_k)
        elif atr_stop:
            risk_budget["atr_stop_k"] = float(atr_stop.get("k", 2.0))

    # MA200 市场过滤器 → market_filter config
    mf_cfg = pos_risk.get("market_filter") if isinstance(pos_risk.get("market_filter"), dict) else {}
    if mf_cfg:
        market_filter = cfg.setdefault("market_filter", {})
        market_filter["enabled"] = bool(mf_cfg.get("enabled", False))
        market_filter["slope_window"] = int(mf_cfg.get("slope_window", 10))
        market_filter["slope_ma_period"] = int(mf_cfg.get("slope_ma_period", 50))
        market_filter["bull_multiplier"] = float(mf_cfg.get("bull_multiplier", 1.5))
        market_filter["light_multiplier"] = float(mf_cfg.get("light_multiplier", 0.6))
        market_filter["ema_light_fast"] = int(mf_cfg.get("ema_light_fast", 5))
        market_filter["ema_light_slow"] = int(mf_cfg.get("ema_light_slow", 20))

    # ── Benchmark Regime 过滤器 ──
    br_cfg = wb_cfg.get("benchmark_regime") if isinstance(wb_cfg.get("benchmark_regime"), dict) else {}
    if br_cfg:
        br = cfg.setdefault("benchmark_regime", {})
        br["enabled"] = bool(br_cfg.get("enabled", False))
        br["fast_period"] = int(br_cfg.get("fast_period", 20))
        br["slow_period"] = int(br_cfg.get("slow_period", 60))
        br["slope_window"] = int(br_cfg.get("slope_window", 5))

    # ── Breadth 动态仓位 ──
    breadth_cfg = pos_risk.get("breadth") if isinstance(pos_risk.get("breadth"), dict) else {}
    if breadth_cfg:
        breadth = cfg.setdefault("breadth", {})
        breadth["enabled"] = bool(breadth_cfg.get("enabled", False))
        breadth["score_type"] = str(breadth_cfg.get("score_type", "B"))
        breadth["mapping_mode"] = str(breadth_cfg.get("mapping_mode", "smooth"))
        breadth["min_positions"] = int(breadth_cfg.get("min_positions", 3))
        breadth["max_positions"] = int(breadth_cfg.get("max_positions", 15))
        breadth["step_high"] = float(breadth_cfg.get("step_high", 0.60))
        breadth["step_mid"] = float(breadth_cfg.get("step_mid", 0.45))
        breadth["smooth_lo"] = float(breadth_cfg.get("smooth_lo", 0.40))
        breadth["smooth_range"] = float(breadth_cfg.get("smooth_range", 0.20))
        breadth["ema_fast"] = int(breadth_cfg.get("ema_fast", 8))
        breadth["ema_slow"] = int(breadth_cfg.get("ema_slow", 25))
        breadth["mode"] = str(breadth_cfg.get("mode", "dynamic_maxpos"))
        breadth["gate_threshold"] = float(breadth_cfg.get("gate_threshold", 0.45))
        breadth["gate_quantile_window"] = int(breadth_cfg.get("gate_quantile_window", 252))
        breadth["gate_quantile_pct"] = float(breadth_cfg.get("gate_quantile_pct", 0.20))
        breadth["gate_persist_days"] = int(breadth_cfg.get("gate_persist_days", 3))
        breadth["size_scale_floor"] = float(breadth_cfg.get("size_scale_floor", 0.3))

    # ── 交易成本覆盖 ──
    cost_cfg = wb_cfg.get("costs") if isinstance(wb_cfg.get("costs"), dict) else {}
    if cost_cfg:
        costs = cfg.setdefault("costs", {})
        for k in ("commission_rate", "commission_min", "stamp_tax_rate", "slippage_bps"):
            if k in cost_cfg:
                costs[k] = float(cost_cfg[k])
        if "slippage_mode" in cost_cfg:
            costs["slippage_mode"] = str(cost_cfg["slippage_mode"])

    return cfg


def _run_backtest_v2_experiment_sync(
    body: BacktestV2ExperimentRequest,
    progress_hook: Callable[[int, str], None] | None = None,
) -> dict[str, Any]:
    bt_root = _bt_root()
    if not bt_root.exists():
        raise HTTPException(status_code=500, detail=f"backtest_V2 root not found: {bt_root}")

    try:
        from backend.core.tools.experiment_runner import run_experiment  # type: ignore
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"failed to import experiment tools: {exc}")

    cfg_rel = body.config_path.strip() if (body.config_path or "").strip() else "configs/pams_cn_pg.json"
    cfg_path = (bt_root / cfg_rel).resolve()
    if not cfg_path.exists():
        cfg_path_alt = (bt_root.parent / cfg_rel).resolve()
        if cfg_path_alt.exists():
            cfg_path = cfg_path_alt
        else:
            raise HTTPException(status_code=400, detail=f"config not found: {cfg_path}")

    try:
        base_cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid config json: {cfg_path} ({exc})")

    overrides: dict[str, Any] = {}
    if body.symbols:
        overrides["symbols"] = list(body.symbols)
    if body.start_date:
        overrides["start_date"] = body.start_date
    if body.end_date:
        overrides["end_date"] = body.end_date
    if body.benchmark:
        overrides["benchmark"] = body.benchmark
    if body.compare_symbol:
        overrides["compare_symbol"] = body.compare_symbol
    if body.initial_capital is not None:
        overrides["initial_capital"] = float(body.initial_capital)
    if body.max_positions is not None:
        overrides["max_positions"] = int(body.max_positions)
    if body.base_order_value is not None:
        overrides["base_order_value"] = float(body.base_order_value)
    if body.lot_size is not None:
        overrides["lot_size"] = int(body.lot_size)
    if body.universe_limit is not None:
        overrides["universe_limit"] = int(body.universe_limit)
    if body.fast_mode is not None:
        overrides["fast_mode"] = bool(body.fast_mode)
    if body.config_id:
        overrides["config_id"] = str(body.config_id)
    if body.workbench_mode:
        overrides["workbench_mode"] = str(body.workbench_mode)
    if isinstance(body.workbench_config, dict):
        wb_cfg = sanitize_json(dict(body.workbench_config))
        overrides["workbench_config"] = _build_runtime_cfg_from_workbench(base_cfg, body, wb_cfg)
        overrides["original_workbench_config"] = wb_cfg
    if body.universe_mode:
        overrides["universe_mode"] = str(body.universe_mode)
    if body.industries:
        overrides["industries"] = list(body.industries)
    if body.price_adj:
        overrides["price_adj"] = str(body.price_adj)
    # 选股排序参数透传
    if body.enable_strength_rank is not None:
        overrides["enable_strength_rank"] = bool(body.enable_strength_rank)
    if body.strength_ma is not None:
        overrides["strength_ma"] = int(body.strength_ma)
    if body.strength_top_k_mode is not None:
        overrides["strength_top_k_mode"] = str(body.strength_top_k_mode)
    if body.enable_multifactor_rank is not None:
        overrides["enable_multifactor_rank"] = bool(body.enable_multifactor_rank)
    if body.mf_topk is not None:
        overrides["mf_topk"] = int(body.mf_topk)

    env_backup = {
        "PAMS_PG_HOST": os.environ.get("PAMS_PG_HOST"),
        "PAMS_PG_PORT": os.environ.get("PAMS_PG_PORT"),
        "PAMS_PG_DBNAME": os.environ.get("PAMS_PG_DBNAME"),
        "PAMS_PG_USER": os.environ.get("PAMS_PG_USER"),
        "PAMS_PG_PASSWORD": os.environ.get("PAMS_PG_PASSWORD"),
    }
    os.environ["PAMS_PG_HOST"] = os.environ.get("PGHOST", env_backup["PAMS_PG_HOST"] or "pams-postgres")
    os.environ["PAMS_PG_PORT"] = os.environ.get("PGPORT", env_backup["PAMS_PG_PORT"] or "5432")
    os.environ["PAMS_PG_DBNAME"] = os.environ.get("PGDATABASE", env_backup["PAMS_PG_DBNAME"] or "pams")
    os.environ["PAMS_PG_USER"] = os.environ.get("PGUSER", env_backup["PAMS_PG_USER"] or "pams")
    os.environ["PAMS_PG_PASSWORD"] = os.environ.get("PGPASSWORD", env_backup["PAMS_PG_PASSWORD"] or "")

    requested_preset = str(body.preset or "").strip()
    try:
        result = run_experiment(str(cfg_path), requested_preset or "single", overrides, progress_hook=progress_hook)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"experiment run failed: {exc}")
    finally:
        for k, v in env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    try:
        _attach_run_profile_summary(result)
    except Exception:
        pass

    try:
        result = stabilize_experiment_result(
            bt_root=bt_root,
            result=result if isinstance(result, dict) else {},
            base_cfg=base_cfg,
            overrides=overrides,
            run_profile_summary=result.get("run_profile_summary") if isinstance(result, dict) else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f"artifact stabilization failed: {exc}")

    result.setdefault("exp_id", "")
    result.setdefault("results_dir", "")
    result.setdefault("status", "OK")
    result["requested_preset"] = requested_preset
    return sanitize_json(result)


def _attach_run_profile_summary(result: dict[str, Any]) -> None:
    if not isinstance(result, dict):
        return
    results_dir_raw = str(result.get("results_dir") or "").strip()
    if not results_dir_raw:
        return
    rp = Path(results_dir_raw) / "run_profile.json"
    if not rp.exists():
        return
    try:
        obj = json.loads(rp.read_text(encoding="utf-8-sig"))
    except Exception:
        return
    stages = obj.get("stage_seconds") if isinstance(obj.get("stage_seconds"), dict) else {}
    summary: dict[str, Any] = {
        "run_profile_path": str(rp),
        "total_wall_seconds": float(obj.get("total_wall_seconds", 0.0) or 0.0),
        "stage_seconds": {str(k): float(v or 0.0) for k, v in stages.items()},
        "symbols_count": int(obj.get("symbols_count", 0) or 0),
        "trading_days": int(obj.get("trading_days", 0) or 0),
        "variant_count": int(obj.get("variant_count", 0) or 0),
        "row_count": int(obj.get("row_count", 0) or 0),
        "rows_per_second": float(obj.get("rows_per_second", 0.0) or 0.0),
        "bottleneck_stage": str(obj.get("bottleneck_stage") or ""),
        "bottleneck_label": str(obj.get("bottleneck_label") or "BOTTLENECK_UNKNOWN"),
    }
    perf = obj.get("perf") if isinstance(obj.get("perf"), dict) else {}
    if perf:
        summary["perf"] = {
            "db_load_seconds": float(perf.get("db_load_seconds", 0.0) or 0.0),
            "precompute_seconds": float(perf.get("precompute_seconds", 0.0) or 0.0),
            "simulation_seconds": float(perf.get("simulation_seconds", 0.0) or 0.0),
            "io_write_seconds": float(perf.get("io_write_seconds", 0.0) or 0.0),
            "db_queries": int(perf.get("db_queries", 0) or 0),
            "cache_hit_rate": float(perf.get("cache_hit_rate", 0.0) or 0.0),
        }
    tips: list[str] = []
    b = summary["bottleneck_label"]
    if b == "BOTTLENECK_DATA_LOAD":
        tips.append("数据加载是主要瓶颈：建议减少 universe_limit 或缩短回测区间。")
    elif b == "BOTTLENECK_SIMULATION":
        tips.append("仿真执行是主要瓶颈：建议启用 fast_mode 并关闭非必要明细写盘。")
    elif b == "BOTTLENECK_PRECOMPUTE":
        tips.append("预计算是主要瓶颈：建议缩短 lookback 或减少因子维度。")
    elif b == "BOTTLENECK_IO":
        tips.append("写盘是主要瓶颈：建议关闭 trades/candidates 明细输出。")
    if float(summary.get("rows_per_second", 0.0) or 0.0) <= 0.0:
        tips.append("当前 rows_per_second=0，建议检查实验是否无有效分组输出。")
    summary["optimization_tips"] = tips
    result["run_profile_summary"] = summary


def _run_backtest_v2_experiment_job(job_id: str, body: BacktestV2ExperimentRequest) -> None:
    try:
        preset = str(body.preset or "G1-G4")
        if _is_cancel_requested(job_id):
            _update_job(job_id, status="canceled", message="实验已取消")
            return
        _update_job(job_id, status="running", progress_pct=3, message=f"开始实验：{preset}")

        def _progress_cb(pct: int, msg: str) -> None:
            if _is_cancel_requested(job_id):
                return
            _update_job(job_id, status="running", progress_pct=int(max(0, min(99, pct))), message=str(msg))

        payload = _run_backtest_v2_experiment_sync(body, progress_hook=_progress_cb)
        if _is_cancel_requested(job_id):
            _update_job(job_id, status="canceled", message="实验已取消")
            return
        _update_job(job_id, status="running", progress_pct=95, message="汇总矩阵与报告")
        if _is_cancel_requested(job_id):
            _update_job(job_id, status="canceled", message="实验已取消")
            return
        _update_job(job_id, status="success", progress_pct=100, message="实验完成", result=payload)
    except Exception as exc:
        msg = str(exc)
        if isinstance(exc, HTTPException):
            msg = str(exc.detail)
        if _is_cancel_requested(job_id):
            _update_job(job_id, status="canceled", message="实验已取消")
            return
        _update_job(job_id, status="failed", message="实验失败", error=msg)


@router.post("/api/backtest_v2/experiment/run")
def run_backtest_v2_experiment(body: BacktestV2ExperimentRequest):
    return _run_backtest_v2_experiment_sync(body)


@router.post("/api/backtest_v2/experiment/run_async")
def run_backtest_v2_experiment_async(body: BacktestV2ExperimentRequest):
    preset_key = str(body.preset or "").strip().upper()
    eta = 480
    if preset_key in {"G1-G4", "REGIME_BUFFER_2X2", "ATR_RISK_2X2", "ATR_PORTFOLIO_VALIDATE_V1", "PORTFOLIO_FILL_VALIDATE_V1", "TREND_FILTER_VALIDATE_V1", "TREND_TIER_VALIDATE_V1", "TREND_ACCEL_BRAKE_VALIDATE_V1", "TREND_BRAKE_CONFIRM_VALIDATE_V1", "STRENGTH_RANK_VALIDATE_V1", "FULL_RANGE_VALIDATE_V1", "CANDIDATE_DIAG_VALIDATE_V1", "SLOT_DEBUG_VALIDATE_V1", "MAX_POSITION_EXPAND_VALIDATE_V1", "STRONG_ONLY_VALIDATE_V1", "MULTIFACTOR_RANKING_VALIDATE_V1", "MULTIFACTOR_RANKING_WALKFORWARD_V1", "MF_RANK_REGIME_GATE_VALIDATE_V1", "MULTIFACTOR_BALANCED_V1", "MULTIFACTOR_FUSION_COMPARE_V1", "MULTIFACTOR_INCREMENTAL_V1", "MULTIFACTOR_INCREMENTAL_V1_6_1A", "EXPERIMENT_6_1A", "6.1A", "MULTIFACTOR_INCREMENTAL_V1_6_1B", "EXPERIMENT_6_1B", "6.1B", "MULTIFACTOR_INCREMENTAL_V1_6_1_LIMIT", "MULTIFACTOR_INCREMENTAL_V1_6_4", "EXPERIMENT_6_4", "6.4", "EXPERIMENT_6_1_LIMIT", "6.1L"}:
        eta = 240
    elif preset_key in {"STRENGTH_RANK_VALIDATE_V2", "STRENGTH_RANK_VALIDATE_V2A", "STRENGTH_RANK_VALIDATE_V2B", "ENGINE_PERF_COMPARE_V1", "ENGINE_PERF_COMPARE_V2"}:
        eta = 180 if bool(body.fast_mode) else 360
    elif preset_key in {"ATR_PARAM_SCAN_V1"}:
        eta = 1200
    elif preset_key in {"ATR_PARAM_VALIDATE_UNIVOTE", "ATR_PARAM_VALIDATE_UNIVOTE_V2"}:
        eta = 900
    job_id = _create_job("experiment", eta_seconds=eta)
    th = threading.Thread(target=_run_backtest_v2_experiment_job, args=(job_id, body), daemon=True)
    th.start()
    return {"job_id": job_id, "status": "queued"}


@router.get("/api/backtest_v2/jobs/{job_id}")
def get_backtest_v2_job(job_id: str):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if not job:
        disk_job = _load_job_from_disk(job_id)
        if not disk_job:
            raise HTTPException(status_code=404, detail=f"job not found: {job_id}")
        payload = _job_payload(dict(disk_job))
    else:
        payload = _job_payload(dict(job))
    return _sanitize_for_json(payload)


@router.post("/api/backtest_v2/jobs/{job_id}/cancel")
def cancel_backtest_v2_job(job_id: str):
    job = _mark_job_canceled(job_id, message="用户取消")
    if not job:
        raise HTTPException(status_code=404, detail=f"job not found: {job_id}")
    return _sanitize_for_json(_job_payload(dict(job)))
