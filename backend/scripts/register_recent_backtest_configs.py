from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _results_root() -> Path:
    return (_repo_root() / "outputs").resolve()


def _experiments_root() -> Path:
    return _results_root() / "experiments"


def _configs_root() -> Path:
    root = _results_root() / "configs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _hash_json(obj: Any) -> str:
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _strategy_pack_from_name(name: str) -> str:
    n = str(name or "").strip().lower()
    if n == "ema_cross":
        return "EMA_CROSS"
    return "SMA_CROSS"


def _variant_label(params: dict[str, Any]) -> str:
    above = bool(params.get("enable_entry_above_slow_ma", False))
    slope = bool(params.get("enable_entry_slow_ma_slope", False))
    lb = int(params.get("entry_slope_lookback", 5) or 5)
    if above and slope:
        return f"ENTRY_FILTER(LB{lb})"
    if above:
        return "ENTRY_ABOVE_SLOW_MA"
    if slope:
        return f"ENTRY_SLOPE(LB{lb})"
    return "BASELINE"


def _to_workbench_config(
    run_config: dict[str, Any],
    run_meta: dict[str, Any],
) -> dict[str, Any]:
    universe = dict(run_config.get("universe") or {})
    strategy = dict(run_config.get("strategy") or {})
    params = dict(strategy.get("params") or {})
    sizing = dict(run_config.get("sizing") or {})
    execution = dict(run_config.get("execution") or {})
    costs = dict(run_config.get("costs") or {})
    counters = dict(run_meta.get("counters") or {})
    data = dict(run_meta.get("data") or {})

    strategy_name = str(strategy.get("name") or "sma_cross")
    strategy_pack = _strategy_pack_from_name(strategy_name)
    fast = int(strategy.get("fast", 5) or 5)
    slow = int(strategy.get("slow", 20) or 20)
    variant = _variant_label(params)
    start = str(universe.get("start") or data.get("start") or "")
    end = str(universe.get("end") or data.get("end") or "")
    benchmark = str(universe.get("benchmark") or data.get("benchmark") or "000300.SH")
    universe_mode = str(data.get("universe_mode") or "CUSTOM")
    universe_limit = int(data.get("universe_limit") or 1000)
    if variant == "ENTRY_FILTER(LB5)":
        filter_desc = "入场过滤=开(站上慢线+慢线斜率,LB5)"
    elif variant.startswith("ENTRY_FILTER("):
        filter_desc = f"入场过滤=开(站上慢线+慢线斜率,{variant.split('(')[-1].rstrip(')')})"
    elif variant == "ENTRY_ABOVE_SLOW_MA":
        filter_desc = "入场过滤=开(站上慢线)"
    elif variant.startswith("ENTRY_SLOPE("):
        filter_desc = f"入场过滤=开(慢线斜率,{variant.split('(')[-1].rstrip(')')})"
    else:
        filter_desc = "入场过滤=关"

    display_name = (
        f"[回测配置] {strategy_pack} {fast}/{slow} | "
        f"{filter_desc} | "
        f"{universe_mode}({universe_limit}) | {start}~{end}"
    )

    cfg = {
        "mode": "experiment",
        "strategy_pack": strategy_pack,
        "universe_mode": universe_mode,
        "universe": {
            "start": start,
            "end": end,
            "benchmark": benchmark,
            "symbols": list(universe.get("symbols") or []),
            "limit": universe_limit,
            "price_adj": str(run_meta.get("price_adj_mode") or "hfq"),
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
            "strategy": strategy_pack,
            "sma": {
                "fast_ma": fast,
                "slow_ma": slow,
                "entry_buffer_pct": 1.0,
            },
            "ema": {
                "fast_ma": fast,
                "slow_ma": slow,
                "entry_buffer_pct": 1.0,
            },
            "entry_filter": {
                "enable_entry_above_slow_ma": bool(params.get("enable_entry_above_slow_ma", False)),
                "enable_entry_slow_ma_slope": bool(params.get("enable_entry_slow_ma_slope", False)),
                "entry_slope_lookback": int(params.get("entry_slope_lookback", 5) or 5),
            },
        },
        "signal_composition": {
            "enabled": True,
            "compose_mode": "WEIGHTED_SCORE",
        },
        "exit_rules": {
            "enabled": True,
            "signal_reverse": True,
            "atr_stop": {
                "enabled": bool(strategy.get("enable_atr_stop", False)),
                "k": float(strategy.get("atr_stop_k", 0.8) or 0.8),
            },
            "trailing": {
                "enabled": bool(strategy.get("enable_atr_trail", False)),
                "k": float(strategy.get("atr_trail_k", 2.0) or 2.0),
            },
            "time_exit": {
                "enabled": False,
                "n_days": 20,
            },
        },
        "position_risk": {
            "enabled": True,
            "max_positions": int(counters.get("max_positions", 10) or 10),
            "single_stock_cap": 0.1,
            "industry_cap": 0.3,
            "lot": int(execution.get("lot_size", sizing.get("lot_size", 100)) or 100),
            "cash_shortage_policy": "skip",
        },
        "execution_assumptions": {
            "commission_bps": float(costs.get("commission_rate", 0.0003) or 0.0003) * 10000,
            "slippage_bps": float(costs.get("slippage_bps", 2.0) or 2.0),
            "buy_delay_days": 1,
            "sell_delay_days": 1,
            "fill_model": "open_next",
        },
        "flow_script": {
            "script_id": f"recent_{strategy_pack.lower()}_{fast}_{slow}_{variant.lower().replace('(', '_').replace(')', '').replace('+', '_').replace('/', '_')}",
            "description": "从最近实验自动注册，可在前端“加载”下拉直接调用",
            "naming_rule": "STRATEGY|ENTRY_FILTER|UNIVERSE|DATE_RANGE",
        },
        "_label": display_name,
    }
    return cfg


