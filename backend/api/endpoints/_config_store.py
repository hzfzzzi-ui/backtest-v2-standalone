from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ._paths import _configs_root
from ._utils import sanitize_json, _hash_json, _sanitize_for_json

router = APIRouter(tags=["backtest_v2"])

_FLOW_SCRIPT_CONFIG_ID = "cfg_flow_smoke_v1"
_BREAKOUT_CHAMPION_CONFIG_ID = "cfg_champion_breakout_p3d"
_EMA_CHAMPION_CONFIG_ID = "cfg_champion_ema_g5"
_EXP4_ALL3_CONFIG_ID = "cfg_exp4_all3_2016_v1"
_C4_CHAMPION_CONFIG_ID = "cfg_champion_0407_c4"


def _flow_script_config_json() -> dict[str, Any]:
    return {
        "mode": "experiment",
        "strategy_pack": "SMA_CROSS",
        "universe_mode": "CUSTOM",
        "universe": {
            "start": "2025-01-01",
            "end": "2025-03-31",
            "benchmark": "000300.SH",
            "symbols": ["600000.SH", "000001.SZ", "600519.SH"],
            "limit": 100,
            "filters": {
                "exclude_st": True,
                "exclude_suspended": True,
                "min_list_days": 120,
                "min_avg_turnover_20d": 100000000,
                "limit_rule": "skip",
            },
        },
        "signal_generation": {
            "enabled": True,
            "strategy": "SMA_CROSS",
            "sma": {"fast_ma": 5, "slow_ma": 20, "entry_buffer_pct": 1.0},
        },
        "signal_composition": {"enabled": True, "compose_mode": "WEIGHTED_SCORE"},
        "exit_rules": {
            "enabled": True,
            "signal_reverse": True,
            "atr_stop": {"enabled": True, "k": 0.8},
            "trailing": {"enabled": False, "k": 2.0},
        },
        "position_risk": {
            "enabled": True,
            "max_positions": 10,
            "single_stock_cap": 0.1,
            "industry_cap": 0.3,
            "lot": 100,
            "cash_shortage_policy": "skip",
        },
        "flow_script": {
            "script_id": "flow_smoke_v1",
            "description": "最小通流：validate -> experiment(run_async) -> group inspect -> execution preview",
            "recommended_preset": "G1-G4",
        },
    }


