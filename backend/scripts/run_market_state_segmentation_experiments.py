from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.api.endpoints._experiment_runner_api import (  # noqa: E402
    BacktestV2ExperimentRequest,
    _build_runtime_cfg_from_workbench,
)
from backend.core.tools.experiment_runner import run_experiment  # noqa: E402


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _build_runtime_from_wb(
    base_cfg: dict[str, Any],
    wb_cfg: dict[str, Any],
) -> dict[str, Any]:
    body = BacktestV2ExperimentRequest(
        preset="single",
        universe_mode=str(wb_cfg.get("universe_mode", "ALL_A")),
        start_date=str((wb_cfg.get("universe") or {}).get("start", "2016-03-01")),
        end_date=str((wb_cfg.get("universe") or {}).get("end", "2026-03-01")),
        benchmark=str((wb_cfg.get("universe") or {}).get("benchmark", "000300.SH")),
        max_positions=int(((wb_cfg.get("position_risk") or {}).get("max_positions", 10))),
        fast_mode=True,
        price_adj=str((wb_cfg.get("universe") or {}).get("price_adj", "hfq")),
    )
    return _build_runtime_cfg_from_workbench(base_cfg, body, wb_cfg)


def _apply_variant(base_wb: dict[str, Any], variant: str) -> tuple[dict[str, Any], dict[str, Any]]:
    wb = deepcopy(base_wb)
    pos_risk = wb.setdefault("position_risk", {})
    mf = pos_risk.setdefault("market_filter", {})

    # Do not touch entry/exit; only market-state position control.
    mf["slope_ma_period"] = int(mf.get("slope_ma_period", 50))
    mf["slope_window"] = int(mf.get("slope_window", 10))
    mf["ema_light_fast"] = int(mf.get("ema_light_fast", 5))
    mf["ema_light_slow"] = int(mf.get("ema_light_slow", 20))

    if variant == "baseline_off":
        mf["enabled"] = False
        params = {"enabled": False}
    elif variant == "legacy_2state":
        mf.update({"enabled": True, "bull_multiplier": 1.2, "light_multiplier": 0.6})
        mf.pop("trans_down_multiplier", None)
        mf.pop("trans_up_multiplier", None)
        mf.pop("bear_multiplier", None)
        params = {"enabled": True, "bull": 1.2, "light": 0.6}
    elif variant == "segmented_v1":
        mf.update(
            {
                "enabled": True,
                "bull_multiplier": 1.2,
                "light_multiplier": 0.6,
                "trans_down_multiplier": 0.4,
                "trans_up_multiplier": 0.8,
                "bear_multiplier": 0.2,
            }
        )
        params = {"enabled": True, "bull": 1.2, "td": 0.4, "tu": 0.8, "bear": 0.2}
    elif variant == "segmented_v2":
        mf.update(
            {
                "enabled": True,
                "bull_multiplier": 1.1,
                "light_multiplier": 0.6,
                "trans_down_multiplier": 0.3,
                "trans_up_multiplier": 0.7,
                "bear_multiplier": 0.3,
            }
        )
        params = {"enabled": True, "bull": 1.1, "td": 0.3, "tu": 0.7, "bear": 0.3}
    elif variant == "segmented_v3":
        mf.update(
            {
                "enabled": True,
                "bull_multiplier": 1.3,
                "light_multiplier": 0.6,
                "trans_down_multiplier": 0.5,
                "trans_up_multiplier": 0.9,
                "bear_multiplier": 0.1,
            }
        )
        params = {"enabled": True, "bull": 1.3, "td": 0.5, "tu": 0.9, "bear": 0.1}
    else:
        raise ValueError(f"unknown variant: {variant}")
    return wb, params