def _save_cfg(cfg: dict[str, Any], *, name: str, tags: list[str]) -> tuple[str, Path]:
    cfg_hash = _hash_json(cfg)
    config_id = f"cfg_{cfg_hash[:12]}"
    payload = {
        "config_id": config_id,
        "config_hash": cfg_hash,
        "saved_at": datetime.now().isoformat(),
        "name": name,
        "tags": tags,
        "config_json": cfg,
    }
    path = _configs_root() / f"{config_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return config_id, path


def _pick_experiments(count: int, exp_ids: list[str]) -> list[Path]:
    root = _experiments_root()
    if exp_ids:
        out: list[Path] = []
        for eid in exp_ids:
            p = root / eid
            if p.exists() and p.is_dir():
                out.append(p)
        return out
    exps = [p for p in root.glob("exp_*") if p.is_dir()]
    exps.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return exps[: max(1, int(count))]


def main() -> int:
    parser = argparse.ArgumentParser(description="Register recent experiments as frontend-loadable configs.")
    parser.add_argument("--count", type=int, default=2, help="How many recent experiments to register.")
    parser.add_argument("--exp-ids", type=str, default="", help="Comma separated exp ids. If set, count is ignored.")
    args = parser.parse_args()

    exp_ids = [x.strip() for x in str(args.exp_ids or "").split(",") if x.strip()]
    exps = _pick_experiments(args.count, exp_ids)
    if not exps:
        print("No experiments found.")
        return 1

    for exp_dir in exps:
        exp_id = exp_dir.name
        run_config = _load_json(exp_dir / "run_config.json")
        run_meta = _load_json(exp_dir / "run_meta.json")
        cfg = _to_workbench_config(run_config, run_meta)
        name = str(cfg.pop("_label"))
        tags = ["flow_script", "backtest_named", "recent"]
        ef = ((cfg.get("signal_generation") or {}).get("entry_filter") or {})
        if bool(ef.get("enable_entry_above_slow_ma", False) or ef.get("enable_entry_slow_ma_slope", False)):
            tags.append("entry_filter")
        else:
            tags.append("baseline")
        config_id, path = _save_cfg(cfg, name=name, tags=tags)
        print(f"{exp_id} -> {config_id} :: {name}")
        print(f"saved: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