def _ensure_builtin_flow_script_config() -> None:
    root = _configs_root()
    p = root / f"{_FLOW_SCRIPT_CONFIG_ID}.json"
    cfg_obj = sanitize_json(_flow_script_config_json())
    cfg_hash = _hash_json(cfg_obj)
    saved_at = datetime.now().isoformat()
    payload = {
        "config_id": _FLOW_SCRIPT_CONFIG_ID,
        "config_hash": cfg_hash,
        "saved_at": saved_at,
        "name": "最小通流脚本",
        "tags": ["flow_script", "builtin"],
        "config_json": cfg_obj,
    }
    if p.exists():
        try:
            prev = json.loads(p.read_text(encoding="utf-8-sig"))
            if isinstance(prev, dict) and prev.get("config_hash") == cfg_hash:
                return
        except Exception:
            pass
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _breakout_champion_config_json() -> dict[str, Any]:
    """P3-D champion: breakout_window=20, TP=20%, trail=3, stop=1.5, DD=10%/0.5."""
    return {
        "mode": "experiment",
        "strategy_pack": "BREAKOUT_TREND",
        "universe_mode": "HS300_ZZ500",
        "industries": [],
        "universe": {
            "start": "2016-03-01",
            "end": "2026-03-01",
            "benchmark": "000300.SH",
            "symbols": [],
            "limit": 0,
            "price_adj": "hfq",
            "filters": {
                "exclude_st": True,
                "exclude_suspended": True,
                "min_list_days": 120,
                "min_avg_turnover_20d": 100000000,
                "price_min": 0,
                "price_max": 99999,
                "atr_pct_range": "0,100",
                "limit_rule": "ignore",
            },
        },
        "signal_generation": {
            "enabled": True,
            "strategy": "BREAKOUT_TREND",
            "regime_detection": {
                "enabled": False,
                "regime_ma": 120,
                "regime_filter": {
                    "enabled": False,
                    "regime_threshold": 0.3,
                    "alpha_m": 2.0,
                    "alpha_sec": 2.0,
                    "alpha_i": 2.0,
                },
            },
            "trend": {
                "strategy": "BREAKOUT_TREND",
                "fast_ma": 20,
                "slow_ma": 60,
                "entry_buffer_pct": 1,
            },
            "mr": {
                "strategy": "RSI_REVERSAL",
                "rsi_period": 6,
                "rsi_buy_threshold": 20,
                "rsi_sell_threshold": 80,
                "mr_max_hold_days": 5,
                "mr_stop_loss_pct": 0.03,
            },
            "sma": {"fast_ma": 20, "slow_ma": 60, "entry_buffer_pct": 1},
            "ema": {"fast_ma": 20, "slow_ma": 60, "entry_buffer_pct": 1},
            "breakout": {"breakout_window": 20},
            "entry_filter": {
                "enable_entry_above_slow_ma": False,
                "enable_entry_slow_ma_slope": False,
                "entry_slope_lookback": 5,
            },
            "ranking": {"momentum_top_pct": 0},
        },
        "stock_trend_filter": {
            "enabled": False,
            "short_ma": 20,
            "long_ma": 60,
        },
        "sector_gate": {
            "enabled": False,
            "rank_window": 60,
            "top_pct": 0.30,
        },
        "signal_composition": {
            "enabled": True,
            "compose_mode": "WEIGHTED_SCORE",
            "modules": [],
        },
        "exit_rules": {
            "enabled": True,
            "signal_reverse": True,
            "atr_stop": {"enabled": True, "k": 1.5},
            "trailing": {"enabled": True, "k": 3.0},
            "time_exit": {"enabled": False, "n_days": 20},
            "hold_constraint": {"min_hold_days": 5, "cooldown_days": 5},
            "take_profit": {"enabled": True, "mode": "pct", "pct": 0.20},
            "fixed_stop": {"enabled": False, "pct": 0.05},
            "ma20_exit": {"enabled": False},
            "low10_exit": {"enabled": True},
        },
        "universe_filter": {"min_price": 5},
        "position_risk": {
            "enabled": True,
            "max_positions": 10,
            "single_stock_cap": 0.10,
            "industry_cap": 0.30,
            "lot": 100,
            "cash_shortage_policy": "skip",
            "risk_budget": {
                "enabled": True,
                "dd_reduce_pct": 0.10,
                "dd_reduce_scale": 0.5,
                "atr_stop_k": 1.5,
            },
            "market_filter": {
                "enabled": False,
                "slope_ma_period": 50,
                "slope_window": 10,
                "bull_multiplier": 1.5,
                "light_multiplier": 0.6,
                "ema_light_fast": 5,
                "ema_light_slow": 20,
            },
            "cost_model": {
                "commission": "fixed_assumption",
                "stamp_tax": "fixed_assumption",
                "slippage": "fixed_assumption",
                "matching": "next_open",
            },
        },
        "exit_priority": [
            "止损 (ATR Stop)",
            "止盈 (Take Profit)",
            "追踪止损 (Trailing)",
            "LOW10退出",
            "信号反转 (Signal Reverse)",
        ],
    }


