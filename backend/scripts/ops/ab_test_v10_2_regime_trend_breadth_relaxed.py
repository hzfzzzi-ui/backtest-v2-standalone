from __future__ import annotations

import copy
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from backend.core.tools.experiment_runtime_access import run_experiment_sync


ROOT = Path(__file__).resolve().parents[3]
OPS_ROOT = ROOT / "outputs" / "ops"
EXPERIMENT_ROOT = ROOT / "outputs" / "experiments"

SOURCE_EXP_ID = "exp_20260320_063727806_260c"
LEGACY_EXP_ID = "exp_20260320_124758017_a2de"
FORMAL_DEFAULT_EXP_ID = "exp_20260320_125317256_782c"
FORMAL_TREND_RELAXED_EXP_ID = "exp_20260320_144750475_7708"
WINDOW_START = "2017-06-01"
WINDOW_END = "2026-03-16"
ASSET_SCOPE = "cn_a_equity"
OPS_DIR = OPS_ROOT / "ab_test_v10_2_regime_trend_breadth_relaxed_20260320"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid json root: {path}")
    return payload


def _source_config() -> dict[str, Any]:
    return _load_json(EXPERIMENT_ROOT / SOURCE_EXP_ID / "input_config.json")


def _build_config(
    source_cfg: dict[str, Any],
    *,
    regime_engine: str,
    trend_long_ma_window: int | None = None,
    breadth_above_ma_long_window: int | None = None,
) -> dict[str, Any]:
    cfg = copy.deepcopy(source_cfg)
    universe = dict(cfg.get("universe") or {})
    universe["start"] = WINDOW_START
    universe["end"] = WINDOW_END
    universe["membership_mode"] = "PIT_DYNAMIC"
    cfg["universe"] = universe
    data_source = dict(cfg.get("data_source") or {})
    data_source["data_role"] = "v2_canonical"
    cfg["data_source"] = data_source
    regime_cfg: dict[str, Any] = {"engine": regime_engine}
    if regime_engine == "market_regime_framework":
        if trend_long_ma_window is not None:
            regime_cfg["trend_block"] = {
                "long_ma_window": int(trend_long_ma_window),
            }
        if breadth_above_ma_long_window is not None:
            regime_cfg["breadth_block"] = {
                "above_ma_long_window": int(breadth_above_ma_long_window),
            }
    cfg["regime_engine"] = regime_cfg
    return cfg


def _run(cfg: dict[str, Any]) -> str:
    result = run_experiment_sync(
        {
            "preset": "single",
            "asset_scope": ASSET_SCOPE,
            "workbench_config": cfg,
        }
    )
    if not isinstance(result, dict):
        raise RuntimeError("runtime service returned non-dict result")
    exp_id = str(result.get("exp_id") or "").strip()
    status = str(result.get("status") or "").strip().upper()
    if not exp_id or status != "OK":
        raise RuntimeError(f"experiment failed: {result!r}")
    return exp_id


def _exp_dir(exp_id: str) -> Path:
    exp_dir = EXPERIMENT_ROOT / exp_id
    if not exp_dir.exists():
        raise RuntimeError(f"missing experiment directory: {exp_dir}")
    return exp_dir


def _extract_row(*, variant: str, exp_id: str) -> dict[str, Any]:
    exp_dir = _exp_dir(exp_id)
    perf = _load_json(exp_dir / "perf.json")
    run_meta = _load_json(exp_dir / "run_meta.json")
    counters = run_meta.get("counters") if isinstance(run_meta.get("counters"), dict) else {}
    return {
        "variant": variant,
        "exp_id": exp_id,
        "total_return": perf.get("total_return"),
        "cagr": perf.get("cagr"),
        "sharpe": perf.get("sharpe"),
        "max_drawdown": perf.get("max_drawdown"),
        "trades": perf.get("trades"),
        "turnover": perf.get("turnover"),
        "trade_mode_main_days": counters.get("trade_mode_main_days"),
        "trade_mode_light_days": counters.get("trade_mode_light_days"),
        "trade_mode_notrade_days": counters.get("trade_mode_notrade_days"),
        "market_state_bull_days": counters.get("market_state_bull_days"),
        "market_state_trans_up_days": counters.get("market_state_trans_up_days"),
        "market_state_trans_down_days": counters.get("market_state_trans_down_days"),
        "market_state_bear_days": counters.get("market_state_bear_days"),
        "effective_execution_start_date": perf.get("effective_execution_start_date"),
    }


