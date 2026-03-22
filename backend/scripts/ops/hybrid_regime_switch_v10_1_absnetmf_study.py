from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from backend.api.shared.json_utils import sanitize_json

BASELINE_DIR = REPO / "outputs/experiments/exp_20260320_035043267_e2c1"
ABS_DIR = REPO / "outputs/ops/strict_pit_dynamic_absnetmf_vs_monthly_trend_12m_1226_v2_canonical_tradable_cov_20260319"
OUT_DIR = REPO / "outputs/ops/hybrid_regime_switch_v10_1_absnetmf_1226_20260320"
INITIAL_CAPITAL = 1_000_000.0
ABS_NON_BULL_WEIGHT = 0.5


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _annual_returns(nav_df: pd.DataFrame) -> pd.DataFrame:
    frame = nav_df.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date", "nav"]).sort_values("date")
    rows: list[dict[str, object]] = []
    for year, grp in frame.groupby(frame["date"].dt.year):
        grp = grp.sort_values("date")
        rows.append(
            {
                "year": int(year),
                "start_date": grp["date"].iloc[0].date().isoformat(),
                "end_date": grp["date"].iloc[-1].date().isoformat(),
                "annual_return": float(grp["nav"].iloc[-1] / grp["nav"].iloc[0] - 1.0),
                "end_nav": float(grp["nav"].iloc[-1]),
            }
        )
    return pd.DataFrame(rows)


def _phase_metrics(nav_df: pd.DataFrame) -> pd.DataFrame:
    frame = nav_df.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date", "nav"]).sort_values("date")
    phases = [
        ("2012-2016", "2012-01-04", "2016-12-30"),
        ("2017-2021", "2017-01-03", "2021-12-31"),
        ("2022-2026", "2022-01-04", "2026-03-16"),
    ]
    rows: list[dict[str, object]] = []
    for phase, start_s, end_s in phases:
        part = frame[(frame["date"] >= pd.Timestamp(start_s)) & (frame["date"] <= pd.Timestamp(end_s))].copy()
        if part.empty:
            rows.append({"phase": phase, "total_return": None, "cagr": None, "sharpe": None, "max_drawdown": None, "days": 0})
            continue
        part["daily_return"] = pd.to_numeric(part["daily_return"], errors="coerce").fillna(0.0)
        total_return = float(part["nav"].iloc[-1] / part["nav"].iloc[0] - 1.0)
        years = max(len(part) / 252.0, 1e-9)
        cagr = float((part["nav"].iloc[-1] / part["nav"].iloc[0]) ** (1.0 / years) - 1.0)
        std = float(part["daily_return"].std(ddof=0) or 0.0)
        sharpe = float(part["daily_return"].mean() / std * np.sqrt(252.0)) if std > 0 else 0.0
        maxdd = float(part["drawdown"].min())
        rows.append(
            {
                "phase": phase,
                "total_return": total_return,
                "cagr": cagr,
                "sharpe": sharpe,
                "max_drawdown": maxdd,
                "days": int(len(part)),
            }
        )
    return pd.DataFrame(rows)


def _compute_perf(nav_df: pd.DataFrame) -> dict[str, float]:
    frame = nav_df.copy().sort_values("date")
    daily_ret = pd.to_numeric(frame["daily_return"], errors="coerce").fillna(0.0)
    nav0 = float(frame["nav"].iloc[0])
    nav1 = float(frame["nav"].iloc[-1])
    total_return = float(nav1 / nav0 - 1.0) if nav0 > 0 else 0.0
    years = max(len(frame) / 252.0, 1e-9)
    cagr = float((nav1 / nav0) ** (1.0 / years) - 1.0) if nav0 > 0 and nav1 > 0 else 0.0
    std = float(daily_ret.std(ddof=0) or 0.0)
    sharpe = float(daily_ret.mean() / std * np.sqrt(252.0)) if std > 0 else 0.0
    maxdd = float(frame["drawdown"].min())
    calmar = float(cagr / abs(maxdd)) if maxdd != 0 else 0.0
    return {
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": maxdd,
        "calmar": calmar,
        "effective_execution_start_date": str(frame["date"].iloc[0].date()),
        "effective_observation_days": int(len(frame)),
    }