def _ema_champion_config_json() -> dict[str, Any]:
    """EMA(8,25) champion: TP=30%, trail=6, min5/cool5, CSI800."""
    return {
        "mode": "experiment",
        "strategy_pack": "EMA_CROSS",
        "universe_mode": "HS300_ZZ500",
        "industries": [],
        "universe": {
            "start": "2016-03-01",
            "end": "2026-03-01",
            "benchmark": "000300.SH",
            "symbols": [],
            "limit": 0,
            "price_adj": "hfq",
            "filters": {
                "exclude_st": True,
                "exclude_suspended": True,
                "min_list_days": 120,
                "min_avg_turnover_20d": 100000000,
                "price_min": 0,
                "price_max": 99999,
                "atr_pct_range": "0,100",
                "limit_rule": "ignore",
            },
        },
        "signal_generation": {
            "enabled": True,
            "strategy": "EMA_CROSS",
            "regime_detection": {
                "enabled": False,
                "regime_ma": 60,
                "regime_filter": {
                    "enabled": False,
                    "regime_threshold": 0.3,
                    "alpha_m": 2.0,
                    "alpha_sec": 2.0,
                    "alpha_i": 2.0,
                },
            },
            "trend": {
                "strategy": "EMA_CROSS",
                "fast_ma": 8,
                "slow_ma": 25,
                "entry_buffer_pct": 1,
            },
            "mr": {
                "strategy": "RSI_REVERSAL",
                "rsi_period": 6,
                "rsi_buy_threshold": 20,
                "rsi_sell_threshold": 80,
                "mr_max_hold_days": 5,
                "mr_stop_loss_pct": 0.03,
            },
            "sma": {"fast_ma": 8, "slow_ma": 25, "entry_buffer_pct": 1},
            "ema": {"fast_ma": 8, "slow_ma": 25, "entry_buffer_pct": 1},
            "breakout": {"breakout_window": 20},
            "entry_filter": {
                "enable_entry_above_slow_ma": False,
                "enable_entry_slow_ma_slope": False,
                "entry_slope_lookback": 5,
            },
            "ranking": {"momentum_top_pct": 0},
        },
        "stock_trend_filter": {
            "enabled": False,
            "short_ma": 20,
            "long_ma": 60,
        },
        "sector_gate": {
            "enabled": False,
            "rank_window": 60,
            "top_pct": 0.30,
        },
        "signal_composition": {
            "enabled": True,
            "compose_mode": "WEIGHTED_SCORE",
            "modules": [],
        },
        "exit_rules": {
            "enabled": True,
            "signal_reverse": True,
            "atr_stop": {"enabled": True, "k": 2.0},
            "trailing": {"enabled": True, "k": 6.0},
            "time_exit": {"enabled": False, "n_days": 20},
            "hold_constraint": {"min_hold_days": 5, "cooldown_days": 5},
            "take_profit": {"enabled": True, "mode": "pct", "pct": 0.30},
            "fixed_stop": {"enabled": False, "pct": 0.05},
            "ma20_exit": {"enabled": False},
            "low10_exit": {"enabled": False},
        },
        "universe_filter": {"min_price": 0},
        "position_risk": {
            "enabled": True,
            "max_positions": 10,
            "single_stock_cap": 0.10,
            "industry_cap": 0.30,
            "lot": 100,
            "cash_shortage_policy": "skip",
            "risk_budget": {
                "enabled": False,
                "dd_reduce_pct": 0.10,
                "dd_reduce_scale": 0.5,
                "atr_stop_k": 2.0,
            },
            "market_filter": {
                "enabled": False,
                "slope_ma_period": 50,
                "slope_window": 10,
                "bull_multiplier": 1.5,
                "light_multiplier": 0.6,
                "ema_light_fast": 5,
                "ema_light_slow": 20,
            },
            "cost_model": {
                "commission": "fixed_assumption",
                "stamp_tax": "fixed_assumption",
                "slippage": "fixed_assumption",
                "matching": "next_open",
            },
        },
        "exit_priority": [
            "止损 (ATR Stop)",
            "止盈 (Take Profit)",
            "追踪止损 (Trailing)",
            "信号反转 (Signal Reverse)",
        ],
    }


