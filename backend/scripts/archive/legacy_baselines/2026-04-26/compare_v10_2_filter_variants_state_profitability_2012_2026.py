from __future__ import annotations

import copy
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.api.shared.json_utils import sanitize_json
from backend.core.tools.experiment_runtime_access import run_experiment_sync


ROOT = Path(__file__).resolve().parents[3]
OPS_ROOT = ROOT / "outputs" / "ops"
EXPERIMENT_ROOT = ROOT / "outputs" / "experiments"

SOURCE_EXP_ID = "exp_20260320_063727806_260c"
LEGACY_EXP_ID = "exp_20260320_195828116_f50f"
WEEKLY_EXP_ID = "exp_20260320_200252333_ffdd"
ASSET_SCOPE = "cn_a_equity"
OPS_DIR = OPS_ROOT / "compare_v10_2_filter_variants_state_profitability_2012_2026_20260321"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid json root: {path}")
    return payload


def _source_config() -> dict[str, Any]:
    return _load_json(EXPERIMENT_ROOT / SOURCE_EXP_ID / "input_config.json")


def _build_no_filter_config(source_cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = copy.deepcopy(source_cfg)
    universe = dict(cfg.get("universe") or {})
    universe["membership_mode"] = "PIT_DYNAMIC"
    cfg["universe"] = universe

    data_source = dict(cfg.get("data_source") or {})
    data_source["data_role"] = "v2_canonical"
    cfg["data_source"] = data_source

    benchmark_regime = dict(cfg.get("benchmark_regime") or {})
    benchmark_regime["enabled"] = False
    cfg["benchmark_regime"] = benchmark_regime

    position_risk = dict(cfg.get("position_risk") or {})
    market_filter = dict(position_risk.get("market_filter") or {})
    market_filter["enabled"] = False
    position_risk["market_filter"] = market_filter
    cfg["position_risk"] = position_risk

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
    universe = run_meta.get("universe") if isinstance(run_meta.get("universe"), dict) else {}
    return {
        "variant": variant,
        "exp_id": exp_id,
        "window_start": data.get("start"),
        "window_end": data.get("end"),
        "data_role": consistency.get("data_role") or data.get("data_role") or "v1",
        "regime_engine": consistency.get("regime_engine") or "ma200_legacy",
        "membership_mode": universe.get("membership_mode"),
        "historical_membership_dynamic": universe.get("historical_membership_dynamic"),
        "total_return": perf.get("total_return"),
        "cagr": perf.get("cagr"),
        "sharpe": perf.get("sharpe"),
        "max_drawdown": perf.get("max_drawdown"),
        "trades": perf.get("trades"),
        "turnover": perf.get("turnover"),
        "effective_execution_start_date": perf.get("effective_execution_start_date"),
        "trade_mode_main_days": counters.get("trade_mode_main_days"),
        "trade_mode_light_days": counters.get("trade_mode_light_days"),
        "trade_mode_notrade_days": counters.get("trade_mode_notrade_days"),
        "market_state_trans_up_days": counters.get("market_state_trans_up_days"),
        "market_state_trans_down_days": counters.get("market_state_trans_down_days"),
    }


def _load_portfolio_daily(exp_id: str) -> pd.DataFrame:
    path = _exp_dir(exp_id) / "portfolio_daily.csv"
    frame = pd.read_csv(path, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["daily_return"] = pd.to_numeric(frame["daily_return"], errors="coerce").fillna(0.0)
    frame["nav"] = pd.to_numeric(frame["nav"], errors="coerce")
    for col in ("market_state", "trade_mode", "market_state_5", "regime_engine"):
        if col in frame.columns:
            frame[col] = frame[col].astype(str).str.strip()
    return frame


def _compound_return(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    values = pd.to_numeric(returns, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    return float(np.prod(1.0 + values) - 1.0)


def _annualized_sharpe(returns: pd.Series) -> float:
    values = pd.to_numeric(returns, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    if values.size == 0:
        return 0.0
    std = float(values.std(ddof=0))
    if std <= 0:
        return 0.0
    return float(values.mean() / std * np.sqrt(252.0))


def _reference_state_counts(reference_df: pd.DataFrame, *, group_col: str, group_name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for state, grp in reference_df.groupby(group_col, dropna=False):
        rows.append(
            {
                "group_name": group_name,
                "state": str(state),
                "days": int(len(grp)),
                "ratio": float(len(grp) / len(reference_df)) if len(reference_df) else 0.0,
            }
        )
    rows.sort(key=lambda row: (-row["days"], row["state"]))
    return rows


def _profitability_by_reference_state(
    reference_df: pd.DataFrame,
    variant_frames: dict[str, pd.DataFrame],
    *,
    group_col: str,
    group_name: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    ref_cols = ["date", group_col]
    ref = reference_df[ref_cols].copy()
    for variant, frame in variant_frames.items():
        merged = ref.merge(frame[["date", "daily_return", "nav"]], on="date", how="left")
        merged["daily_return"] = pd.to_numeric(merged["daily_return"], errors="coerce").fillna(0.0)
        for state, grp in merged.groupby(group_col, dropna=False):
            rows.append(
                {
                    "variant": variant,
                    "group_name": group_name,
                    "state": str(state),
                    "days": int(len(grp)),
                    "compounded_return": _compound_return(grp["daily_return"]),
                    "avg_daily_return": float(grp["daily_return"].mean()) if len(grp) else 0.0,
                    "daily_sharpe": _annualized_sharpe(grp["daily_return"]),
                    "hit_rate": float((grp["daily_return"] > 0).mean()) if len(grp) else 0.0,
                    "avg_nav": float(pd.to_numeric(grp["nav"], errors="coerce").dropna().mean()) if len(grp) else np.nan,
                }
            )
    rows.sort(key=lambda row: (row["group_name"], row["state"], row["variant"]))
    return rows


def _delta_rows(comparison_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    base_map = {row["variant"]: row for row in comparison_rows}
    legacy = base_map["V10.2_LEGACY"]
    rows: list[dict[str, Any]] = []
    for variant in ("V10.2_WEEKLY_FIVE_STATE", "V10.2_NO_MARKET_FILTER"):
        row = base_map[variant]
        rows.append(
            {
                "variant": variant,
                "delta_total_return_vs_legacy": float((row["total_return"] or 0.0) - (legacy["total_return"] or 0.0)),
                "delta_cagr_vs_legacy": float((row["cagr"] or 0.0) - (legacy["cagr"] or 0.0)),
                "delta_sharpe_vs_legacy": float((row["sharpe"] or 0.0) - (legacy["sharpe"] or 0.0)),
                "delta_max_drawdown_vs_legacy": float((row["max_drawdown"] or 0.0) - (legacy["max_drawdown"] or 0.0)),
                "delta_trades_vs_legacy": int((row["trades"] or 0) - (legacy["trades"] or 0)),
            }
        )
    return rows


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


def _build_report(
    *,
    comparison_rows: list[dict[str, Any]],
    state_rows: list[dict[str, Any]],
    mode_rows: list[dict[str, Any]],
    counts_rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> str:
    performance_map = {row["variant"]: row for row in comparison_rows}
    legacy = performance_map["V10.2_LEGACY"]
    weekly = performance_map["V10.2_WEEKLY_FIVE_STATE"]
    no_filter = performance_map["V10.2_NO_MARKET_FILTER"]

    def top_states(rows: list[dict[str, Any]], variant: str, group_name: str) -> list[dict[str, Any]]:
        subset = [row for row in rows if row["variant"] == variant and row["group_name"] == group_name]
        subset.sort(key=lambda row: row["compounded_return"], reverse=True)
        return subset[:2]

    legacy_top_state = top_states(state_rows, "V10.2_LEGACY", "reference_market_state")
    no_filter_top_state = top_states(state_rows, "V10.2_NO_MARKET_FILTER", "reference_market_state")
    weekly_top_mode = top_states(mode_rows, "V10.2_WEEKLY_FIVE_STATE", "reference_trade_mode")

    lines = [
        "# V10.2 三种市场过滤口径：状态盈利能力对照",
        "",
        "## 结论",
        "",
        "- 这轮新增了 `V10.2_NO_MARKET_FILTER`，并与 `V10.2_LEGACY / V10.2_WEEKLY_FIVE_STATE` 做同口径对照。",
        "- 为了可比性，市场状态分段统一使用 `V10.2 legacy` 的 `market_state / trade_mode` 作为参考状态序列。",
        "- 也就是说，这里的“不同市场状态下盈利能力”是三条线在同一套参考市场环境上的表现，不是各自内部状态标签互相混比。",
        "",
        "## 总体对照",
        "",
        "| Variant | Exp ID | Total Return | CAGR | Sharpe | MaxDD | Trades |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in comparison_rows:
        lines.append(
            f"| {row['variant']} | `{row['exp_id']}` | {_fmt_num(row['total_return'])} | {_fmt_num(row['cagr'])} | {_fmt_num(row['sharpe'])} | {_fmt_num(row['max_drawdown'])} | {int(row['trades'] or 0)} |"
        )

    lines += [
        "",
        "## 参考状态样本分布",
        "",
        "| 参考分组 | 状态 | 天数 | 占比 |",
        "|---|---|---:|---:|",
    ]
    for row in counts_rows:
        lines.append(f"| {row['group_name']} | {row['state']} | {row['days']} | {_fmt_num(row['ratio'])} |")

    lines += [
        "",
        "## 重点观察",
        "",
        f"- `V10.2_LEGACY` 最强的参考市场状态通常落在：{', '.join(f'{row['state']}({_fmt_num(row['compounded_return'])})' for row in legacy_top_state) if legacy_top_state else 'n/a'}。",
        f"- `V10.2_NO_MARKET_FILTER` 最强的参考市场状态通常落在：{', '.join(f'{row['state']}({_fmt_num(row['compounded_return'])})' for row in no_filter_top_state) if no_filter_top_state else 'n/a'}。",
        f"- `V10.2_WEEKLY_FIVE_STATE` 在参考交易模式里相对还能工作的阶段主要是：{', '.join(f'{row['state']}({_fmt_num(row['compounded_return'])})' for row in weekly_top_mode) if weekly_top_mode else 'n/a'}。",
        "",
        "## 边界",
        "",
        "- `V10.2_NO_MARKET_FILTER` 自己的日度状态天然会接近全 `BULL/TREND_MAIN`，所以这里不使用它自己的状态做分段。",
        "- 这里的状态盈利能力比较，是研究分析口径，不是正式主线切换建议。",
        "",
        "## 产物",
        "",
        "- `performance_comparison.csv`：总体绩效对照",
        "- `profitability_by_reference_market_state.csv`：按 legacy 参考市场状态拆分",
        "- `profitability_by_reference_trade_mode.csv`：按 legacy 参考交易模式拆分",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    OPS_DIR.mkdir(parents=True, exist_ok=True)
    source_cfg = _source_config()
    no_filter_exp = _run(_build_no_filter_config(source_cfg))

    comparison_rows = [
        _extract_perf_row(variant="V10.2_LEGACY", exp_id=LEGACY_EXP_ID),
        _extract_perf_row(variant="V10.2_WEEKLY_FIVE_STATE", exp_id=WEEKLY_EXP_ID),
        _extract_perf_row(variant="V10.2_NO_MARKET_FILTER", exp_id=no_filter_exp),
    ]

    legacy_daily = _load_portfolio_daily(LEGACY_EXP_ID)
    weekly_daily = _load_portfolio_daily(WEEKLY_EXP_ID)
    no_filter_daily = _load_portfolio_daily(no_filter_exp)
    variant_frames = {
        "V10.2_LEGACY": legacy_daily,
        "V10.2_WEEKLY_FIVE_STATE": weekly_daily,
        "V10.2_NO_MARKET_FILTER": no_filter_daily,
    }

    reference_counts = _reference_state_counts(legacy_daily, group_col="market_state", group_name="reference_market_state")
    reference_counts += _reference_state_counts(legacy_daily, group_col="trade_mode", group_name="reference_trade_mode")

    state_rows = _profitability_by_reference_state(
        legacy_daily,
        variant_frames,
        group_col="market_state",
        group_name="reference_market_state",
    )
    mode_rows = _profitability_by_reference_state(
        legacy_daily,
        variant_frames,
        group_col="trade_mode",
        group_name="reference_trade_mode",
    )
    delta_rows = _delta_rows(comparison_rows)

    summary = sanitize_json(
        {
            "generated_at": datetime.now().isoformat(),
            "comparison_name": "v10_2_filter_variants_state_profitability",
            "source_exp_id": SOURCE_EXP_ID,
            "legacy_exp_id": LEGACY_EXP_ID,
            "weekly_exp_id": WEEKLY_EXP_ID,
            "no_filter_exp_id": no_filter_exp,
            "window": {
                "start": source_cfg.get("universe", {}).get("start"),
                "end": source_cfg.get("universe", {}).get("end"),
            },
            "notes": [
                "This analysis uses V10.2 legacy market_state / trade_mode as the common reference state series.",
                "No-filter variant disables benchmark_regime and position_risk.market_filter, but keeps stock signal logic unchanged.",
                "State-level compounded returns are grouped by dates within a state and are not additive across states.",
            ],
            "variants": comparison_rows,
            "deltas_vs_legacy": delta_rows,
            "reference_state_counts": reference_counts,
        }
    )

    _write_csv(OPS_DIR / "performance_comparison.csv", comparison_rows)
    _write_csv(OPS_DIR / "profitability_by_reference_market_state.csv", state_rows)
    _write_csv(OPS_DIR / "profitability_by_reference_trade_mode.csv", mode_rows)
    _write_csv(OPS_DIR / "reference_state_counts.csv", reference_counts)
    _write_csv(OPS_DIR / "delta_vs_legacy.csv", delta_rows)
    (OPS_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OPS_DIR / "report.md").write_text(
        _build_report(
            comparison_rows=comparison_rows,
            state_rows=state_rows,
            mode_rows=mode_rows,
            counts_rows=reference_counts,
            summary=summary,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
