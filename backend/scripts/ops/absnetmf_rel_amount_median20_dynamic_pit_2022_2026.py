from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from backend.api.shared.json_utils import sanitize_json
from backend.research.a_share_moneyflow_divergence import (
    UniverseFilterConfig,
    _create_provider_from_payload,
    _extract_runtime_costs,
    _month_end_observation_dates,
    apply_universe_filters,
    build_month_end_candidate_snapshot,
)
from backend.scripts.ops.absnetmf_dynamic_pit_audit import (
    _annual_returns,
    _phase_metrics,
    _replay_monthly,
)


REPO = Path(__file__).resolve().parents[3]
RUN_META = REPO / "outputs/studies/a_share_moneyflow_abs_mean20_csi800_1226_v2_canonical/factors_a_share_moneyflow_abs_mean20_csi800_1226_v2_canonical/1226_FULL/CSI800_V2_CANONICAL_T10_ABSNETMF_MA20/run_meta.json"
OUT_DIR = REPO / "outputs/ops/absnetmf_rel_amount_median20_dynamic_pit_2022_2026_20260320"


def _industry_map_for(industry_history: pd.DataFrame, obs_ts: pd.Timestamp, symbols: list[str]) -> dict[str, str]:
    if industry_history.empty or not symbols:
        return {}
    frame = industry_history[
        (industry_history["ts_code"].isin(symbols))
        & (industry_history["start_date"] <= obs_ts)
        & (industry_history["end_date"].isna() | (industry_history["end_date"] > obs_ts))
    ].copy()
    if frame.empty:
        return {}
    frame = frame.sort_values(["ts_code", "start_date"]).drop_duplicates("ts_code", keep="last")
    return dict(zip(frame["ts_code"], frame["industry_l1"]))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    request_payload = dict(json.loads(RUN_META.read_text(encoding="utf-8"))["request_payload"])
    provider, cfg_snapshot, _ = _create_provider_from_payload(request_payload)
    initial_capital, lot_size, costs = _extract_runtime_costs(cfg_snapshot)

    start_date = date.fromisoformat("2022-01-04")
    end_date = date.fromisoformat("2026-03-16")
    warmup_start = start_date - timedelta(days=450)
    trading_days = provider.load_trading_calendar_cn(start_date, end_date)
    observation_dates = _month_end_observation_dates(trading_days, start_date, end_date)

    const_hist = provider.load_index_constituent_history("000906.SH", start_date, end_date)
    const_hist["start_date"] = pd.to_datetime(const_hist["start_date"], errors="coerce").dt.normalize()
    const_hist["end_date"] = pd.to_datetime(const_hist["end_date"], errors="coerce").dt.normalize()
    const_hist["symbol"] = const_hist["symbol"].astype(str).str.lower()
    union_symbols = sorted(const_hist["symbol"].dropna().unique().tolist())

    security_master = provider.load_security_master(union_symbols)
    st_history = provider.load_st_history(union_symbols, warmup_start, end_date)
    industry_history = provider.load_industry_history(union_symbols, warmup_start, end_date)
    if not industry_history.empty:
        industry_history["ts_code"] = industry_history["ts_code"].astype(str).str.lower()
        industry_history["start_date"] = pd.to_datetime(industry_history["start_date"], errors="coerce").dt.normalize()
        industry_history["end_date"] = pd.to_datetime(industry_history["end_date"], errors="coerce").dt.normalize()

    full_price = provider.load_ohlcv_daily(union_symbols, warmup_start, end_date, source="absnetmf_rel_amount_median_dynamic_pit")
    full_mf = provider.load_stock_moneyflow(union_symbols, warmup_start, end_date, table="pit_stock_moneyflow_v2")

    full_price["date"] = pd.to_datetime(full_price["date"], errors="coerce").dt.normalize()
    full_price["symbol"] = full_price["symbol"].astype(str).str.lower()
    full_price["close"] = pd.to_numeric(full_price.get("close"), errors="coerce")
    full_price["adj_factor"] = pd.to_numeric(full_price.get("adj_factor"), errors="coerce")
    full_price["amount"] = pd.to_numeric(full_price.get("amount"), errors="coerce")
    full_price["hfq_close"] = full_price["close"] * full_price["adj_factor"]
    full_price = full_price.sort_values(["symbol", "date"]).reset_index(drop=True)
    full_price["hfq_ret1"] = full_price.groupby("symbol")["hfq_close"].pct_change()
    full_price["vol20_annual"] = full_price.groupby("symbol")["hfq_ret1"].transform(
        lambda s: s.rolling(20, min_periods=20).std(ddof=0) * np.sqrt(252.0)
    )

    full_mf["trade_date"] = pd.to_datetime(full_mf.get("trade_date", full_mf.get("date")), errors="coerce").dt.normalize()
    full_mf["symbol"] = full_mf["symbol"].astype(str).str.lower()
    full_mf["net_mf_amount"] = pd.to_numeric(full_mf.get("net_mf_amount"), errors="coerce")
    full_mf = full_mf.sort_values(["symbol", "trade_date"]).reset_index(drop=True)

    mf_enriched = full_mf.merge(
        full_price[["date", "symbol", "amount"]].rename(columns={"date": "trade_date"}),
        on=["trade_date", "symbol"],
        how="left",
    )
    mf_enriched["amount"] = pd.to_numeric(mf_enriched["amount"], errors="coerce")
    mf_enriched["rel_abs_net_mf"] = np.where(
        mf_enriched["net_mf_amount"].notna() & mf_enriched["amount"].notna() & mf_enriched["amount"].gt(0.0),
        mf_enriched["net_mf_amount"].abs() / mf_enriched["amount"],
        np.nan,
    )
    mf_enriched["rel_abs_net_mf_median20_count"] = mf_enriched.groupby("symbol")["rel_abs_net_mf"].transform(
        lambda s: s.rolling(20, min_periods=20).count()
    )
    mf_enriched["rel_abs_net_mf_median20"] = mf_enriched.groupby("symbol")["rel_abs_net_mf"].transform(
        lambda s: s.rolling(20, min_periods=20).median()
    )

    filter_cfg = UniverseFilterConfig(
        exclude_st=True,
        exclude_delisted=True,
        exclude_suspended=True,
        exclude_star_market=False,
        exclude_chinext=False,
        min_list_days=1,
        min_avg_turnover_20d=0.0,
        min_avg_turnover_rate_20d=0.0,
        min_price=0.0,
    )

    ranked_rows: list[pd.DataFrame] = []
    selected_rows: list[pd.DataFrame] = []
    schedule_rows: list[dict[str, object]] = []

    for obs in observation_dates:
        obs_ts = pd.Timestamp(obs).normalize()
        exec_candidates = [pd.Timestamp(d).normalize() for d in trading_days if pd.Timestamp(d).normalize().date() > obs]
        exec_ts = exec_candidates[0] if exec_candidates else pd.NaT
        if pd.notna(exec_ts) and exec_ts.date() > end_date:
            exec_ts = pd.NaT

        active = const_hist[(const_hist["start_date"] <= obs_ts) & (const_hist["end_date"].isna() | (const_hist["end_date"] > obs_ts))]
        active_symbols = sorted(active["symbol"].dropna().unique().tolist())
        candidate_rows = build_month_end_candidate_snapshot(
            full_price[
                (full_price["symbol"].isin(active_symbols))
                & (full_price["date"] >= obs_ts - pd.Timedelta(days=450))
                & (full_price["date"] <= obs_ts)
            ].copy(),
            [obs],
            security_master=security_master,
            st_history=st_history,
        )
        filtered_rows, _, excluded_counts = apply_universe_filters(candidate_rows, filter_cfg)
        tradable_symbols = sorted(filtered_rows["symbol"].dropna().astype(str).str.lower().unique().tolist())
        denominator_count = len(tradable_symbols)

        mf_chunk = mf_enriched[
            (mf_enriched["symbol"].isin(active_symbols))
            & (mf_enriched["trade_date"] >= obs_ts - pd.Timedelta(days=90))
            & (mf_enriched["trade_date"] <= obs_ts)
        ].copy()
        mf_day = mf_chunk[mf_chunk["trade_date"] == obs_ts].copy()
        if tradable_symbols:
            mf_day = mf_day[mf_day["symbol"].isin(tradable_symbols)].copy()
        row_cov = float(mf_day["symbol"].nunique() / denominator_count) if denominator_count > 0 else 0.0
        net_cov = float(mf_day[mf_day["net_mf_amount"].notna()]["symbol"].nunique() / denominator_count) if denominator_count > 0 else 0.0
        can_rebalance = bool(pd.notna(exec_ts) and denominator_count > 0 and row_cov >= 0.95 and net_cov >= 0.90)
        gate_status = "tradable" if can_rebalance else "skipped_low_coverage"
        schedule_rows.append(
            {
                "observation_date": obs_ts,
                "execution_date": exec_ts,
                "gate_status": gate_status,
                "pit_member_count": len(active_symbols),
                "coverage_denominator_count": denominator_count,
                "row_coverage_ratio": row_cov,
                "net_amount_coverage_ratio": net_cov,
                "excluded_counts_json": json.dumps(excluded_counts, ensure_ascii=False, sort_keys=True),
            }
        )

        factor_rows = mf_chunk[
            (mf_chunk["trade_date"] == obs_ts)
            & (mf_chunk["rel_abs_net_mf_median20_count"] == 20.0)
            & (mf_chunk["rel_abs_net_mf_median20"].notna())
        ][["symbol", "rel_abs_net_mf_median20"]].copy()
        vol_day = full_price[full_price["date"] == obs_ts][["symbol", "vol20_annual"]].copy()
        joined = filtered_rows.merge(factor_rows, on="symbol", how="inner").merge(vol_day, on="symbol", how="left")
        if joined.empty:
            continue
        joined["observation_date"] = obs_ts
        joined["execution_date"] = exec_ts
        joined["month"] = obs_ts.to_period("M").to_timestamp()
        joined["gate_status"] = gate_status
        joined["industry_l1"] = joined["symbol"].map(
            _industry_map_for(industry_history, obs_ts, joined["symbol"].astype(str).str.lower().tolist())
        ).fillna("UNKNOWN")
        joined = joined.sort_values(["rel_abs_net_mf_median20", "symbol"]).reset_index(drop=True)
        joined["rank_all"] = np.arange(1, len(joined) + 1)
        joined["liquidity_percentile"] = pd.to_numeric(joined["avg_turnover_20d"], errors="coerce").rank(method="average", pct=True)
        joined["volatility_percentile"] = pd.to_numeric(joined["vol20_annual"], errors="coerce").rank(method="average", pct=True)
        ranked_rows.append(
            joined[
                [
                    "observation_date",
                    "month",
                    "execution_date",
                    "symbol",
                    "rank_all",
                    "rel_abs_net_mf_median20",
                    "avg_turnover_20d",
                    "avg_turnover_rate_20d",
                    "vol20_annual",
                    "liquidity_percentile",
                    "volatility_percentile",
                    "industry_l1",
                    "gate_status",
                ]
            ].copy()
        )
        if can_rebalance:
            sel = joined.head(10).copy()
            sel["rank"] = np.arange(1, len(sel) + 1)
            selected_rows.append(
                sel[
                    [
                        "observation_date",
                        "month",
                        "execution_date",
                        "symbol",
                        "rank",
                        "rank_all",
                        "rel_abs_net_mf_median20",
                        "avg_turnover_20d",
                        "avg_turnover_rate_20d",
                        "vol20_annual",
                        "liquidity_percentile",
                        "volatility_percentile",
                        "industry_l1",
                        "gate_status",
                    ]
                ].copy()
            )

    schedule_df = pd.DataFrame(schedule_rows)
    ranked_df = pd.concat(ranked_rows, ignore_index=True) if ranked_rows else pd.DataFrame()
    selected_df = pd.concat(selected_rows, ignore_index=True) if selected_rows else pd.DataFrame()

    replay_symbols = sorted(set(ranked_df["symbol"].dropna().astype(str).str.lower().tolist())) if not ranked_df.empty else []
    replay_price = (
        provider.load_ohlcv_daily(replay_symbols, start_date, end_date, source="absnetmf_rel_amount_median_dynamic_replay")
        if replay_symbols
        else pd.DataFrame()
    )
    replay = _replay_monthly(
        replay_price,
        [pd.Timestamp(d).normalize() for d in trading_days],
        schedule_df,
        selected_df[["observation_date", "month", "execution_date", "symbol", "rank"]] if not selected_df.empty else selected_df,
        initial_capital=float(initial_capital),
        lot_size=int(lot_size),
        commission_rate=float(costs["commission_rate"]),
        commission_min=float(costs["commission_min"]),
        stamp_tax_rate=float(costs["stamp_tax_rate"]),
        slippage_bps=float(costs["slippage_bps"]),
    )

    daily_df = replay["portfolio_daily"].copy()
    trades_df = replay["portfolio_trades"].copy()
    nav_df = replay["nav"].copy()
    perf = dict(replay["perf"] or {})
    trades_df["date"] = pd.to_datetime(trades_df.get("date"), errors="coerce")
    daily_df["turnover_pct"] = pd.to_numeric(daily_df.get("turnover_pct"), errors="coerce")
    effective_execution_start_date = (
        trades_df.loc[trades_df["side"].astype(str).str.upper().eq("BUY"), "date"].min().date().isoformat()
        if not trades_df.empty and trades_df["side"].astype(str).str.upper().eq("BUY").any()
        else ""
    )
    phase_df = _phase_metrics(nav_df)
    annual_df = _annual_returns(nav_df)

    planned_months = int(schedule_df["gate_status"].astype(str).isin(["tradable", "skipped_low_coverage"]).sum()) if not schedule_df.empty else 0
    tradable_months = int(schedule_df["gate_status"].astype(str).eq("tradable").sum()) if not schedule_df.empty else 0
    skipped_months = int(max(planned_months - tradable_months, 0))
    summary = {
        "definition": "month_end median20(abs(net_mf_amount) / amount), top10 lowest, month-open entry, hold one month, equal weight",
        "scope": {
            "data_role": "v2_canonical",
            "universe": "CSI800 + strict historical PIT dynamic",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        "schedule": {
            "planned_months": planned_months,
            "tradable_months": tradable_months,
            "skipped_months": skipped_months,
            "mean_row_coverage_ratio": float(pd.to_numeric(schedule_df["row_coverage_ratio"], errors="coerce").mean()) if not schedule_df.empty else None,
            "mean_net_amount_coverage_ratio": float(pd.to_numeric(schedule_df["net_amount_coverage_ratio"], errors="coerce").mean()) if not schedule_df.empty else None,
        },
        "performance": {
            "total_return": float(perf.get("total_return") or 0.0),
            "cagr": float(perf.get("cagr") or 0.0),
            "sharpe": float(perf.get("sharpe") or 0.0),
            "max_drawdown": float(perf.get("max_drawdown") or 0.0),
            "calmar": float(perf.get("calmar") or 0.0) if perf.get("calmar") is not None else None,
            "trades": int(perf.get("trades") or 0),
            "closed_trades": int(trades_df["side"].astype(str).str.upper().eq("SELL").sum()) if not trades_df.empty else 0,
            "turnover": float(daily_df["turnover_pct"].mean()) if not daily_df.empty and daily_df["turnover_pct"].notna().any() else None,
            "effective_execution_start_date": effective_execution_start_date,
        },
        "selection": {
            "distinct_symbols": int(selected_df["symbol"].nunique()) if not selected_df.empty else 0,
            "selection_rows": int(len(selected_df)),
            "mean_candidates_ranked_per_month": float(ranked_df.groupby("observation_date")["symbol"].size().mean()) if not ranked_df.empty else 0.0,
        },
        "phase_metrics": sanitize_json(phase_df.to_dict(orient="records")),
        "annual_returns": sanitize_json(annual_df.to_dict(orient="records")),
    }

    (OUT_DIR / "summary.json").write_text(json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2), encoding="utf-8")
    schedule_df.to_csv(OUT_DIR / "monthly_schedule.csv", index=False, encoding="utf-8-sig")
    ranked_df.to_csv(OUT_DIR / "ranked_panel.csv", index=False, encoding="utf-8-sig")
    selected_df.to_csv(OUT_DIR / "selection.csv", index=False, encoding="utf-8-sig")
    daily_df.to_csv(OUT_DIR / "portfolio_daily.csv", index=False, encoding="utf-8-sig")
    trades_df.to_csv(OUT_DIR / "portfolio_trades.csv", index=False, encoding="utf-8-sig")
    nav_df.to_csv(OUT_DIR / "nav.csv", index=False, encoding="utf-8-sig")
    phase_df.to_csv(OUT_DIR / "phase_metrics.csv", index=False, encoding="utf-8-sig")
    annual_df.to_csv(OUT_DIR / "annual_returns.csv", index=False, encoding="utf-8-sig")
    report = "\n".join(
        [
            "# ABSNETMF_REL_AMOUNT_MEDIAN20 Dynamic PIT 2022-2026",
            "",
            "## 结论",
            "",
            f"- total_return={summary['performance']['total_return']:.4f}",
            f"- cagr={summary['performance']['cagr']:.4f}",
            f"- sharpe={summary['performance']['sharpe']:.4f}",
            f"- max_drawdown={summary['performance']['max_drawdown']:.4f}",
            f"- trades={summary['performance']['trades']}",
            f"- tradable_months={summary['schedule']['tradable_months']}/{summary['schedule']['planned_months']}",
        ]
    )
    (OUT_DIR / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