def _exp4_all3_config_json() -> dict[str, Any]:
    """Experiment 4 (ALL3): regime + ALL_A liquidity filter + ATR stop 1.2."""
    return {
        "mode": "experiment",
        "initial_capital": 1000000,
        "strategy_pack": "BREAKOUT_TREND",
        "universe_mode": "ALL_A",
        "industries": [],
        "universe": {
            "start": "2016-03-01",
            "end": "2026-03-01",
            "benchmark": "000300.SH",
            "symbols": [],
            "limit": 0,
            "price_adj": "hfq",
            "filters": {
                "exclude_st": True,
                "exclude_suspended": True,
                "min_list_days": 120,
                "min_avg_turnover_20d": 100000000,
                "price_min": 5,
                "price_max": 99999,
                "atr_pct_range": "0,100",
                "limit_rule": "ignore",
            },
        },
        "signal_generation": {
            "enabled": True,
            "strategy": "BREAKOUT_TREND",
            "regime_detection": {
                "enabled": True,
                "regime_ma": 60,
                "regime_filter": {
                    "enabled": False,
                    "regime_threshold": 0.3,
                    "alpha_m": 2.0,
                    "alpha_sec": 2.0,
                    "alpha_i": 2.0,
                },
            },
            "trend": {
                "strategy": "BREAKOUT_TREND",
                "fast_ma": 20,
                "slow_ma": 60,
                "entry_buffer_pct": 1,
            },
            "mr": {
                "strategy": "RSI_REVERSAL",
                "rsi_period": 6,
                "rsi_buy_threshold": 20,
                "rsi_sell_threshold": 80,
                "mr_max_hold_days": 5,
                "mr_stop_loss_pct": 0.03,
            },
            "sma": {"fast_ma": 20, "slow_ma": 60, "entry_buffer_pct": 1},
            "ema": {"fast_ma": 20, "slow_ma": 60, "entry_buffer_pct": 1},
            "breakout": {"breakout_window": 20},
            "entry_filter": {
                "enable_entry_above_slow_ma": False,
                "enable_entry_slow_ma_slope": False,
                "entry_slope_lookback": 5,
            },
            "ranking": {"momentum_top_pct": 0},
        },
        "benchmark_regime": {
            "enabled": True,
            "fast_period": 20,
            "slow_period": 120,
            "slope_window": 5,
        },
        "stock_trend_filter": {
            "enabled": True,
            "short_ma": 20,
            "long_ma": 60,
        },
        "sector_gate": {
            "enabled": False,
            "rank_window": 60,
            "top_pct": 0.30,
        },
        "signal_composition": {
            "enabled": True,
            "compose_mode": "WEIGHTED_SCORE",
            "modules": [],
        },
        "exit_rules": {
            "enabled": True,
            "signal_reverse": True,
            "atr_stop": {"enabled": True, "k": 1.2},
            "trailing": {"enabled": True, "k": 3.0},
            "time_exit": {"enabled": False, "n_days": 20},
            "hold_constraint": {"min_hold_days": 5, "cooldown_days": 5},
            "take_profit": {"enabled": False, "mode": "pct", "pct": 0.20},
            "fixed_stop": {"enabled": False, "pct": 0.05},
            "ma20_exit": {"enabled": False},
            "low10_exit": {"enabled": True},
        },
        "universe_filter": {"min_price": 5},
        "position_risk": {
            "enabled": True,
            "max_positions": 10,
            "single_stock_cap": 0.10,
            "industry_cap": 0.30,
            "lot": 100,
            "cash_shortage_policy": "skip",
            "risk_budget": {
                "enabled": True,
                "dd_reduce_pct": 0.10,
                "dd_reduce_scale": 0.5,
                "atr_stop_k": 1.2,
            },
            "market_filter": {
                "enabled": False,
                "slope_ma_period": 50,
                "slope_window": 10,
                "bull_multiplier": 1.5,
                "light_multiplier": 0.6,
                "ema_light_fast": 5,
                "ema_light_slow": 20,
            },
            "cost_model": {
                "commission": "fixed_assumption",
                "stamp_tax": "fixed_assumption",
                "slippage": "fixed_assumption",
                "matching": "next_open",
            },
        },
        "flow_script": {
            "script_id": "all3_regime_liquidity_atr_2016",
            "description": "重点：基准趋势过滤 + 全A流动性过滤（20日成交额）+ ATR止损收紧(1.2)，在2016-2026区间平衡收益与回撤。",
            "recommended_preset": "single",
        },
    }


