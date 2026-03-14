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

from backend.core.services.experiment_runtime_service import build_runtime_cfg_from_workbench  # noqa: E402
from backend.core.tools.experiment_runner import run_experiment  # noqa: E402


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _build_runtime_from_wb(
    base_cfg: dict[str, Any],
    wb_cfg: dict[str, Any],
) -> dict[str, Any]:
    return build_runtime_cfg_from_workbench(
        base_cfg=base_cfg,
        request_payload={
            "preset": "single",
            "universe_mode": str(wb_cfg.get("universe_mode", "ALL_A")),
            "start_date": str((wb_cfg.get("universe") or {}).get("start", "2016-03-01")),
            "end_date": str((wb_cfg.get("universe") or {}).get("end", "2026-03-01")),
            "benchmark": str((wb_cfg.get("universe") or {}).get("benchmark", "000300.SH")),
            "max_positions": int(((wb_cfg.get("position_risk") or {}).get("max_positions", 10))),
            "fast_mode": True,
            "price_adj": str((wb_cfg.get("universe") or {}).get("price_adj", "hfq")),
        },
        wb_cfg=wb_cfg,
    )


def _apply_variant(base_wb: dict[str, Any], variant: str) -> dict[str, Any]:
    wb = deepcopy(base_wb)
    pos_risk = wb.setdefault("position_risk", {})
    sizing = wb.setdefault("sizing", {})
    market_filter = pos_risk.setdefault("market_filter", {})

    # Keep entry/exit unchanged; only modify sizing/risk position controls.
    sizing["min_positions"] = int(sizing.get("min_positions", 10) or 10)
    sizing["weight_mode"] = str(sizing.get("weight_mode", "equal"))

    if variant == "baseline":
        sizing["weight_mode"] = "equal"
        market_filter["enabled"] = False
    elif variant == "inverse_vol":
        sizing["weight_mode"] = "inverse_vol"
        market_filter["enabled"] = False
    elif variant == "market_filter":
        sizing["weight_mode"] = "equal"
        market_filter.update(
            {
                "enabled": True,
                "slope_ma_period": 50,
                "slope_window": 10,
                "bull_multiplier": 1.2,
                "light_multiplier": 0.6,
                "ema_light_fast": 5,
                "ema_light_slow": 20,
            }
        )
    elif variant == "combo":
        sizing["weight_mode"] = "inverse_vol"
        market_filter.update(
            {
                "enabled": True,
                "slope_ma_period": 50,
                "slope_window": 10,
                "bull_multiplier": 1.2,
                "light_multiplier": 0.6,
                "ema_light_fast": 5,
                "ema_light_slow": 20,
            }
        )
    else:
        raise ValueError(f"unknown variant: {variant}")
    return wb


def _run_one(
    *,
    base_cfg: dict[str, Any],
    wb_cfg: dict[str, Any],
    variant: str,
) -> dict[str, Any]:
    wb_variant = _apply_variant(wb_cfg, variant)
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
    }


def main() -> None:
    t0 = time.perf_counter()
    base_cfg = _load_json(ROOT / "backend" / "configs" / "pams_cn_pg.json")
    # Prefer local DB host in standalone runs (container alias may be unavailable on host).
    base_cfg.setdefault("db", {})
    base_cfg["db"]["host"] = str(base_cfg["db"].get("host") or "localhost")
    if base_cfg["db"]["host"] == "pams-postgres":
        base_cfg["db"]["host"] = "localhost"
    if not str(base_cfg["db"].get("password") or "").strip():
        env_pwd = str(
            os.environ.get("PGPASSWORD")
            or os.environ.get("PAMS_PG_PASSWORD")
            or ""
        ).strip()
        if env_pwd:
            base_cfg["db"]["password"] = env_pwd
    wb_payload = _load_json(ROOT / "outputs" / "configs" / "cfg_da4a2be7f3b7.json")
    wb_cfg = dict(wb_payload.get("config_json") or {})

    variants = ["baseline", "inverse_vol", "market_filter", "combo"]
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
    out_path = ROOT / "outputs" / "experiments" / f"dynamic_sizing_matrix_{stamp}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().isoformat(),
        "base_config_id": "cfg_da4a2be7f3b7",
        "base_config_name": "3月6日冠军配置",
        "notes": "Only sizing/position-risk changed; entry and stop unchanged.",
        "results": rows,
        "elapsed_seconds": float(time.perf_counter() - t0),
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[DONE] {out_path}")


if __name__ == "__main__":
    main()
