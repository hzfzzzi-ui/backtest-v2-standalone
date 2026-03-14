from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(r"C:\Users\hzfzzzi\openclaw\backtest_V2_standalone")
OUTPUT_DIR = ROOT / "outputs" / "ops" / "v10_attack_phase_attribution_20260313"

EXPERIMENTS = {
    "exp_20260313_035110024_32ed": ROOT / "outputs" / "experiments" / "exp_20260313_035110024_32ed",
    "exp_20260312_034933994_f811": ROOT / "outputs" / "experiments" / "exp_20260312_034933994_f811",
}


@dataclass(frozen=True)
class Phase:
    phase_key: str
    phase_label: str
    experiment_id: str
    start: str
    end: str


PHASES = [
    Phase(
        phase_key="phase_2009_rebound_bull",
        phase_label="2009反弹牛",
        experiment_id="exp_20260313_035110024_32ed",
        start="2009-01-05",
        end="2009-12-31",
    ),
    Phase(
        phase_key="phase_2014_2015_leverage_bull",
        phase_label="2014-2015杠杆牛",
        experiment_id="exp_20260313_035110024_32ed",
        start="2014-01-02",
        end="2015-06-12",
    ),
    Phase(
        phase_key="phase_2019_2021_core_asset_bull",
        phase_label="2019-2021核心资产牛",
        experiment_id="exp_20260312_034933994_f811",
        start="2019-01-02",
        end="2021-02-18",
    ),
    Phase(
        phase_key="phase_2024_2026_policy_recovery",
        phase_label="2024-2026政策修复进攻段",
        experiment_id="exp_20260312_034933994_f811",
        start="2024-02-06",
        end="2026-02-27",
    ),
]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _to_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series
    return series.astype(str).str.lower().map({"true": True, "false": False}).fillna(False)