def _c4_champion_config_json() -> dict[str, Any]:
    """C4 champion: breakout55 + profit_release portfolio mode (2016-2026, ALL_A)."""
    return {
        "mode": "experiment",
        "initial_capital": 1000000,
        "strategy_pack": "BREAKOUT_TREND",
        "universe_mode": "ALL_A",
        "industries": [],
        "universe": {
            "start": "2016-03-01",
            "end": "2026-03-01",
            "benchmark": "000300.SH",
            "symbols": [],
            "limit": 0,
            "price_adj": "hfq",
            "filters": {
                "exclude_st": True,
                "exclude_suspended": True,
                "min_list_days": 120,
                "min_avg_turnover_20d": 100000000,
                "price_min": 5,
                "price_max": 99999,
                "atr_pct_range": "0,100",
                "limit_rule": "ignore",
            },
        },
        "signal_generation": {
            "enabled": True,
            "strategy": "BREAKOUT_TREND",
            "regime_detection": {
                "enabled": True,
                "regime_ma": 60,
                "regime_filter": {
                    "enabled": False,
                    "regime_threshold": 0.3,
                    "alpha_m": 2.0,
                    "alpha_sec": 2.0,
                    "alpha_i": 2.0,
                },
            },
            "trend": {"strategy": "BREAKOUT_TREND", "fast_ma": 20, "slow_ma": 60, "entry_buffer_pct": 1},
            "mr": {
                "strategy": "RSI_REVERSAL",
                "rsi_period": 6,
                "rsi_buy_threshold": 20,
                "rsi_sell_threshold": 80,
                "mr_max_hold_days": 5,
                "mr_stop_loss_pct": 0.03,
            },
            "sma": {"fast_ma": 20, "slow_ma": 60, "entry_buffer_pct": 1},
            "ema": {"fast_ma": 20, "slow_ma": 60, "entry_buffer_pct": 1},
            "breakout": {
                "breakout_window": 55,
                "entry_confirm_mode": "none",
                "entry_delay_mode": "none",
            },
            "entry_filter": {
                "enable_entry_above_slow_ma": False,
                "enable_entry_slow_ma_slope": False,
                "entry_slope_lookback": 5,
            },
            "ranking": {"momentum_top_pct": 0},
        },
        "benchmark_regime": {"enabled": True, "fast_period": 20, "slow_period": 120, "slope_window": 5},
        "stock_trend_filter": {"enabled": False, "short_ma": 20, "long_ma": 60},
        "sector_gate": {"enabled": False, "rank_window": 60, "top_pct": 0.30},
        "signal_composition": {"enabled": True, "compose_mode": "WEIGHTED_SCORE", "modules": []},
        "exit_rules": {
            "enabled": True,
            "signal_reverse": True,
            "atr_stop": {"enabled": True, "k": 1.2},
            "trailing": {"enabled": True, "k": 3.0},
            "time_exit": {"enabled": False, "n_days": 20},
            "hold_constraint": {"min_hold_days": 5, "cooldown_days": 5},
            "take_profit": {"enabled": False, "mode": "pct", "pct": 0.20},
            "fixed_stop": {"enabled": False, "pct": 0.05},
            "ma20_exit": {"enabled": False},
            "low10_exit": {"enabled": True},
        },
        "universe_filter": {"min_price": 5},
        "position_risk": {
            "enabled": True,
            "max_positions": 10,
            "single_stock_cap": 0.10,
            "industry_cap": 0.30,
            "lot": 100,
            "cash_shortage_policy": "skip",
            "portfolio_mode": "profit_release",
            "risk_budget": {"enabled": True, "dd_reduce_pct": 0.10, "dd_reduce_scale": 0.5, "atr_stop_k": 1.2},
            "market_filter": {
                "enabled": False,
                "slope_ma_period": 50,
                "slope_window": 10,
                "bull_multiplier": 1.5,
                "light_multiplier": 0.6,
                "ema_light_fast": 5,
                "ema_light_slow": 20,
            },
            "cost_model": {
                "commission": "fixed_assumption",
                "stamp_tax": "fixed_assumption",
                "slippage": "fixed_assumption",
                "matching": "next_open",
            },
        },
        "flow_script": {
            "script_id": "breakout55_c4_profit_release_2016",
            "description": "C4: breakout55 + profit_release 仓位释放；ALL_A 2016-2026。",
            "recommended_preset": "single",
        },
    }


