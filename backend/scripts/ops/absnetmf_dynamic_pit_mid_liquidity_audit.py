from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from backend.api.shared.json_utils import sanitize_json
from backend.scripts.ops.absnetmf_dynamic_pit_audit import (
    OUT_DIR as BASE_AUDIT_DIR,
    SOURCE_DIR,
    _annual_returns,
    _build_ranked_frames,
    _phase_metrics,
    _replay_monthly,
    _symbol_contribution,
)


OUT_DIR = Path(__file__).resolve().parents[3] / "outputs/ops/absnetmf_ma20_dynamic_pit_mid_liquidity_audit_20260320"
LOWER = 0.2
UPPER = 5.0


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    context, schedule_df, ranked_df, _selected_df, trading_days = _build_ranked_frames()
    unrestricted_summary = json.loads((BASE_AUDIT_DIR / "summary.json").read_text(encoding="utf-8"))

    band_ranked = ranked_df.copy()
    band_ranked["avg_turnover_rate_20d"] = pd.to_numeric(band_ranked["avg_turnover_rate_20d"], errors="coerce")
    band_ranked = band_ranked[
        band_ranked["avg_turnover_rate_20d"].notna()
        & band_ranked["avg_turnover_rate_20d"].ge(LOWER)
        & band_ranked["avg_turnover_rate_20d"].le(UPPER)
    ].copy()

    band_ranked = band_ranked[band_ranked["gate_status"].astype(str).eq("tradable") & pd.to_datetime(band_ranked["execution_date"], errors="coerce").notna()].copy()
    band_monthly = (
        band_ranked.groupby("observation_date", as_index=False)
        .agg(candidates_in_band=("symbol", "size"), execution_date=("execution_date", "first"), month=("month", "first"))
        .sort_values("observation_date")
    )
    band_selection_rows = []
    for obs, grp in band_ranked.groupby("observation_date"):
        frame = grp.sort_values(["rank_all", "symbol"]).head(10).copy()
        if frame.empty:
            continue
        frame["rank"] = np.arange(1, len(frame) + 1)
        band_selection_rows.append(frame[["observation_date", "month", "execution_date", "symbol", "rank", "rank_all", "absnetmf_ma20", "avg_turnover_20d", "avg_turnover_rate_20d", "vol20_annual", "liquidity_percentile", "volatility_percentile", "industry_l1", "gate_status"]].copy())
    band_selection = pd.concat(band_selection_rows, ignore_index=True) if band_selection_rows else pd.DataFrame()

    replay_symbols = sorted(set(band_ranked["symbol"].dropna().astype(str).str.lower().tolist()))
    replay_price = context["provider"].load_ohlcv_daily(replay_symbols, pd.Timestamp("2012-01-04").date(), pd.Timestamp("2026-03-16").date(), source="absnetmf_dynamic_mid_liquidity_replay")
    band_replay = _replay_monthly(
        replay_price,
        trading_days,
        schedule_df,
        band_selection[["observation_date", "month", "execution_date", "symbol", "rank"]] if not band_selection.empty else band_selection,
        initial_capital=context["initial_capital"],
        lot_size=context["lot_size"],
        commission_rate=float(context["costs"]["commission_rate"]),
        commission_min=float(context["costs"]["commission_min"]),
        stamp_tax_rate=float(context["costs"]["stamp_tax_rate"]),
        slippage_bps=float(context["costs"]["slippage_bps"]),
    )
    band_perf = dict(band_replay["perf"] or {})
    band_trades = band_replay["portfolio_trades"].copy()
    band_daily = band_replay["portfolio_daily"].copy()
    band_nav = band_replay["nav"].copy()

    freq = band_selection.groupby("symbol").size().reset_index(name="selection_count").sort_values(["selection_count", "symbol"], ascending=[False, True]).reset_index(drop=True)
    total_selection_rows = int(len(band_selection))
    freq["selection_share"] = freq["selection_count"] / total_selection_rows if total_selection_rows > 0 else np.nan
    contrib_df, _ = _symbol_contribution(band_trades, band_daily, band_nav, context["initial_capital"])
    top10 = freq.head(10).merge(contrib_df[["symbol", "pnl_contribution", "return_points", "contribution_share_of_total_pnl"]], on="symbol", how="left").fillna(0.0)
    top3_symbols = freq.head(3)["symbol"].tolist()
    top5_symbols = freq.head(5)["symbol"].tolist()

    def build_variant_selection(excluded_symbols: list[str]) -> pd.DataFrame:
        excluded = {str(s).lower() for s in excluded_symbols}
        rows = []
        for _, grp in band_ranked.groupby("observation_date"):
            frame = grp.sort_values(["rank_all", "symbol"])
            frame = frame[~frame["symbol"].isin(excluded)].copy().head(10)
            if frame.empty:
                continue
            frame["rank"] = np.arange(1, len(frame) + 1)
            rows.append(frame[["observation_date", "month", "execution_date", "symbol", "rank"]].copy())
        return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["observation_date", "month", "execution_date", "symbol", "rank"])

    stress_rows = [
        {
            "variant": "band_base",
            "excluded_symbols": "",
            "total_return": float(band_perf.get("total_return") or 0.0),
            "cagr": float(band_perf.get("cagr") or 0.0),
            "sharpe": float(band_perf.get("sharpe") or 0.0),
            "max_drawdown": float(band_perf.get("max_drawdown") or 0.0),
            "trades": int(band_perf.get("trades") or 0),
            "distinct_symbols": int(band_selection["symbol"].nunique()) if not band_selection.empty else 0,
        }
    ]
    for name, excluded in [("exclude_top3", top3_symbols), ("exclude_top5", top5_symbols)]:
        variant_sel = build_variant_selection(excluded)
        replay = _replay_monthly(
            replay_price,
            trading_days,
            schedule_df,
            variant_sel,
            initial_capital=context["initial_capital"],
            lot_size=context["lot_size"],
            commission_rate=float(context["costs"]["commission_rate"]),
            commission_min=float(context["costs"]["commission_min"]),
            stamp_tax_rate=float(context["costs"]["stamp_tax_rate"]),
            slippage_bps=float(context["costs"]["slippage_bps"]),
        )
        perf = dict(replay["perf"] or {})
        stress_rows.append({"variant": name, "excluded_symbols": ",".join(excluded), "total_return": float(perf.get("total_return") or 0.0), "cagr": float(perf.get("cagr") or 0.0), "sharpe": float(perf.get("sharpe") or 0.0), "max_drawdown": float(perf.get("max_drawdown") or 0.0), "trades": int(perf.get("trades") or 0), "distinct_symbols": int(variant_sel["symbol"].nunique())})
    stress_df = pd.DataFrame(stress_rows)

    industry_distribution = band_selection.groupby("industry_l1", as_index=False).size().rename(columns={"size": "selection_count"}).sort_values(["selection_count", "industry_l1"], ascending=[False, True]).reset_index(drop=True)
    if not industry_distribution.empty:
        industry_distribution["selection_share"] = industry_distribution["selection_count"] / len(band_selection)
    reuse_rows = []
    prev_set: set[str] | None = None
    for obs, grp in band_selection.groupby("observation_date"):
        current = set(grp["symbol"].tolist())
        reuse_count = len(current & prev_set) if prev_set is not None else np.nan
        reuse_rate = reuse_count / len(current) if prev_set is not None and len(current) > 0 else np.nan
        reuse_rows.append({"observation_date": obs, "selected_count": len(current), "reused_count_vs_prev": reuse_count, "reuse_rate_vs_prev": reuse_rate})
        prev_set = current
    reuse_df = pd.DataFrame(reuse_rows)

    annual_df = _annual_returns(band_nav)
    phase_df = _phase_metrics(band_nav)
    style_summary = {
        "selection_rows": int(len(band_selection)),
        "distinct_symbols": int(band_selection["symbol"].nunique()) if not band_selection.empty else 0,
        "top10_selection_share": float(freq.head(10)["selection_count"].sum() / total_selection_rows) if total_selection_rows > 0 else 0.0,
        "avg_turnover_rate_20d_mean": float(pd.to_numeric(band_selection["avg_turnover_rate_20d"], errors="coerce").mean()) if not band_selection.empty else None,
        "avg_turnover_rate_20d_median": float(pd.to_numeric(band_selection["avg_turnover_rate_20d"], errors="coerce").median()) if not band_selection.empty else None,
        "liquidity_percentile_mean_vs_full_ranked_universe": float(pd.to_numeric(band_selection["liquidity_percentile"], errors="coerce").mean()) if not band_selection.empty else None,
        "liquidity_percentile_median_vs_full_ranked_universe": float(pd.to_numeric(band_selection["liquidity_percentile"], errors="coerce").median()) if not band_selection.empty else None,
        "vol20_annual_mean": float(pd.to_numeric(band_selection["vol20_annual"], errors="coerce").mean()) if not band_selection.empty else None,
        "vol20_annual_median": float(pd.to_numeric(band_selection["vol20_annual"], errors="coerce").median()) if not band_selection.empty else None,
        "volatility_percentile_mean_vs_full_ranked_universe": float(pd.to_numeric(band_selection["volatility_percentile"], errors="coerce").mean()) if not band_selection.empty else None,
        "volatility_percentile_median_vs_full_ranked_universe": float(pd.to_numeric(band_selection["volatility_percentile"], errors="coerce").median()) if not band_selection.empty else None,
        "reuse_rate_vs_prev_mean": float(pd.to_numeric(reuse_df["reuse_rate_vs_prev"], errors="coerce").mean()) if not reuse_df.empty else None,
        "reuse_rate_vs_prev_median": float(pd.to_numeric(reuse_df["reuse_rate_vs_prev"], errors="coerce").median()) if not reuse_df.empty else None,
        "top1_industry_share": float(industry_distribution["selection_share"].iloc[0]) if len(industry_distribution) >= 1 else None,
        "top3_industry_share": float(industry_distribution["selection_share"].head(3).sum()) if len(industry_distribution) >= 1 else None,
    }
    band_schedule = {
        "months_total": int(schedule_df["gate_status"].astype(str).eq("tradable").sum()),
        "months_with_candidates_in_band": int((band_monthly["candidates_in_band"] > 0).sum()) if not band_monthly.empty else 0,
        "months_with_top10_in_band": int((band_monthly["candidates_in_band"] >= 10).sum()) if not band_monthly.empty else 0,
        "mean_candidates_in_band_per_month": float(band_monthly["candidates_in_band"].mean()) if not band_monthly.empty else 0.0,
    }

    summary = {
        "band_definition": "avg_turnover_rate_20d between 0.2% and 5.0%",
        "unrestricted_base_performance": unrestricted_summary["base_performance"],
        "band_performance": {
            "total_return": float(band_perf.get("total_return") or 0.0),
            "cagr": float(band_perf.get("cagr") or 0.0),
            "sharpe": float(band_perf.get("sharpe") or 0.0),
            "max_drawdown": float(band_perf.get("max_drawdown") or 0.0),
            "trades": int(band_perf.get("trades") or 0),
        },
        "band_schedule": band_schedule,
        "top10_high_frequency_symbols": sanitize_json(freq.head(10).to_dict(orient="records")),
        "top10_contribution": sanitize_json(top10.to_dict(orient="records")),
        "top10_combined_contribution_share_of_total_pnl": float(top10["contribution_share_of_total_pnl"].sum()) if not top10.empty else 0.0,
        "top3_symbols": top3_symbols,
        "top5_symbols": top5_symbols,
        "stress_test": sanitize_json(stress_df.to_dict(orient="records")),
        "style_summary": sanitize_json(style_summary),
        "annual_returns": sanitize_json(annual_df.to_dict(orient="records")),
        "phase_metrics": sanitize_json(phase_df.to_dict(orient="records")),
    }

    (OUT_DIR / "summary.json").write_text(json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2), encoding="utf-8")
    band_selection.to_csv(OUT_DIR / "band_selection.csv", index=False, encoding="utf-8-sig")
    band_monthly.to_csv(OUT_DIR / "band_monthly_candidates.csv", index=False, encoding="utf-8-sig")
    top10.to_csv(OUT_DIR / "top10_frequency_contribution.csv", index=False, encoding="utf-8-sig")
    stress_df.to_csv(OUT_DIR / "stress_test_comparison.csv", index=False, encoding="utf-8-sig")
    industry_distribution.to_csv(OUT_DIR / "industry_distribution.csv", index=False, encoding="utf-8-sig")
    band_selection[["observation_date", "execution_date", "symbol", "industry_l1"]].to_csv(OUT_DIR / "industry_selected_rows.csv", index=False, encoding="utf-8-sig")
    band_selection[["observation_date", "execution_date", "symbol", "avg_turnover_20d", "avg_turnover_rate_20d", "liquidity_percentile"]].to_csv(OUT_DIR / "liquidity_profile_selected_rows.csv", index=False, encoding="utf-8-sig")
    band_selection[["observation_date", "execution_date", "symbol", "vol20_annual", "volatility_percentile"]].to_csv(OUT_DIR / "volatility_profile_selected_rows.csv", index=False, encoding="utf-8-sig")
    reuse_df.to_csv(OUT_DIR / "selection_reuse_by_month.csv", index=False, encoding="utf-8-sig")
    annual_df.to_csv(OUT_DIR / "annual_returns.csv", index=False, encoding="utf-8-sig")
    phase_df.to_csv(OUT_DIR / "phase_metrics.csv", index=False, encoding="utf-8-sig")
    band_replay["portfolio_daily"].to_csv(OUT_DIR / "band_portfolio_daily.csv", index=False, encoding="utf-8-sig")
    band_replay["portfolio_trades"].to_csv(OUT_DIR / "band_portfolio_trades.csv", index=False, encoding="utf-8-sig")
    band_replay["nav"].to_csv(OUT_DIR / "band_nav.csv", index=False, encoding="utf-8-sig")
    report = "\n".join(
        [
            "# ABSNETMF_MA20 Dynamic PIT Mid-Liquidity Audit",
            "",
            "## 结论",
            "",
            f"- 流动性带: {LOWER:.1f}%-{UPPER:.1f}% avg_turnover_rate_20d",
            f"- unrestricted: total_return={unrestricted_summary['base_performance']['total_return']:.4f}, sharpe={unrestricted_summary['base_performance']['sharpe']:.4f}",
            f"- band: total_return={float(band_perf.get('total_return') or 0.0):.4f}, sharpe={float(band_perf.get('sharpe') or 0.0):.4f}, max_drawdown={float(band_perf.get('max_drawdown') or 0.0):.4f}",
            f"- 带内前10高频股票入选占比={freq.head(10)['selection_count'].sum() / total_selection_rows:.4f}, PnL贡献占比={float(top10['contribution_share_of_total_pnl'].sum()) if not top10.empty else 0.0:.4f}",
        ]
    )
    (OUT_DIR / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
