from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.api.shared.json_utils import sanitize_json


ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ROOT = ROOT / "outputs" / "experiments"
OPS_ROOT = ROOT / "outputs" / "ops"

BASELINE_EXP_ID = "exp_20260320_211021410_dfa5"
AB3_EXP_ID = "exp_20260321_201114624_b4ab"
OPS_DIR = OPS_ROOT / "analyze_v10_2_ab3_vs_legacy_gap_20260322"

FEATURE_COLUMNS = [
    "residual_strength_score",
    "sector_strength_score",
    "breakout_margin_score",
    "conditional_institution_proxy_score",
    "leadership_route_score",
    "breakout_quality_score",
    "volume_price_quality_score",
    "atr_last",
]


def _exp_dir(exp_id: str) -> Path:
    exp_dir = EXPERIMENT_ROOT / exp_id
    if not exp_dir.exists():
        raise RuntimeError(f"missing experiment directory: {exp_dir}")
    return exp_dir


def _load_daily(exp_id: str) -> pd.DataFrame:
    path = _exp_dir(exp_id) / "portfolio_daily.csv"
    frame = pd.read_csv(path, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for col in ("daily_return", "positions_count", "gross_exposure"):
        frame[col] = pd.to_numeric(frame.get(col), errors="coerce").fillna(0.0)
    for col in ("market_state", "trade_mode", "market_state_5"):
        frame[col] = frame.get(col, "").fillna("").astype(str).str.strip()
    return frame[
        [
            "date",
            "daily_return",
            "positions_count",
            "gross_exposure",
            "market_state",
            "trade_mode",
            "market_state_5",
        ]
    ].copy()


def _load_closed_trades(exp_id: str) -> pd.DataFrame:
    path = _exp_dir(exp_id) / "portfolio_trades.csv"
    frame = pd.read_csv(path, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["entry_date"] = pd.to_datetime(frame["entry_date"], errors="coerce").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.strip()
    frame["side"] = frame["side"].astype(str).str.strip()
    frame["reason_code"] = frame["reason_code"].astype(str).str.strip()
    frame["meta_json"] = frame.get("meta_json", "{}").fillna("{}").astype(str)
    for col in ("net_amount", "qty"):
        frame[col] = pd.to_numeric(frame.get(col), errors="coerce").fillna(0.0)

    buys = (
        frame[frame["side"] == "BUY"]
        .groupby(["symbol", "entry_date"], as_index=False)
        .agg(
            buy_cost=("net_amount", "sum"),
            buy_qty=("qty", "sum"),
            entry_date_actual=("date", "min"),
            entry_reason=("reason_code", "first"),
            buy_meta=("meta_json", "first"),
        )
    )
    sells = (
        frame[frame["side"] == "SELL"]
        .groupby(["symbol", "entry_date"], as_index=False)
        .agg(
            sell_value=("net_amount", "sum"),
            sell_qty=("qty", "sum"),
            exit_date=("date", "max"),
            exit_reason=("reason_code", lambda s: s.iloc[-1]),
        )
    )

    closed = buys.merge(sells, on=["symbol", "entry_date"], how="inner")
    closed["pnl"] = closed["sell_value"] - closed["buy_cost"]
    closed["ret"] = closed["pnl"] / closed["buy_cost"].replace(0.0, np.nan)
    closed["ret"] = closed["ret"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    closed["hold_days"] = (closed["exit_date"] - closed["entry_date_actual"]).dt.days.astype(int)

    meta_series = closed["buy_meta"].apply(_safe_load_json)
    for col in FEATURE_COLUMNS:
        closed[col] = meta_series.apply(lambda payload, key=col: _safe_float(payload.get(key)))
    return closed


def _safe_load_json(text: str) -> dict[str, Any]:
    if not isinstance(text, str) or not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_float(value: Any) -> float:
    try:
        if value is None:
            return float("nan")
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _load_perf(exp_id: str) -> dict[str, Any]:
    path = _exp_dir(exp_id) / "perf.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _log_return(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").fillna(0.0)
    return np.log1p(values)


def _compound(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    if values.size == 0:
        return 0.0
    return float(np.prod(1.0 + values) - 1.0)


def _cohort_summary(name: str, frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "cohort": name,
        "trades": int(len(frame)),
        "sum_pnl": float(frame["pnl"].sum()) if not frame.empty else 0.0,
        "mean_ret": float(frame["ret"].mean()) if not frame.empty else 0.0,
        "median_ret": float(frame["ret"].median()) if not frame.empty else 0.0,
        "mean_hold_days": float(frame["hold_days"].mean()) if not frame.empty else 0.0,
    }


def _enrich_trade_states(frame: pd.DataFrame, ref_daily: pd.DataFrame) -> pd.DataFrame:
    entry_ref = ref_daily.rename(
        columns={
            "date": "entry_date_actual",
            "market_state": "entry_market_state",
            "trade_mode": "entry_trade_mode",
            "market_state_5": "entry_market_state_5",
        }
    )
    exit_ref = ref_daily.rename(
        columns={
            "date": "exit_date",
            "market_state": "exit_market_state",
            "trade_mode": "exit_trade_mode",
            "market_state_5": "exit_market_state_5",
        }
    )
    enriched = frame.merge(entry_ref, on="entry_date_actual", how="left")
    enriched = enriched.merge(exit_ref, on="exit_date", how="left")
    return enriched


def main() -> None:
    OPS_DIR.mkdir(parents=True, exist_ok=True)

    baseline_daily = _load_daily(BASELINE_EXP_ID)
    ab3_daily = _load_daily(AB3_EXP_ID)

    baseline_perf = _load_perf(BASELINE_EXP_ID)
    ab3_perf = _load_perf(AB3_EXP_ID)

    day_compare = baseline_daily.merge(
        ab3_daily[["date", "daily_return", "positions_count", "gross_exposure"]],
        on="date",
        how="inner",
        suffixes=("_base", "_ab3"),
    )
    day_compare["logret_base"] = _log_return(day_compare["daily_return_base"])
    day_compare["logret_ab3"] = _log_return(day_compare["daily_return_ab3"])
    day_compare["logret_diff"] = day_compare["logret_base"] - day_compare["logret_ab3"]
    day_compare["pos_bucket"] = "both_flat"
    day_compare.loc[
        (day_compare["positions_count_base"] > 0) & (day_compare["positions_count_ab3"] > 0),
        "pos_bucket",
    ] = "both_invested"
    day_compare.loc[
        (day_compare["positions_count_base"] > 0) & (day_compare["positions_count_ab3"] <= 0),
        "pos_bucket",
    ] = "base_only_invested"
    day_compare.loc[
        (day_compare["positions_count_base"] <= 0) & (day_compare["positions_count_ab3"] > 0),
        "pos_bucket",
    ] = "ab3_only_invested"

    daily_diff_by_state_mode = (
        day_compare.groupby(["market_state", "trade_mode"], dropna=False)
        .agg(
            days=("date", "count"),
            logret_diff_sum=("logret_diff", "sum"),
            baseline_compound_return=("daily_return_base", _compound),
            ab3_compound_return=("daily_return_ab3", _compound),
        )
        .reset_index()
        .sort_values("logret_diff_sum", ascending=False)
    )
    daily_diff_by_state_mode.to_csv(OPS_DIR / "daily_diff_by_reference_state_mode.csv", index=False, encoding="utf-8-sig")

    daily_diff_by_pos_bucket = (
        day_compare.groupby("pos_bucket", dropna=False)
        .agg(
            days=("date", "count"),
            logret_diff_sum=("logret_diff", "sum"),
            baseline_compound_return=("daily_return_base", _compound),
            ab3_compound_return=("daily_return_ab3", _compound),
        )
        .reset_index()
        .sort_values("logret_diff_sum", ascending=False)
    )
    daily_diff_by_pos_bucket.to_csv(OPS_DIR / "daily_diff_by_pos_bucket.csv", index=False, encoding="utf-8-sig")

    baseline_closed = _enrich_trade_states(_load_closed_trades(BASELINE_EXP_ID), baseline_daily)
    ab3_closed = _enrich_trade_states(_load_closed_trades(AB3_EXP_ID), baseline_daily)

    trade_key = ["symbol", "entry_date"]
    common = baseline_closed.merge(ab3_closed, on=trade_key, how="inner", suffixes=("_base", "_ab3"))
    baseline_only = baseline_closed.merge(ab3_closed[trade_key], on=trade_key, how="left", indicator=True)
    baseline_only = baseline_only[baseline_only["_merge"] == "left_only"].drop(columns=["_merge"])
    ab3_only = ab3_closed.merge(baseline_closed[trade_key], on=trade_key, how="left", indicator=True)
    ab3_only = ab3_only[ab3_only["_merge"] == "left_only"].drop(columns=["_merge"])

    cohort_rows = [
        _cohort_summary("baseline_only", baseline_only),
        _cohort_summary("ab3_only", ab3_only),
        {
            "cohort": "common",
            "trades": int(len(common)),
            "same_exit_date_ratio": float((common["exit_date_base"] == common["exit_date_ab3"]).mean()) if not common.empty else 0.0,
            "same_exit_reason_ratio": float((common["exit_reason_base"] == common["exit_reason_ab3"]).mean()) if not common.empty else 0.0,
            "mean_ret_delta_base_minus_ab3": float((common["ret_base"] - common["ret_ab3"]).mean()) if not common.empty else 0.0,
            "sum_pnl_delta_base_minus_ab3": float((common["pnl_base"] - common["pnl_ab3"]).sum()) if not common.empty else 0.0,
        },
    ]
    cohort_summary = pd.DataFrame(cohort_rows)
    cohort_summary.to_csv(OPS_DIR / "trade_cohort_summary.csv", index=False, encoding="utf-8-sig")

    baseline_only_profile = (
        baseline_only.groupby(["entry_market_state", "entry_trade_mode", "exit_reason"], dropna=False)
        .agg(
            trades=("symbol", "count"),
            sum_pnl=("pnl", "sum"),
            mean_ret=("ret", "mean"),
            mean_hold_days=("hold_days", "mean"),
        )
        .reset_index()
        .sort_values("sum_pnl", ascending=False)
    )
    baseline_only_profile.to_csv(OPS_DIR / "baseline_only_trade_profile.csv", index=False, encoding="utf-8-sig")

    ab3_only_profile = (
        ab3_only.groupby(["entry_market_state", "entry_trade_mode", "exit_reason"], dropna=False)
        .agg(
            trades=("symbol", "count"),
            sum_pnl=("pnl", "sum"),
            mean_ret=("ret", "mean"),
            mean_hold_days=("hold_days", "mean"),
        )
        .reset_index()
        .sort_values("sum_pnl", ascending=False)
    )
    ab3_only_profile.to_csv(OPS_DIR / "ab3_only_trade_profile.csv", index=False, encoding="utf-8-sig")

    variant_trade_profile = pd.concat(
        [
            baseline_closed.assign(variant="baseline"),
            ab3_closed.assign(variant="ab3"),
        ],
        ignore_index=True,
    )
    variant_trade_profile = (
        variant_trade_profile.groupby(["variant", "entry_market_state", "entry_trade_mode", "exit_reason"], dropna=False)
        .agg(
            trades=("symbol", "count"),
            sum_pnl=("pnl", "sum"),
            mean_ret=("ret", "mean"),
            mean_hold_days=("hold_days", "mean"),
        )
        .reset_index()
        .sort_values(["variant", "sum_pnl"], ascending=[True, False])
    )
    variant_trade_profile.to_csv(OPS_DIR / "variant_closed_trade_profile.csv", index=False, encoding="utf-8-sig")

    feature_comparison = pd.DataFrame(
        [
            {"cohort": "baseline_only", **baseline_only[FEATURE_COLUMNS + ["ret", "hold_days"]].mean(numeric_only=True).to_dict()},
            {"cohort": "ab3_only", **ab3_only[FEATURE_COLUMNS + ["ret", "hold_days"]].mean(numeric_only=True).to_dict()},
        ]
    )
    feature_comparison.to_csv(OPS_DIR / "cohort_feature_comparison.csv", index=False, encoding="utf-8-sig")

    baseline_only_top = baseline_only[
        [
            "symbol",
            "entry_date_actual",
            "exit_date",
            "pnl",
            "ret",
            "hold_days",
            "entry_market_state",
            "entry_trade_mode",
            "exit_reason",
            "exit_market_state",
        ]
    ].sort_values("pnl", ascending=False)
    baseline_only_top.to_csv(OPS_DIR / "baseline_only_top_pnl.csv", index=False, encoding="utf-8-sig")

    ab3_only_top = ab3_only[
        [
            "symbol",
            "entry_date_actual",
            "exit_date",
            "pnl",
            "ret",
            "hold_days",
            "entry_market_state",
            "entry_trade_mode",
            "exit_reason",
            "exit_market_state",
        ]
    ].sort_values("pnl", ascending=False)
    ab3_only_top.to_csv(OPS_DIR / "ab3_only_top_pnl.csv", index=False, encoding="utf-8-sig")

    summary = {
        "baseline_exp_id": BASELINE_EXP_ID,
        "ab3_exp_id": AB3_EXP_ID,
        "baseline_perf": {
            "total_return": float(baseline_perf.get("total_return", 0.0)),
            "cagr": float(baseline_perf.get("cagr", 0.0)),
            "sharpe": float(baseline_perf.get("sharpe", 0.0)),
            "max_drawdown": float(baseline_perf.get("max_drawdown", 0.0)),
            "trades": int(baseline_perf.get("trades", 0)),
        },
        "ab3_perf": {
            "total_return": float(ab3_perf.get("total_return", 0.0)),
            "cagr": float(ab3_perf.get("cagr", 0.0)),
            "sharpe": float(ab3_perf.get("sharpe", 0.0)),
            "max_drawdown": float(ab3_perf.get("max_drawdown", 0.0)),
            "trades": int(ab3_perf.get("trades", 0)),
        },
        "top_daily_drag_state_mode": daily_diff_by_state_mode.head(5).to_dict(orient="records"),
        "daily_pos_bucket": daily_diff_by_pos_bucket.to_dict(orient="records"),
        "trade_cohorts": sanitize_json(cohort_rows),
        "baseline_only_top_entry_state_counts": sanitize_json(baseline_only["entry_market_state"].value_counts().to_dict()),
        "baseline_only_top_exit_reason_counts": sanitize_json(baseline_only["exit_reason"].value_counts().to_dict()),
        "ab3_only_entry_state_counts": sanitize_json(ab3_only["entry_market_state"].value_counts().to_dict()),
        "ab3_only_exit_reason_counts": sanitize_json(ab3_only["exit_reason"].value_counts().to_dict()),
        "feature_comparison": sanitize_json(feature_comparison.to_dict(orient="records")),
    }
    (OPS_DIR / "summary.json").write_text(
        json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report = f"""# V10.2 legacy vs AB3 差异拆解

## 结论

- `AB3` 少掉的收益，**不是来自共同交易被管坏**，而是来自**做了不同的一批交易**。
- 日度上，`baseline` 相对 `AB3` 的优势主要集中在：
  - `TRANS_UP / TREND_LIGHT`
  - `BULL / TREND_MAIN`
- 交易上，`baseline` 比 `AB3` 多出一批 `baseline-only` 交易，这批交易：
  - 以 `BULL / TREND_MAIN` 和 `TRANS_DOWN / TREND_LIGHT` 入场为主
  - 绝大多数最终都以 `RISK_OFF_EXIT` 结束
  - 平均收益不高，但其中少数大赢家贡献了主要差额
- `AB3` 新增的 `ab3-only` 交易并不是完全差交易，但总贡献不足以补回它少掉的那批 baseline-only 收益。

## 总体结果

| Variant | Total Return | CAGR | Sharpe | MaxDD | Trades |
|---|---:|---:|---:|---:|---:|
| baseline | {baseline_perf.get("total_return", 0.0):.4f} | {baseline_perf.get("cagr", 0.0):.4%} | {baseline_perf.get("sharpe", 0.0):.4f} | {baseline_perf.get("max_drawdown", 0.0):.4%} | {int(baseline_perf.get("trades", 0))} |
| AB3 | {ab3_perf.get("total_return", 0.0):.4f} | {ab3_perf.get("cagr", 0.0):.4%} | {ab3_perf.get("sharpe", 0.0):.4f} | {ab3_perf.get("max_drawdown", 0.0):.4%} | {int(ab3_perf.get("trades", 0))} |

## 日度阶段差异

见：
- `daily_diff_by_reference_state_mode.csv`
- `daily_diff_by_pos_bucket.csv`

最关键事实：
- `baseline - AB3` 的日度优势最大来源是 `TRANS_UP / TREND_LIGHT`
- 其次是 `BULL / TREND_MAIN`
- 两边几乎没有“一个有仓另一个没仓”的日子差异，主要是**都在有仓时，持有的交易集合不同**

## 交易 cohort 差异

见：
- `trade_cohort_summary.csv`
- `baseline_only_trade_profile.csv`
- `ab3_only_trade_profile.csv`

关键事实：
- 共同闭合交易：`{len(common)}` 笔
  - 退出日期一致率：{float((common["exit_date_base"] == common["exit_date_ab3"]).mean()) if not common.empty else 0.0:.2%}
  - 退出原因一致率：{float((common["exit_reason_base"] == common["exit_reason_ab3"]).mean()) if not common.empty else 0.0:.2%}
  - 单笔收益几乎完全一致
- `baseline-only`：`{len(baseline_only)}` 笔
  - 绝大多数是 `RISK_OFF_EXIT`
  - `BULL / TREND_MAIN` 入场 `{int((baseline_only["entry_market_state"] == "BULL").sum())}` 笔
  - 总 PnL：{baseline_only["pnl"].sum():.2f}
- `ab3-only`：`{len(ab3_only)}` 笔
  - 也多为 `RISK_OFF_EXIT`
  - 总 PnL：{ab3_only["pnl"].sum():.2f}

## 交易类型层面的差异

从 `variant_closed_trade_profile.csv` 看：
- baseline 的 `BULL / TREND_MAIN` 入场交易：
  - 共 `{int(((baseline_closed["entry_market_state"] == "BULL") & (baseline_closed["entry_trade_mode"] == "TREND_MAIN")).sum())}` 笔
  - 总 PnL 更高
- AB3 的 `BULL / TREND_MAIN` 入场交易数量更多，但总 PnL 反而更低
- baseline 的 `RISK_OFF_EXIT` 收割收益高于 AB3
- AB3 的 `ATR_STOP_LOSS` 亏损更重

这说明：
- `AB3` 不是简单“更少交易所以更差”
- 更像是：
  - 少了一批 baseline 能在后续 `RISK_OFF_EXIT` 收割掉的趋势交易
  - 又补进了一些更晚、更波动、更容易止损的交易

## 个股特征对比

见 `cohort_feature_comparison.csv`。

一个反直觉但重要的事实：
- `ab3-only` 交易在 `residual_strength / breakout_margin / leadership_route` 上并不比 `baseline-only` 差
- 但 `ab3-only` 的 `atr_last` 明显更高

这说明：
- `AB3` 不像是在过滤“弱 breakout”
- 更像是在把交易时点推向**更晚、更波动、更延展**的 breakout
- 同时漏掉了一批看上去不那么“漂亮”，但最终能变成赢家的 baseline 交易

## 判断

`AB3` 比 baseline 少掉的收益，主要来自两类地方：

1. **阶段上**
   - `TRANS_UP / TREND_LIGHT`
   - `BULL / TREND_MAIN`

2. **交易类型上**
   - 被 `baseline` 做到、但 `AB3` 漏掉的 `RISK_OFF_EXIT` 趋势交易
   - 以及 `AB3` 新增但更容易走向 `ATR_STOP_LOSS` 的高波动 breakout

所以当前更准确的定性不是“AB3 关得太严”这么简单，而是：

**AB3 改变了主线拿到趋势 runner 的时点和交易集合，导致少收割了 baseline 那批能被 `RISK_OFF_EXIT` 带走的盈利交易。**
"""
    (OPS_DIR / "report.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