def _parse_meta(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def _load_experiment(exp_id: str) -> dict[str, Any]:
    exp_dir = EXPERIMENTS[exp_id]
    daily = pd.read_csv(exp_dir / "portfolio_daily.csv", parse_dates=["date"])
    trades = pd.read_csv(exp_dir / "portfolio_trades.csv", parse_dates=["date", "entry_date"])
    perf = _read_json(exp_dir / "perf.json")

    daily = daily.sort_values("date").reset_index(drop=True)
    trades = trades.sort_values("date").reset_index(drop=True)
    daily["benchmark_regime_on"] = _to_bool(daily["benchmark_regime_on"])
    daily["strong_risk_on"] = pd.to_numeric(daily["strong_risk_on"], errors="coerce").fillna(0.0)

    date_to_idx = {ts.normalize(): idx for idx, ts in enumerate(daily["date"])}
    return {
        "exp_dir": exp_dir,
        "daily": daily,
        "trades": trades,
        "perf": perf,
        "date_to_idx": date_to_idx,
    }


def _monthly_returns(full_daily: pd.DataFrame, phase_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if phase_daily.empty:
        return pd.DataFrame(rows)

    for month_period, month_df in phase_daily.groupby(phase_daily["date"].dt.to_period("M")):
        month_df = month_df.sort_values("date")
        start_date = month_df["date"].iloc[0]
        end_date = month_df["date"].iloc[-1]
        prev_full = full_daily.loc[full_daily["date"] < start_date, "nav"]
        base_nav = prev_full.iloc[-1] if not prev_full.empty else month_df["nav"].iloc[0]
        end_nav = month_df["nav"].iloc[-1]
        rows.append(
            {
                "month": str(month_period),
                "start_date": start_date.date().isoformat(),
                "end_date": end_date.date().isoformat(),
                "month_return": float(end_nav / base_nav - 1.0) if base_nav else 0.0,
                "avg_gross_exposure": float(month_df["gross_exposure"].mean()),
                "avg_positions_count": float(month_df["positions_count_end_of_day"].mean()),
                "zero_exposure_rate": float((month_df["gross_exposure"] <= 1e-9).mean()),
            }
        )
    return pd.DataFrame(rows)


def _trade_holding_bars(row: pd.Series, date_to_idx: dict[pd.Timestamp, int]) -> float | None:
    meta = row["meta"]
    bars = meta.get("bars_since_entry")
    if bars is not None:
        try:
            return float(bars)
        except (TypeError, ValueError):
            pass
    sell_date = row["date"].normalize() if pd.notna(row["date"]) else None
    entry_date = row["entry_date"].normalize() if pd.notna(row["entry_date"]) else None
    if sell_date is None or entry_date is None:
        return None
    if sell_date not in date_to_idx or entry_date not in date_to_idx:
        return None
    return float(date_to_idx[sell_date] - date_to_idx[entry_date])


def _prepare_trades(trades: pd.DataFrame, date_to_idx: dict[pd.Timestamp, int]) -> pd.DataFrame:
    trades = trades.copy()
    trades["meta"] = trades["meta_json"].map(_parse_meta)
    trades["qty"] = pd.to_numeric(trades["qty"], errors="coerce")
    trades["fill_price"] = pd.to_numeric(trades["fill_price"], errors="coerce")
    trades["net_amount"] = pd.to_numeric(trades["net_amount"], errors="coerce")
    trades["avg_cost"] = trades["meta"].map(lambda m: pd.to_numeric(m.get("avg_cost"), errors="coerce"))
    trades["pnl_pct"] = trades["meta"].map(lambda m: pd.to_numeric(m.get("pnl_pct"), errors="coerce"))
    trades["holding_bars"] = trades.apply(lambda row: _trade_holding_bars(row, date_to_idx), axis=1)
    trades["realized_pnl"] = pd.NA
    cost_mask = trades["avg_cost"].notna() & trades["qty"].notna() & trades["net_amount"].notna()
    trades.loc[cost_mask, "realized_pnl"] = (
        trades.loc[cost_mask, "net_amount"] - trades.loc[cost_mask, "avg_cost"] * trades.loc[cost_mask, "qty"]
    )
    fallback_mask = trades["realized_pnl"].isna() & trades["pnl_pct"].notna() & trades["avg_cost"].notna() & trades["qty"].notna()
    trades.loc[fallback_mask, "realized_pnl"] = trades.loc[fallback_mask, "pnl_pct"] * trades.loc[fallback_mask, "avg_cost"] * trades.loc[fallback_mask, "qty"]
    return trades


def _winner_concentration(sells: pd.DataFrame) -> dict[str, Any]:
    pos = sells.loc[sells["realized_pnl"].fillna(0.0) > 0].groupby("symbol", as_index=True)["realized_pnl"].sum().sort_values(ascending=False)
    if pos.empty:
        return {
            "positive_symbol_count": 0,
            "positive_realized_pnl": 0.0,
            "winner_top1_share": 0.0,
            "winner_top3_share": 0.0,
            "winner_top5_share": 0.0,
            "winner_top10_share": 0.0,
        }
    total = float(pos.sum())
    return {
        "positive_symbol_count": int(pos.shape[0]),
        "positive_realized_pnl": total,
        "winner_top1_share": float(pos.head(1).sum() / total),
        "winner_top3_share": float(pos.head(3).sum() / total),
        "winner_top5_share": float(pos.head(5).sum() / total),
        "winner_top10_share": float(pos.head(10).sum() / total),
    }


def _positive_month_concentration(monthly: pd.DataFrame) -> dict[str, float]:
    pos = monthly.loc[monthly["month_return"] > 0, "month_return"].sort_values(ascending=False)
    if pos.empty:
        return {
            "positive_month_top1_share": 0.0,
            "positive_month_top3_share": 0.0,
            "positive_month_top5_share": 0.0,
        }
    total = float(pos.sum())
    return {
        "positive_month_top1_share": float(pos.head(1).sum() / total),
        "positive_month_top3_share": float(pos.head(3).sum() / total),
        "positive_month_top5_share": float(pos.head(5).sum() / total),
    }


def _phase_summary(phase: Phase, loaded: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    daily = loaded["daily"]
    trades = loaded["trades"]
    phase_start = pd.Timestamp(phase.start)
    phase_end = pd.Timestamp(phase.end)
    phase_daily = daily[(daily["date"] >= phase_start) & (daily["date"] <= phase_end)].copy()
    phase_trades = trades[(trades["date"] >= phase_start) & (trades["date"] <= phase_end)].copy()
    sells = phase_trades[phase_trades["side"] == "SELL"].copy()
    buys = phase_trades[phase_trades["side"] == "BUY"].copy()

    if phase_daily.empty:
        raise ValueError(f"{phase.phase_key} has no daily rows")

    monthly = _monthly_returns(daily, phase_daily)
    reason_counts = sells["reason_code"].value_counts(dropna=False).rename_axis("reason_code").reset_index(name="sell_count")
    if not reason_counts.empty:
        reason_counts["sell_share"] = reason_counts["sell_count"] / reason_counts["sell_count"].sum()

    winner = _winner_concentration(sells)
    positive_month = _positive_month_concentration(monthly)
    invested_daily = phase_daily[phase_daily["gross_exposure"] > 1e-9]
    summary = {
        "phase_key": phase.phase_key,
        "phase_label": phase.phase_label,
        "experiment_id": phase.experiment_id,
        "start": phase.start,
        "end": phase.end,
        "trading_days": int(phase_daily.shape[0]),
        "first_invested_date": invested_daily["date"].min().date().isoformat() if not invested_daily.empty else "",
        "days_to_first_invested": int((invested_daily["date"].min() - phase_start).days) if not invested_daily.empty else -1,
        "first_buy_date": buys["date"].min().date().isoformat() if not buys.empty else "",
        "phase_total_return": float(phase_daily["nav"].iloc[-1] / phase_daily["nav"].iloc[0] - 1.0),
        "avg_monthly_return": float(monthly["month_return"].mean()) if not monthly.empty else 0.0,
        "positive_month_ratio": float((monthly["month_return"] > 0).mean()) if not monthly.empty else 0.0,
        "best_month_return": float(monthly["month_return"].max()) if not monthly.empty else 0.0,
        "worst_month_return": float(monthly["month_return"].min()) if not monthly.empty else 0.0,
        "avg_gross_exposure": float(phase_daily["gross_exposure"].mean()),
        "median_gross_exposure": float(phase_daily["gross_exposure"].median()),
        "avg_gross_exposure_when_invested": float(phase_daily.loc[phase_daily["gross_exposure"] > 1e-9, "gross_exposure"].mean()) if (phase_daily["gross_exposure"] > 1e-9).any() else 0.0,
        "avg_positions_count": float(phase_daily["positions_count_end_of_day"].mean()),
        "median_positions_count": float(phase_daily["positions_count_end_of_day"].median()),
        "avg_positions_when_invested": float(phase_daily.loc[phase_daily["positions_count_end_of_day"] > 0, "positions_count_end_of_day"].mean()) if (phase_daily["positions_count_end_of_day"] > 0).any() else 0.0,
        "zero_exposure_rate": float((phase_daily["gross_exposure"] <= 1e-9).mean()),
        "low_exposure_rate_lt_50pct": float((phase_daily["gross_exposure"] < 0.5).mean()),
        "high_exposure_rate_ge_80pct": float((phase_daily["gross_exposure"] >= 0.8).mean()),
        "benchmark_regime_on_rate": float(phase_daily["benchmark_regime_on"].mean()),
        "strong_risk_on_rate": float((phase_daily["strong_risk_on"] > 0.5).mean()),
        "buy_count": int(buys.shape[0]),
        "sell_count": int(sells.shape[0]),
        "avg_holding_bars": float(sells["holding_bars"].dropna().mean()) if sells["holding_bars"].notna().any() else 0.0,
        "median_holding_bars": float(sells["holding_bars"].dropna().median()) if sells["holding_bars"].notna().any() else 0.0,
        "sell_win_rate": float((sells["realized_pnl"].fillna(0.0) > 0).mean()) if not sells.empty else 0.0,
        "avg_sell_pnl_pct": float(sells["pnl_pct"].dropna().mean()) if sells["pnl_pct"].notna().any() else 0.0,
        "median_sell_pnl_pct": float(sells["pnl_pct"].dropna().median()) if sells["pnl_pct"].notna().any() else 0.0,
        "net_realized_pnl": float(pd.to_numeric(sells["realized_pnl"], errors="coerce").fillna(0.0).sum()) if not sells.empty else 0.0,
        **winner,
        **positive_month,
    }

    symbol_pnl = sells.groupby("symbol", as_index=False)["realized_pnl"].sum().sort_values("realized_pnl", ascending=False)
    return summary, monthly, reason_counts, symbol_pnl


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    loaded_by_exp = {exp_id: _load_experiment(exp_id) for exp_id in EXPERIMENTS}
    for exp_id, loaded in loaded_by_exp.items():
        loaded["trades"] = _prepare_trades(loaded["trades"], loaded["date_to_idx"])

    summaries: list[dict[str, Any]] = []

    for phase in PHASES:
        summary, monthly, reason_counts, symbol_pnl = _phase_summary(phase, loaded_by_exp[phase.experiment_id])
        summaries.append(summary)
        monthly.to_csv(OUTPUT_DIR / f"{phase.phase_key}_monthly.csv", index=False, encoding="utf-8-sig")
        reason_counts.to_csv(OUTPUT_DIR / f"{phase.phase_key}_sell_reasons.csv", index=False, encoding="utf-8-sig")
        symbol_pnl.to_csv(OUTPUT_DIR / f"{phase.phase_key}_symbol_realized_pnl.csv", index=False, encoding="utf-8-sig")

    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(OUTPUT_DIR / "phase_attack_summary.csv", index=False, encoding="utf-8-sig")
    (OUTPUT_DIR / "phase_attack_summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
