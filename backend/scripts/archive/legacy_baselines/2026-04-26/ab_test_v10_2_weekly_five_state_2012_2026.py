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
ASSET_SCOPE = "cn_a_equity"
OPS_DIR = OPS_ROOT / "ab_test_v10_2_weekly_five_state_2012_2026_20260321"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid json root: {path}")
    return payload


def _source_config() -> dict[str, Any]:
    return _load_json(EXPERIMENT_ROOT / SOURCE_EXP_ID / "input_config.json")


def _build_config(source_cfg: dict[str, Any], *, regime_engine: str) -> dict[str, Any]:
    cfg = copy.deepcopy(source_cfg)
    universe = dict(cfg.get("universe") or {})
    universe["membership_mode"] = "PIT_DYNAMIC"
    cfg["universe"] = universe
    data_source = dict(cfg.get("data_source") or {})
    data_source["data_role"] = "v2_canonical"
    cfg["data_source"] = data_source
    if regime_engine == "weekly_five_state":
        cfg["regime_engine"] = {
            "engine": "weekly_five_state",
            "benchmark": "000001.SH",
            "weekly_five_state": {
                "benchmark": "000001.SH",
                "ma_window": 120,
                "ma_slope_lookback": 20,
                "ret_short_window": 60,
                "ret_long_window": 120,
                "adx_window": 20,
                "weekly_rule": "W-FRI",
                "upgrade_confirm_weeks": 2,
                "downgrade_confirm_weeks": 1,
                "turn_weak_budget": 0.15,
            },
            "fallback": {
                "on_feature_unavailable": "ma200_legacy",
                "required_blocks": [],
                "emit_feature_availability": True,
            },
        }
    else:
        cfg["regime_engine"] = {"engine": "ma200_legacy"}
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


def _extract_perf_row(*, variant: str, exp_id: str) -> dict[str, Any]:
    exp_dir = _exp_dir(exp_id)
    perf = _load_json(exp_dir / "perf.json")
    run_meta = _load_json(exp_dir / "run_meta.json")
    data = run_meta.get("data") if isinstance(run_meta.get("data"), dict) else {}
    consistency = run_meta.get("report_consistency") if isinstance(run_meta.get("report_consistency"), dict) else {}
    counters = run_meta.get("counters") if isinstance(run_meta.get("counters"), dict) else {}
    return {
        "variant": variant,
        "exp_id": exp_id,
        "window_start": data.get("start"),
        "window_end": data.get("end"),
        "data_role": consistency.get("data_role") or data.get("data_role") or "v1",
        "regime_engine": consistency.get("regime_engine") or "ma200_legacy",
        "membership_mode": (run_meta.get("universe") or {}).get("membership_mode"),
        "historical_membership_dynamic": (run_meta.get("universe") or {}).get("historical_membership_dynamic"),
        "total_return": perf.get("total_return"),
        "cagr": perf.get("cagr"),
        "sharpe": perf.get("sharpe"),
        "max_drawdown": perf.get("max_drawdown"),
        "trades": perf.get("trades"),
        "turnover": perf.get("turnover"),
        "effective_execution_start_date": perf.get("effective_execution_start_date"),
        "market_filter_bull_days": counters.get("market_filter_bull_days"),
        "market_filter_bear_days": counters.get("market_filter_bear_days"),
        "market_state_trans_up_days": counters.get("market_state_trans_up_days"),
        "market_state_trans_down_days": counters.get("market_state_trans_down_days"),
        "trade_mode_main_days": counters.get("trade_mode_main_days"),
        "trade_mode_light_days": counters.get("trade_mode_light_days"),
        "trade_mode_notrade_days": counters.get("trade_mode_notrade_days"),
    }


def _load_portfolio_daily(exp_id: str) -> pd.DataFrame:
    path = _exp_dir(exp_id) / "portfolio_daily.csv"
    frame = pd.read_csv(path, encoding="utf-8-sig")
    frame["date"] = frame["date"].astype(str)
    return frame


def _state_distribution(frame: pd.DataFrame, *, variant: str) -> list[dict[str, Any]]:
    state_col = "market_state_5" if "market_state_5" in frame.columns else "market_state"
    if state_col not in frame.columns:
        return []
    states = frame[state_col].astype(str).str.strip().replace({"": "UNKNOWN"})
    weekly_flags = frame["weekly_observation_flag"] if "weekly_observation_flag" in frame.columns else 0
    out: list[dict[str, Any]] = []
    total = int(len(frame))
    for state, count in states.value_counts(dropna=False).items():
        mask = states == state
        out.append(
            {
                "variant": variant,
                "state": state,
                "days": int(count),
                "ratio": float(count / total) if total else 0.0,
                "weekly_observation_days": int(pd.to_numeric(weekly_flags[mask], errors="coerce").fillna(0).astype(int).sum()),
            }
        )
    return out