def _ensure_builtin_champion_configs() -> None:
    """Auto-create Breakout P3-D and EMA G5 champion config files if missing/stale."""
    root = _configs_root()
    champions = [
        (_BREAKOUT_CHAMPION_CONFIG_ID, "Breakout 冠军 P3-D", ["champion", "builtin", "breakout"], _breakout_champion_config_json),
        (_EMA_CHAMPION_CONFIG_ID, "EMA 冠军 G5", ["champion", "builtin", "ema"], _ema_champion_config_json),
        (_EXP4_ALL3_CONFIG_ID, "ALL3 趋势增强(2016-2026)", ["flow_script", "builtin", "all3", "regime", "liquidity", "atr"], _exp4_all3_config_json),
        (_C4_CHAMPION_CONFIG_ID, "4-7日冠军配置", ["flow_script", "builtin", "champion", "c4", "breakout55", "profit_release"], _c4_champion_config_json),
    ]
    for config_id, name, tags, config_fn in champions:
        p = root / f"{config_id}.json"
        cfg_obj = sanitize_json(config_fn())
        cfg_hash = _hash_json(cfg_obj)
        if p.exists():
            try:
                prev = json.loads(p.read_text(encoding="utf-8-sig"))
                if isinstance(prev, dict) and prev.get("config_hash") == cfg_hash:
                    continue
            except Exception:
                pass
        payload = {
            "config_id": config_id,
            "config_hash": cfg_hash,
            "saved_at": datetime.now().isoformat(),
            "name": name,
            "tags": tags,
            "config_json": cfg_obj,
        }
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class BacktestV2ConfigSaveRequest(BaseModel):
    config_json: dict[str, Any]
    name: str | None = None
    tags: list[str] | None = None


@router.post("/api/backtest_v2/configs")
def save_backtest_v2_config(body: BacktestV2ConfigSaveRequest):
    cfg_obj = sanitize_json(dict(body.config_json or {}))
    cfg_hash = _hash_json(cfg_obj)
    config_id = f"cfg_{cfg_hash[:12]}"
    saved_at = datetime.now().isoformat()
    payload = {
        "config_id": config_id,
        "config_hash": cfg_hash,
        "saved_at": saved_at,
        "name": str(body.name or ""),
        "tags": [str(x) for x in (body.tags or [])],
        "config_json": cfg_obj,
    }
    p = _configs_root() / f"{config_id}.json"
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return _sanitize_for_json({"config_id": config_id, "saved_at": saved_at, "config_hash": cfg_hash})


@router.get("/api/backtest_v2/configs/{config_id}")
def get_backtest_v2_config(config_id: str):
    _ensure_builtin_flow_script_config()
    _ensure_builtin_champion_configs()
    p = _configs_root() / f"{str(config_id)}.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"config not found: {config_id}")
    try:
        obj = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"config load failed: {exc}")
    return _sanitize_for_json(obj)


@router.get("/api/backtest_v2/configs")
def list_backtest_v2_configs(latest: int = Query(20, ge=1, le=200)):
    _ensure_builtin_flow_script_config()
    _ensure_builtin_champion_configs()
    root = _configs_root()
    rows: list[dict[str, Any]] = []
    for p in root.glob("cfg_*.json"):
        try:
            obj = json.loads(p.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        rows.append(
            {
                "config_id": str(obj.get("config_id") or p.stem),
                "saved_at": str(obj.get("saved_at") or ""),
                "name": str(obj.get("name") or ""),
                "tags": [str(x) for x in (obj.get("tags") or [])],
                "config_hash": str(obj.get("config_hash") or ""),
            }
        )
    rows.sort(
        key=lambda x: (
            1 if "flow_script" in set(x.get("tags") or []) else 0,
            str(x.get("saved_at") or ""),
        ),
        reverse=True,
    )
    return _sanitize_for_json({"items": rows[: int(latest)]})