def _run_one(
    *,
    base_cfg: dict[str, Any],
    wb_cfg: dict[str, Any],
    variant: str,
) -> dict[str, Any]:
    wb_variant, params = _apply_variant(wb_cfg, variant)
    runtime_cfg = _build_runtime_from_wb(base_cfg, wb_variant)
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(runtime_cfg, tmp, ensure_ascii=False, indent=2)
    tmp.close()
    tmp_path = tmp.name

    universe = wb_variant.get("universe") or {}
    overrides: dict[str, Any] = {
        "universe_mode": str(wb_variant.get("universe_mode", "ALL_A")),
        "start_date": str(universe.get("start", "2016-03-01")),
        "end_date": str(universe.get("end", "2026-03-01")),
        "benchmark": str(universe.get("benchmark", "000300.SH")),
        "initial_capital": float(wb_variant.get("initial_capital", 1_000_000)),
        "max_positions": int((wb_variant.get("position_risk") or {}).get("max_positions", 10)),
        "base_order_value": 0,
        "fast_mode": True,
        "price_adj": str(universe.get("price_adj", "hfq")),
        "momentum_top_pct": float((((wb_variant.get("signal_generation") or {}).get("ranking") or {}).get("momentum_top_pct", 0.0))),
    }
    try:
        result = run_experiment(tmp_path, preset="single", overrides=overrides)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {
        "variant": variant,
        "params": params,
        "exp_id": str(result.get("exp_id", "")),
        "results_dir": str(result.get("results_dir", "")),
        "cagr": float(result.get("cagr", 0.0) or 0.0),
        "sharpe": float(result.get("sharpe", 0.0) or 0.0),
        "max_drawdown": float(result.get("max_drawdown", 0.0) or 0.0),
        "trades": int(result.get("trades", 0) or 0),
        "avg_positions": float(result.get("avg_positions", 0.0) or 0.0),
        "turnover": float(result.get("turnover", 0.0) or 0.0),
        "market_filter_bull_days": int(result.get("market_filter_bull_days", 0) or 0),
        "market_filter_bear_days": int(result.get("market_filter_bear_days", 0) or 0),
        "market_state_trans_down_days": int(result.get("market_state_trans_down_days", 0) or 0),
        "market_state_trans_up_days": int(result.get("market_state_trans_up_days", 0) or 0),
    }


def main() -> None:
    t0 = time.perf_counter()
    base_cfg = _load_json(ROOT / "backend" / "configs" / "pams_cn_pg.json")
    base_cfg.setdefault("db", {})
    if str(base_cfg["db"].get("host") or "").strip() == "pams-postgres":
        base_cfg["db"]["host"] = "localhost"
    if not str(base_cfg["db"].get("password") or "").strip():
        env_pwd = str(os.environ.get("PGPASSWORD") or os.environ.get("PAMS_PG_PASSWORD") or "").strip()
        if env_pwd:
            base_cfg["db"]["password"] = env_pwd

    wb_payload = _load_json(ROOT / "outputs" / "configs" / "cfg_da4a2be7f3b7.json")
    wb_cfg = dict(wb_payload.get("config_json") or {})
    variants = ["baseline_off", "legacy_2state", "segmented_v1", "segmented_v2", "segmented_v3"]
    rows: list[dict[str, Any]] = []

    for v in variants:
        print(f"[RUN] {v}")
        row = _run_one(base_cfg=base_cfg, wb_cfg=wb_cfg, variant=v)
        rows.append(row)
        print(
            f"  -> exp={row['exp_id']} cagr={row['cagr']:.2%} sharpe={row['sharpe']:.2f} "
            f"mdd={row['max_drawdown']:.2%} trades={row['trades']}"
        )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = ROOT / "outputs" / "experiments" / f"market_state_segmentation_{stamp}.json"
    payload = {
        "generated_at": datetime.now().isoformat(),
        "base_config_id": "cfg_da4a2be7f3b7",
        "base_config_name": "3月6日冠军配置",
        "notes": "Entry/exit unchanged; only market-state position multipliers changed.",
        "results": rows,
        "elapsed_seconds": float(time.perf_counter() - t0),
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[DONE] {out_path}")


if __name__ == "__main__":
    main()