def _top_divergence_days(legacy_frame: pd.DataFrame, weekly_frame: pd.DataFrame) -> list[dict[str, Any]]:
    left = legacy_frame[["date", "nav", "market_state", "trade_mode"]].rename(
        columns={"nav": "legacy_nav", "market_state": "legacy_state", "trade_mode": "legacy_trade_mode"}
    )
    right_columns = ["date", "nav"]
    if "market_state_5" in weekly_frame.columns:
        right_columns.append("market_state_5")
    if "market_state_smoothed" in weekly_frame.columns:
        right_columns.append("market_state_smoothed")
    if "trade_mode" in weekly_frame.columns:
        right_columns.append("trade_mode")
    right = weekly_frame[right_columns].rename(
        columns={
            "nav": "weekly_nav",
            "market_state_5": "weekly_state_5",
            "market_state_smoothed": "weekly_state_smoothed",
            "trade_mode": "weekly_trade_mode",
        }
    )
    merged = left.merge(right, on="date", how="inner")
    merged["nav_gap"] = pd.to_numeric(merged["weekly_nav"], errors="coerce") - pd.to_numeric(merged["legacy_nav"], errors="coerce")
    merged["nav_gap_abs"] = merged["nav_gap"].abs()
    merged = merged.sort_values(["nav_gap_abs", "date"], ascending=[False, True]).head(20)
    return merged.to_dict(orient="records")


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

    legacy_exp = _run(_build_config(source_cfg, regime_engine="ma200_legacy"))
    weekly_exp = _run(_build_config(source_cfg, regime_engine="weekly_five_state"))

    legacy_row = _extract_perf_row(variant="V10.2_LEGACY", exp_id=legacy_exp)
    weekly_row = _extract_perf_row(variant="V10.2_WEEKLY_FIVE_STATE", exp_id=weekly_exp)
    comparison_rows = [legacy_row, weekly_row]
    delta = {
        "legacy_exp_id": legacy_exp,
        "weekly_exp_id": weekly_exp,
        "delta_total_return": float((weekly_row["total_return"] or 0.0) - (legacy_row["total_return"] or 0.0)),
        "delta_cagr": float((weekly_row["cagr"] or 0.0) - (legacy_row["cagr"] or 0.0)),
        "delta_sharpe": float((weekly_row["sharpe"] or 0.0) - (legacy_row["sharpe"] or 0.0)),
        "delta_max_drawdown": float((weekly_row["max_drawdown"] or 0.0) - (legacy_row["max_drawdown"] or 0.0)),
        "delta_trades": int((weekly_row["trades"] or 0) - (legacy_row["trades"] or 0)),
        "delta_turnover": float((weekly_row["turnover"] or 0.0) - (legacy_row["turnover"] or 0.0)),
    }

    legacy_daily = _load_portfolio_daily(legacy_exp)
    weekly_daily = _load_portfolio_daily(weekly_exp)
    state_rows = _state_distribution(legacy_daily, variant="V10.2_LEGACY") + _state_distribution(
        weekly_daily, variant="V10.2_WEEKLY_FIVE_STATE"
    )
    divergence_rows = _top_divergence_days(legacy_daily, weekly_daily)

    summary = {
        "generated_at": datetime.now().isoformat(),
        "comparison_name": "v10_2_weekly_five_state_minimal_ab",
        "source_exp_id": SOURCE_EXP_ID,
        "window": {
            "start": source_cfg.get("universe", {}).get("start"),
            "end": source_cfg.get("universe", {}).get("end"),
        },
        "variants": comparison_rows,
        "delta": delta,
        "notes": [
            "This is a minimal AB on top of baseline_V10.2 shell.",
            "The only intended diff is regime_engine.",
            "Weekly engine keeps stock signal logic unchanged and only changes market filter / risk budget path.",
        ],
    }

    _write_csv(OPS_DIR / "performance_comparison.csv", comparison_rows)
    _write_csv(OPS_DIR / "state_distribution.csv", state_rows)
    _write_csv(OPS_DIR / "key_divergence_days.csv", divergence_rows)
    _write_csv(OPS_DIR / "delta.csv", [delta])
    (OPS_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    report_lines = [
        "# Baseline V10.2: Legacy vs Weekly Five-State Minimal AB",
        "",
        "## 结论",
        "",
        "- 这是一轮只改 `regime_engine` 的最小 A/B。",
        "- `weekly_five_state` 不改个股 `40日突破 + 40日残差排序`，只改市场状态与风险预算链。",
        "",
        "## 对照表",
        "",
        "| Variant | Exp ID | Data Role | Regime Engine | Total Return | CAGR | Sharpe | MaxDD | Trades | Turnover |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in comparison_rows:
        report_lines.append(
            f"| {row['variant']} | `{row['exp_id']}` | `{row['data_role']}` | `{row['regime_engine']}` | "
            f"{_fmt_num(row['total_return'])} | {_fmt_num(row['cagr'])} | {_fmt_num(row['sharpe'])} | "
            f"{_fmt_num(row['max_drawdown'])} | {row['trades']} | {_fmt_num(row['turnover'], 6)} |"
        )

    report_lines.extend(
        [
            "",
            "## Weekly - Legacy",
            "",
            f"- `total_return`: {_fmt_num(delta['delta_total_return'])}",
            f"- `cagr`: {_fmt_num(delta['delta_cagr'])}",
            f"- `sharpe`: {_fmt_num(delta['delta_sharpe'])}",
            f"- `max_drawdown`: {_fmt_num(delta['delta_max_drawdown'])}",
            f"- `trades`: {delta['delta_trades']}",
            f"- `turnover`: {_fmt_num(delta['delta_turnover'], 6)}",
            "",
            "## 状态分布与关键分叉",
            "",
            "- 详细状态分布见 `state_distribution.csv`。",
            "- 最大净值分叉日见 `key_divergence_days.csv`。",
        ]
    )
    (OPS_DIR / "report.md").write_text("\n".join(report_lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