def _load_daily(exp_id: str) -> pd.DataFrame:
    path = EXPERIMENT_ROOT / exp_id / "portfolio_daily.csv"
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    return df


def _cross_counts(legacy_exp_id: str, compare_exp_id: str) -> dict[str, Any]:
    legacy = _load_daily(legacy_exp_id)[["date", "market_state", "trade_mode", "selected_count"]].rename(
        columns={
            "market_state": "legacy_market_state",
            "trade_mode": "legacy_trade_mode",
            "selected_count": "legacy_selected_count",
        }
    )
    compare = _load_daily(compare_exp_id)[["date", "market_state", "trade_mode", "selected_count"]].rename(
        columns={
            "market_state": "compare_market_state",
            "trade_mode": "compare_trade_mode",
            "selected_count": "compare_selected_count",
        }
    )
    merged = legacy.merge(compare, on="date", how="inner")
    loss_days = merged[
        (merged["legacy_market_state"] == "BULL")
        & (merged["compare_market_state"] == "TRANS_UP")
        & (
            pd.to_numeric(merged["legacy_selected_count"], errors="coerce").fillna(0)
            > pd.to_numeric(merged["compare_selected_count"], errors="coerce").fillna(0)
        )
    ]
    return {
        "aligned_days": int(len(merged)),
        "bull_to_trans_up_days": int(
            ((merged["legacy_market_state"] == "BULL") & (merged["compare_market_state"] == "TRANS_UP")).sum()
        ),
        "bull_to_bull_days": int(
            ((merged["legacy_market_state"] == "BULL") & (merged["compare_market_state"] == "BULL")).sum()
        ),
        "bull_to_trans_up_selected_loss_days": int(len(loss_days)),
        "bull_to_trans_up_selected_loss_total": int(
            (
                pd.to_numeric(loss_days["legacy_selected_count"], errors="coerce").fillna(0)
                - pd.to_numeric(loss_days["compare_selected_count"], errors="coerce").fillna(0)
            ).sum()
        ),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _fmt_num(value: Any, digits: int = 4) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return ""


def main() -> None:
    OPS_DIR.mkdir(parents=True, exist_ok=True)
    source_cfg = _source_config()

    dual_relaxed_exp = _run(
        _build_config(
            source_cfg,
            regime_engine="market_regime_framework",
            trend_long_ma_window=160,
            breadth_above_ma_long_window=160,
        )
    )

    legacy_row = _extract_row(variant="V10.2_LEGACY", exp_id=LEGACY_EXP_ID)
    formal_default_row = _extract_row(variant="V10.2_FORMAL_DEFAULT", exp_id=FORMAL_DEFAULT_EXP_ID)
    formal_trend_relaxed_row = _extract_row(
        variant="V10.2_FORMAL_TREND_RELAXED",
        exp_id=FORMAL_TREND_RELAXED_EXP_ID,
    )
    formal_dual_relaxed_row = _extract_row(
        variant="V10.2_FORMAL_TREND_BREADTH_RELAXED",
        exp_id=dual_relaxed_exp,
    )

    default_cross = _cross_counts(LEGACY_EXP_ID, FORMAL_DEFAULT_EXP_ID)
    trend_cross = _cross_counts(LEGACY_EXP_ID, FORMAL_TREND_RELAXED_EXP_ID)
    dual_cross = _cross_counts(LEGACY_EXP_ID, dual_relaxed_exp)

    delta_vs_default = {
        "variant": "DUAL_MINUS_DEFAULT",
        "delta_total_return": (formal_dual_relaxed_row["total_return"] or 0.0) - (formal_default_row["total_return"] or 0.0),
        "delta_cagr": (formal_dual_relaxed_row["cagr"] or 0.0) - (formal_default_row["cagr"] or 0.0),
        "delta_sharpe": (formal_dual_relaxed_row["sharpe"] or 0.0) - (formal_default_row["sharpe"] or 0.0),
        "delta_max_drawdown": (formal_dual_relaxed_row["max_drawdown"] or 0.0) - (formal_default_row["max_drawdown"] or 0.0),
        "delta_trades": int((formal_dual_relaxed_row["trades"] or 0) - (formal_default_row["trades"] or 0)),
        "delta_trade_mode_main_days": int((formal_dual_relaxed_row["trade_mode_main_days"] or 0) - (formal_default_row["trade_mode_main_days"] or 0)),
        "delta_trade_mode_light_days": int((formal_dual_relaxed_row["trade_mode_light_days"] or 0) - (formal_default_row["trade_mode_light_days"] or 0)),
        "delta_trade_mode_notrade_days": int((formal_dual_relaxed_row["trade_mode_notrade_days"] or 0) - (formal_default_row["trade_mode_notrade_days"] or 0)),
        "delta_bull_to_trans_up_days": int(dual_cross["bull_to_trans_up_days"] - default_cross["bull_to_trans_up_days"]),
        "delta_bull_to_trans_up_selected_loss_days": int(dual_cross["bull_to_trans_up_selected_loss_days"] - default_cross["bull_to_trans_up_selected_loss_days"]),
        "delta_bull_to_trans_up_selected_loss_total": int(dual_cross["bull_to_trans_up_selected_loss_total"] - default_cross["bull_to_trans_up_selected_loss_total"]),
    }
    delta_vs_trend = {
        "variant": "DUAL_MINUS_TREND_ONLY",
        "delta_total_return": (formal_dual_relaxed_row["total_return"] or 0.0) - (formal_trend_relaxed_row["total_return"] or 0.0),
        "delta_cagr": (formal_dual_relaxed_row["cagr"] or 0.0) - (formal_trend_relaxed_row["cagr"] or 0.0),
        "delta_sharpe": (formal_dual_relaxed_row["sharpe"] or 0.0) - (formal_trend_relaxed_row["sharpe"] or 0.0),
        "delta_max_drawdown": (formal_dual_relaxed_row["max_drawdown"] or 0.0) - (formal_trend_relaxed_row["max_drawdown"] or 0.0),
        "delta_trades": int((formal_dual_relaxed_row["trades"] or 0) - (formal_trend_relaxed_row["trades"] or 0)),
        "delta_trade_mode_main_days": int((formal_dual_relaxed_row["trade_mode_main_days"] or 0) - (formal_trend_relaxed_row["trade_mode_main_days"] or 0)),
        "delta_trade_mode_light_days": int((formal_dual_relaxed_row["trade_mode_light_days"] or 0) - (formal_trend_relaxed_row["trade_mode_light_days"] or 0)),
        "delta_trade_mode_notrade_days": int((formal_dual_relaxed_row["trade_mode_notrade_days"] or 0) - (formal_trend_relaxed_row["trade_mode_notrade_days"] or 0)),
        "delta_bull_to_trans_up_days": int(dual_cross["bull_to_trans_up_days"] - trend_cross["bull_to_trans_up_days"]),
        "delta_bull_to_trans_up_selected_loss_days": int(dual_cross["bull_to_trans_up_selected_loss_days"] - trend_cross["bull_to_trans_up_selected_loss_days"]),
        "delta_bull_to_trans_up_selected_loss_total": int(dual_cross["bull_to_trans_up_selected_loss_total"] - trend_cross["bull_to_trans_up_selected_loss_total"]),
    }

    summary = {
        "generated_at": datetime.now().isoformat(),
        "comparison_name": "v10_2_regime_trend_breadth_block_relaxed_ab",
        "window": {"start": WINDOW_START, "end": WINDOW_END},
        "assumption": {
            "relaxation": [
                "trend_block.long_ma_window: 200 -> 160",
                "breadth_block.above_ma_long_window: 200 -> 160",
            ],
            "only_changed_knobs": [
                "trend_block.long_ma_window",
                "breadth_block.above_ma_long_window",
            ],
        },
        "variants": [
            legacy_row,
            formal_default_row,
            formal_trend_relaxed_row,
            formal_dual_relaxed_row,
        ],
        "legacy_vs_default_cross": default_cross,
        "legacy_vs_trend_cross": trend_cross,
        "legacy_vs_dual_cross": dual_cross,
        "dual_minus_default": delta_vs_default,
        "dual_minus_trend_only": delta_vs_trend,
    }

    (OPS_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(
        OPS_DIR / "performance_comparison.csv",
        [legacy_row, formal_default_row, formal_trend_relaxed_row, formal_dual_relaxed_row],
    )
    _write_csv(OPS_DIR / "delta_dual_minus_default.csv", [delta_vs_default])
    _write_csv(OPS_DIR / "delta_dual_minus_trend_only.csv", [delta_vs_trend])

    report_lines = [
        "# V10.2 Regime Trend + Breadth Relaxed AB",
        "",
        "## 结论",
        "",
        "- 最小双旋钮：`trend_block.long_ma_window 200 -> 160` + `breadth_block.above_ma_long_window 200 -> 160`。",
        f"- 窗口：`{WINDOW_START} ~ {WINDOW_END}`。",
        "",
        "## 对照",
        "",
        "| Variant | Exp ID | Total Return | CAGR | Sharpe | MaxDD | Trades | Main Days | Light Days | NoTrade Days |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in (legacy_row, formal_default_row, formal_trend_relaxed_row, formal_dual_relaxed_row):
        report_lines.append(
            f"| {row['variant']} | `{row['exp_id']}` | {_fmt_num(row['total_return'])} | {_fmt_num(row['cagr'])} | "
            f"{_fmt_num(row['sharpe'])} | {_fmt_num(row['max_drawdown'])} | {row['trades']} | "
            f"{row['trade_mode_main_days']} | {row['trade_mode_light_days']} | {row['trade_mode_notrade_days']} |"
        )
    report_lines.extend(
        [
            "",
            "## Legacy Cross",
            "",
            f"- `default BULL -> TRANS_UP`: {default_cross['bull_to_trans_up_days']}",
            f"- `trend-only BULL -> TRANS_UP`: {trend_cross['bull_to_trans_up_days']}",
            f"- `dual BULL -> TRANS_UP`: {dual_cross['bull_to_trans_up_days']}",
            f"- `default selected-loss days`: {default_cross['bull_to_trans_up_selected_loss_days']}",
            f"- `trend-only selected-loss days`: {trend_cross['bull_to_trans_up_selected_loss_days']}",
            f"- `dual selected-loss days`: {dual_cross['bull_to_trans_up_selected_loss_days']}",
            f"- `default selected-loss total`: {default_cross['bull_to_trans_up_selected_loss_total']}",
            f"- `trend-only selected-loss total`: {trend_cross['bull_to_trans_up_selected_loss_total']}",
            f"- `dual selected-loss total`: {dual_cross['bull_to_trans_up_selected_loss_total']}",
            "",
            "## Dual - Default",
            "",
            f"- `delta_total_return`: {_fmt_num(delta_vs_default['delta_total_return'])}",
            f"- `delta_cagr`: {_fmt_num(delta_vs_default['delta_cagr'])}",
            f"- `delta_sharpe`: {_fmt_num(delta_vs_default['delta_sharpe'])}",
            f"- `delta_max_drawdown`: {_fmt_num(delta_vs_default['delta_max_drawdown'])}",
            f"- `delta_trades`: {delta_vs_default['delta_trades']}",
            f"- `delta_trade_mode_main_days`: {delta_vs_default['delta_trade_mode_main_days']}",
            f"- `delta_trade_mode_light_days`: {delta_vs_default['delta_trade_mode_light_days']}",
            f"- `delta_trade_mode_notrade_days`: {delta_vs_default['delta_trade_mode_notrade_days']}",
            f"- `delta_bull_to_trans_up_days`: {delta_vs_default['delta_bull_to_trans_up_days']}",
            f"- `delta_bull_to_trans_up_selected_loss_days`: {delta_vs_default['delta_bull_to_trans_up_selected_loss_days']}",
            f"- `delta_bull_to_trans_up_selected_loss_total`: {delta_vs_default['delta_bull_to_trans_up_selected_loss_total']}",
            "",
            "## Dual - Trend Only",
            "",
            f"- `delta_total_return`: {_fmt_num(delta_vs_trend['delta_total_return'])}",
            f"- `delta_cagr`: {_fmt_num(delta_vs_trend['delta_cagr'])}",
            f"- `delta_sharpe`: {_fmt_num(delta_vs_trend['delta_sharpe'])}",
            f"- `delta_max_drawdown`: {_fmt_num(delta_vs_trend['delta_max_drawdown'])}",
            f"- `delta_trades`: {delta_vs_trend['delta_trades']}",
            f"- `delta_trade_mode_main_days`: {delta_vs_trend['delta_trade_mode_main_days']}",
            f"- `delta_trade_mode_light_days`: {delta_vs_trend['delta_trade_mode_light_days']}",
            f"- `delta_trade_mode_notrade_days`: {delta_vs_trend['delta_trade_mode_notrade_days']}",
            f"- `delta_bull_to_trans_up_days`: {delta_vs_trend['delta_bull_to_trans_up_days']}",
            f"- `delta_bull_to_trans_up_selected_loss_days`: {delta_vs_trend['delta_bull_to_trans_up_selected_loss_days']}",
            f"- `delta_bull_to_trans_up_selected_loss_total`: {delta_vs_trend['delta_bull_to_trans_up_selected_loss_total']}",
        ]
    )
    (OPS_DIR / "report.md").write_text("\n".join(report_lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