def _source_compound(frame: pd.DataFrame, source_name: str) -> float:
    rel = np.where(frame["source"].eq(source_name), pd.to_numeric(frame["hybrid_daily_return"], errors="coerce").fillna(0.0), 0.0)
    return float(np.prod(1.0 + rel) - 1.0)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    baseline_daily = pd.read_csv(BASELINE_DIR / "portfolio_daily.csv")
    baseline_daily["date"] = pd.to_datetime(baseline_daily["date"], errors="coerce").dt.normalize()
    baseline_daily["daily_return"] = pd.to_numeric(baseline_daily["daily_return"], errors="coerce").fillna(0.0)
    baseline_daily["trade_mode"] = baseline_daily["trade_mode"].astype(str)
    baseline_daily = baseline_daily[["date", "daily_return", "trade_mode", "market_state", "benchmark_regime_on"]].copy()
    baseline_daily = baseline_daily.rename(columns={"daily_return": "baseline_daily_return"})

    abs_daily = pd.read_csv(ABS_DIR / "abs_portfolio_daily.csv")
    abs_daily["date"] = pd.to_datetime(abs_daily["date"], errors="coerce").dt.normalize()
    abs_daily["nav"] = pd.to_numeric(abs_daily["nav"], errors="coerce")
    abs_daily = abs_daily.sort_values("date").reset_index(drop=True)
    abs_daily["abs_daily_return"] = abs_daily["nav"].pct_change().fillna(0.0)
    abs_daily = abs_daily[["date", "abs_daily_return", "nav", "positions_count"]].copy()
    abs_daily = abs_daily.rename(columns={"nav": "abs_nav", "positions_count": "abs_positions_count"})

    merged = baseline_daily.merge(abs_daily, on="date", how="left")
    merged["abs_daily_return"] = pd.to_numeric(merged["abs_daily_return"], errors="coerce").fillna(0.0)
    merged["abs_nav"] = pd.to_numeric(merged["abs_nav"], errors="coerce")
    merged["abs_positions_count"] = pd.to_numeric(merged["abs_positions_count"], errors="coerce").fillna(0.0)
    merged["non_bull"] = ~merged["trade_mode"].eq("TREND_MAIN")
    merged["source"] = np.where(merged["non_bull"], "ABSNETMF_HALF_CASH", "BASELINE_V10_1")
    merged["hybrid_daily_return"] = np.where(
        merged["non_bull"],
        merged["abs_daily_return"] * float(ABS_NON_BULL_WEIGHT),
        merged["baseline_daily_return"],
    )
    merged["nav"] = float(INITIAL_CAPITAL) * (1.0 + pd.to_numeric(merged["hybrid_daily_return"], errors="coerce").fillna(0.0)).cumprod()
    merged["cash_weight"] = np.where(merged["non_bull"], 0.5, 0.0)
    merged["abs_weight"] = np.where(merged["non_bull"], 0.5, 0.0)
    merged["baseline_weight"] = np.where(merged["non_bull"], 0.0, 1.0)
    merged["peak_nav"] = merged["nav"].cummax()
    merged["drawdown"] = merged["nav"] / merged["peak_nav"] - 1.0
    merged["positions_count"] = np.where(merged["non_bull"], merged["abs_positions_count"] * 0.5, np.nan)
    merged["turnover_pct"] = np.nan

    first_signal_idx = merged["source"].ne(merged["source"].shift(1))
    switch_log = merged.loc[first_signal_idx, ["date", "source", "trade_mode", "market_state", "benchmark_regime_on"]].copy()
    switch_log = switch_log.rename(columns={"source": "new_source"})
    switch_log["previous_source"] = merged["source"].shift(1).loc[first_signal_idx].fillna("INIT")
    switch_log = switch_log[["date", "previous_source", "new_source", "trade_mode", "market_state", "benchmark_regime_on"]].reset_index(drop=True)

    hybrid_nav = merged[
        [
            "date",
            "nav",
            "hybrid_daily_return",
            "drawdown",
            "source",
            "trade_mode",
            "market_state",
            "benchmark_regime_on",
            "baseline_daily_return",
            "abs_daily_return",
            "baseline_weight",
            "abs_weight",
            "cash_weight",
        ]
    ].copy()
    hybrid_nav = hybrid_nav.rename(columns={"hybrid_daily_return": "daily_return"})

    perf = _compute_perf(hybrid_nav)
    annual_returns = _annual_returns(hybrid_nav)
    phase_metrics = _phase_metrics(hybrid_nav)

    baseline_perf = _load_json(BASELINE_DIR / "perf.json")
    abs_summary = _load_json(ABS_DIR / "summary.json")
    abs_perf = dict(abs_summary.get("abs_perf") or {})

    mode_counts = (
        merged.groupby(["trade_mode", "source"], dropna=False)
        .size()
        .reset_index(name="days")
        .sort_values(["days", "trade_mode"], ascending=[False, True])
        .reset_index(drop=True)
    )

    summary = sanitize_json(
        {
            "research_only": True,
            "baseline_exp_id": "exp_20260320_035043267_e2c1",
            "abs_run_id": "strict_pit_dynamic_absnetmf_vs_monthly_trend_12m_1226_v2_canonical_tradable_cov_20260319",
            "baseline_data_role": "v1",
            "abs_data_role": "v2_canonical",
            "window_start": str(hybrid_nav["date"].iloc[0].date()),
            "window_end": str(hybrid_nav["date"].iloc[-1].date()),
            "switch_rule": "use baseline_V10.1 when trade_mode == TREND_MAIN; otherwise use 0.5 * ABSNETMF daily return + 0.5 cash",
            "hybrid_perf": perf,
            "baseline_perf": baseline_perf,
            "abs_perf": {
                "total_return": abs_perf.get("total_return"),
                "cagr": abs_perf.get("cagr"),
                "sharpe": abs_perf.get("sharpe"),
                "max_drawdown": abs_perf.get("max_drawdown"),
                "trades": abs_perf.get("trades"),
                "turnover": abs_perf.get("turnover"),
                "effective_execution_start_date": abs_perf.get("effective_execution_start_date"),
            },
            "days_using_baseline": int(merged["source"].eq("BASELINE_V10_1").sum()),
            "days_using_abs_half_cash": int(merged["source"].eq("ABSNETMF_HALF_CASH").sum()),
            "switch_count": int(max(len(switch_log) - 1, 0)),
            "trade_mode_counts": mode_counts.to_dict(orient="records"),
            "baseline_day_compound_return": _source_compound(merged, "BASELINE_V10_1"),
            "abs_half_day_compound_return": _source_compound(merged, "ABSNETMF_HALF_CASH"),
        }
    )

    report = "\n".join(
        [
            "# V10.1 / ABSNETMF 非牛市切换实验",
            "",
            "## 结论",
            "",
            "这是一个 research-only 的混合壳实验，不是正式可交易策略。",
            "",
            f"- 切换规则：`trade_mode == TREND_MAIN` 用 `baseline_V10.1`；否则用 `0.5 * ABSNETMF + 0.5 cash`",
            f"- 混合结果：`total_return={perf['total_return']:.4f}`，`cagr={perf['cagr']:.4f}`，`sharpe={perf['sharpe']:.4f}`，`max_drawdown={perf['max_drawdown']:.4f}`",
            f"- 基线 `baseline_V10.1`：`total_return={float(baseline_perf.get('total_return', 0.0)):.4f}`，`cagr={float(baseline_perf.get('cagr', 0.0)):.4f}`，`sharpe={float(baseline_perf.get('sharpe', 0.0)):.4f}`，`max_drawdown={float(baseline_perf.get('max_drawdown', 0.0)):.4f}`",
            f"- `ABSNETMF`：`total_return={float(abs_perf.get('total_return', 0.0)):.4f}`，`cagr={float(abs_perf.get('cagr', 0.0)):.4f}`，`sharpe={float(abs_perf.get('sharpe', 0.0)):.4f}`，`max_drawdown={float(abs_perf.get('max_drawdown', 0.0)):.4f}`",
            "",
            "## 事实",
            "",
            f"- `baseline` 数据角色：`v1`",
            f"- `ABSNETMF` 数据角色：`v2_canonical`",
            f"- 使用 `baseline` 天数：`{summary['days_using_baseline']}`",
            f"- 使用 `ABSNETMF_HALF_CASH` 天数：`{summary['days_using_abs_half_cash']}`",
            f"- 切换次数：`{summary['switch_count']}`",
            "",
            "## 风险边界",
            "",
            "- 这条线是按日收益拼接，不是订单级真实共仓回放。",
            "- 切换日没有显式建模双边换仓摩擦。",
            "- 两条底层结果的数据角色不同，所以不能把这轮结果当成同底座公平策略对决。",
        ]
    )

    hybrid_nav.to_csv(OUT_DIR / "hybrid_nav.csv", index=False, encoding="utf-8-sig")
    switch_log.to_csv(OUT_DIR / "switch_log.csv", index=False, encoding="utf-8-sig")
    annual_returns.to_csv(OUT_DIR / "annual_returns.csv", index=False, encoding="utf-8-sig")
    phase_metrics.to_csv(OUT_DIR / "phase_metrics.csv", index=False, encoding="utf-8-sig")
    mode_counts.to_csv(OUT_DIR / "trade_mode_counts.csv", index=False, encoding="utf-8-sig")
    (OUT_DIR / "perf.json").write_text(json.dumps(sanitize_json(perf), ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "report.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
