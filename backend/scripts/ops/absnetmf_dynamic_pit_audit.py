from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from backend.api.shared.json_utils import sanitize_json
from backend.core.portfolio.metrics import compute_backtest_metrics
from backend.research.a_share_moneyflow_divergence import (
    UniverseFilterConfig,
    _bar_is_tradable,
    _build_nav_frame,
    _build_perf_daily_frame,
    _create_provider_from_payload,
    _empty_perf_payload,
    _extract_runtime_costs,
    _mark_price_for_nav,
    _max_affordable_buy_qty,
    _month_end_observation_dates,
    _normalize_price_history,
    _resolve_target_weights,
    _round_down_to_lot,
    apply_universe_filters,
    build_month_end_candidate_snapshot,
)


REPO = Path(__file__).resolve().parents[3]
SOURCE_DIR = REPO / "outputs/ops/strict_pit_dynamic_absnetmf_vs_monthly_trend_12m_1226_v2_canonical_tradable_cov_20260319"
OUT_DIR = REPO / "outputs/ops/absnetmf_ma20_dynamic_pit_audit_20260320"
RUN_META = REPO / "outputs/studies/a_share_moneyflow_abs_mean20_csi800_1226_v2_canonical/factors_a_share_moneyflow_abs_mean20_csi800_1226_v2_canonical/1226_FULL/CSI800_V2_CANONICAL_T10_ABSNETMF_MA20/run_meta.json"


def _phase_metrics(nav_frame: pd.DataFrame) -> pd.DataFrame:
    nav = nav_frame.copy()
    nav["date"] = pd.to_datetime(nav["date"], errors="coerce")
    nav["nav"] = pd.to_numeric(nav["nav"], errors="coerce")
    nav = nav.dropna(subset=["date", "nav"]).sort_values("date")
    rows: list[dict[str, object]] = []
    phases = [
        ("2012-2016", "2012-02-01", "2016-12-30"),
        ("2017-2021", "2017-01-03", "2021-12-31"),
        ("2022-2026", "2022-01-04", "2026-03-16"),
    ]
    for name, start_s, end_s in phases:
        frame = nav[(nav["date"] >= pd.Timestamp(start_s)) & (nav["date"] <= pd.Timestamp(end_s))].copy()
        if frame.empty:
            rows.append({"phase": name, "total_return": None, "cagr": None, "sharpe": None, "max_drawdown": None, "days": 0})
            continue
        frame["ret"] = frame["nav"].pct_change().fillna(0.0)
        total_return = float(frame["nav"].iloc[-1] / frame["nav"].iloc[0] - 1.0)
        days = max((frame["date"].iloc[-1] - frame["date"].iloc[0]).days, 1)
        cagr = float((frame["nav"].iloc[-1] / frame["nav"].iloc[0]) ** (365.25 / days) - 1.0)
        std = float(frame["ret"].std(ddof=0) or 0.0)
        sharpe = float(frame["ret"].mean() / std * np.sqrt(252.0)) if std > 0 else None
        maxdd = float((frame["nav"] / frame["nav"].cummax() - 1.0).min())
        rows.append({"phase": name, "total_return": total_return, "cagr": cagr, "sharpe": sharpe, "max_drawdown": maxdd, "days": int(len(frame))})
    return pd.DataFrame(rows)


def _annual_returns(nav_frame: pd.DataFrame) -> pd.DataFrame:
    nav = nav_frame.copy()
    nav["date"] = pd.to_datetime(nav["date"], errors="coerce")
    nav["nav"] = pd.to_numeric(nav["nav"], errors="coerce")
    nav = nav.dropna(subset=["date", "nav"]).sort_values("date")
    rows: list[dict[str, object]] = []
    for year, grp in nav.groupby(nav["date"].dt.year):
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


def _symbol_contribution(trades: pd.DataFrame, daily: pd.DataFrame, nav: pd.DataFrame, initial_capital: float) -> tuple[pd.DataFrame, float]:
    frame = trades.copy()
    frame["symbol"] = frame["symbol"].astype(str).str.lower()
    frame["signed_cf"] = np.where(
        frame["side"].astype(str).str.upper().eq("SELL"),
        pd.to_numeric(frame["net_amount"], errors="coerce"),
        -pd.to_numeric(frame["net_amount"], errors="coerce"),
    )
    cashflow = frame.groupby("symbol", as_index=False)["signed_cf"].sum().rename(columns={"signed_cf": "cashflow_contribution"})
    holdings = {}
    if not daily.empty:
        try:
            payload = json.loads(str(daily.iloc[-1].get("top_positions_json") or "[]"))
        except Exception:
            payload = []
        for item in payload:
            holdings[str(item.get("symbol", "")).lower()] = float(item.get("market_value", 0.0) or 0.0)
    holdings_df = pd.DataFrame([{"symbol": k, "ending_market_value": v} for k, v in holdings.items()])
    contrib = cashflow.merge(holdings_df, on="symbol", how="outer").fillna(0.0)
    contrib["pnl_contribution"] = contrib["cashflow_contribution"] + contrib["ending_market_value"]
    if not daily.empty and "nav" in daily.columns:
        total_pnl = float(pd.to_numeric(daily["nav"], errors="coerce").iloc[-1] - initial_capital)
    elif not nav.empty:
        total_pnl = float(pd.to_numeric(nav["nav"], errors="coerce").iloc[-1] * initial_capital - initial_capital)
    else:
        total_pnl = 0.0
    contrib["return_points"] = contrib["pnl_contribution"] / float(initial_capital)
    contrib["contribution_share_of_total_pnl"] = contrib["pnl_contribution"] / total_pnl if abs(total_pnl) > 1e-12 else np.nan
    return contrib, total_pnl


def _replay_monthly(
    price_history: pd.DataFrame,
    trading_days: list[pd.Timestamp],
    schedule: pd.DataFrame,
    selection_frame: pd.DataFrame,
    *,
    initial_capital: float,
    lot_size: int,
    commission_rate: float,
    commission_min: float,
    stamp_tax_rate: float,
    slippage_bps: float,
) -> dict[str, object]:
    normalized = _normalize_price_history(price_history)
    calendar = [pd.Timestamp(item).normalize() for item in list(trading_days or [])]
    if not calendar:
        return {"portfolio_daily": pd.DataFrame(), "portfolio_trades": pd.DataFrame(), "nav": pd.DataFrame(columns=["date", "nav"]), "perf": _empty_perf_payload()}
    open_idx = {(pd.Timestamp(r.date).normalize(), str(r.symbol)): None if pd.isna(r.open) else float(r.open) for r in normalized.itertuples(index=False)}
    close_idx = {(pd.Timestamp(r.date).normalize(), str(r.symbol)): None if pd.isna(r.close) else float(r.close) for r in normalized.itertuples(index=False)}
    volume_idx = {(pd.Timestamp(r.date).normalize(), str(r.symbol)): None if pd.isna(r.volume) else float(r.volume) for r in normalized.itertuples(index=False)}
    amount_idx = {(pd.Timestamp(r.date).normalize(), str(r.symbol)): None if pd.isna(r.amount) else float(r.amount) for r in normalized.itertuples(index=False)}
    suspended_idx = {(pd.Timestamp(r.date).normalize(), str(r.symbol)): bool(r.is_suspended) for r in normalized.itertuples(index=False)}
    limit_up_idx = {(pd.Timestamp(r.date).normalize(), str(r.symbol)): None if pd.isna(r.limit_up) else float(r.limit_up) for r in normalized.itertuples(index=False)}
    limit_down_idx = {(pd.Timestamp(r.date).normalize(), str(r.symbol)): None if pd.isna(r.limit_down) else float(r.limit_down) for r in normalized.itertuples(index=False)}
    sf = schedule.copy()
    sf["execution_date"] = pd.to_datetime(sf["execution_date"], errors="coerce").dt.normalize()
    sf["can_rebalance"] = sf["gate_status"].astype(str).eq("tradable")
    schedule_map = {pd.Timestamp(r.execution_date).normalize(): r._asdict() for r in sf.itertuples(index=False) if isinstance(r.execution_date, pd.Timestamp) and not pd.isna(r.execution_date)}
    selection = selection_frame.copy()
    if not selection.empty:
        selection["execution_date"] = pd.to_datetime(selection["execution_date"], errors="coerce").dt.normalize()
        selection["symbol"] = selection["symbol"].astype(str).str.lower()
        selection["rank"] = pd.to_numeric(selection["rank"], errors="coerce")
    selection_map = {k: f.sort_values(["rank", "symbol"]).reset_index(drop=True) for k, f in selection.groupby("execution_date", dropna=True)} if not selection.empty else {}
    slip_bps = float(slippage_bps or 0.0) / 10000.0
    lot = max(int(lot_size or 0), 1)
    cash = float(initial_capital or 0.0)
    positions: dict[str, int] = {}
    avg_cost: dict[str, float] = {}
    holding_source: dict[str, dict[str, str]] = {}
    last_close_map: dict[str, float] = {}
    trade_rows: list[dict[str, object]] = []
    daily_rows: list[dict[str, object]] = []
    peak_nav = float(initial_capital or 0.0)
    prev_nav = float(initial_capital or 0.0)
    effective_execution_start_date = None
    for day in calendar:
        traded_value = 0.0
        schedule_row = schedule_map.get(day)
        day_selection = selection_map.get(day)
        selected_count = int(len(day_selection)) if day_selection is not None else 0
        if schedule_row is not None and bool(schedule_row.get("can_rebalance")):
            if day_selection is None:
                day_selection = pd.DataFrame(columns=["symbol", "rank"])
            desired_symbols = [str(item).lower() for item in day_selection["symbol"].tolist()] if not day_selection.empty else []
            desired_ranks = {str(r.symbol): int(r.rank) for r in day_selection.itertuples(index=False) if pd.notna(r.rank)} if not day_selection.empty else {}
            target_weight_map = _resolve_target_weights(day_selection, weight_mode="equal_weight")
            portfolio_open_value = float(cash) + sum(float(qty) * _mark_price_for_nav(day, symbol, close_idx=close_idx, open_idx=open_idx, last_close_map=last_close_map, avg_cost=avg_cost) for symbol, qty in positions.items())
            target_qty_map: dict[str, int] = {}
            for symbol in desired_symbols:
                current_qty = int(positions.get(symbol, 0))
                if _bar_is_tradable(day, symbol, side="BUY", open_idx=open_idx, volume_idx=volume_idx, amount_idx=amount_idx, suspended_idx=suspended_idx, limit_up_idx=limit_up_idx, limit_down_idx=limit_down_idx):
                    open_px = float(open_idx.get((day, symbol)) or 0.0)
                    fill_px = open_px * (1.0 + slip_bps)
                    target_value = float(portfolio_open_value) * float(target_weight_map.get(symbol, 0.0))
                    raw_qty = int(target_value / fill_px) if fill_px > 0 else 0
                    target_qty_map[symbol] = _round_down_to_lot(raw_qty, lot)
                else:
                    target_qty_map[symbol] = current_qty
            for symbol, current_qty in sorted(list(positions.items())):
                target_qty = int(target_qty_map.get(symbol, 0))
                diff_qty = int(current_qty) - int(target_qty)
                if diff_qty > 0 and _bar_is_tradable(day, symbol, side="SELL", open_idx=open_idx, volume_idx=volume_idx, amount_idx=amount_idx, suspended_idx=suspended_idx, limit_up_idx=limit_up_idx, limit_down_idx=limit_down_idx):
                    open_px = float(open_idx.get((day, symbol)) or 0.0)
                    fill_px = open_px * (1.0 - slip_bps)
                    gross = float(diff_qty) * fill_px
                    comm = max(float(commission_min or 0.0), gross * float(commission_rate or 0.0)) if gross > 0 else 0.0
                    stax = gross * float(stamp_tax_rate or 0.0)
                    net = gross - comm - stax
                    cash += net
                    traded_value += gross
                    positions[symbol] = current_qty - diff_qty
                    if positions[symbol] <= 0:
                        positions.pop(symbol, None)
                        avg_cost.pop(symbol, None)
                        holding_source.pop(symbol, None)
                    trade_rows.append({"date": day.date().isoformat(), "symbol": symbol, "side": "SELL", "net_amount": round(net, 2), "reason_code": "MONTHLY_REBALANCE_EXIT" if symbol not in target_qty_map else "MONTHLY_REBALANCE_TRIM"})
            for symbol in desired_symbols:
                current_qty = int(positions.get(symbol, 0))
                target_qty = int(target_qty_map.get(symbol, current_qty))
                diff_qty = int(target_qty) - int(current_qty)
                if diff_qty <= 0:
                    continue
                if not _bar_is_tradable(day, symbol, side="BUY", open_idx=open_idx, volume_idx=volume_idx, amount_idx=amount_idx, suspended_idx=suspended_idx, limit_up_idx=limit_up_idx, limit_down_idx=limit_down_idx):
                    continue
                open_px = float(open_idx.get((day, symbol)) or 0.0)
                fill_px = open_px * (1.0 + slip_bps)
                affordable_qty = _max_affordable_buy_qty(
                    cash_available=float(cash),
                    fill_px=float(fill_px),
                    lot_size=lot,
                    commission_rate=float(commission_rate or 0.0),
                    commission_min=float(commission_min or 0.0),
                )
                qty = _round_down_to_lot(min(diff_qty, affordable_qty), lot)
                if qty <= 0:
                    continue
                gross = float(qty) * fill_px
                comm = max(float(commission_min or 0.0), gross * float(commission_rate or 0.0)) if gross > 0.0 else 0.0
                net = gross + comm
                if net > cash:
                    continue
                cash -= net
                traded_value += gross
                prev_qty = int(positions.get(symbol, 0))
                prev_avg = float(avg_cost.get(symbol, 0.0))
                new_qty = prev_qty + qty
                avg_cost[symbol] = ((prev_qty * prev_avg) + (qty * fill_px)) / float(new_qty) if new_qty > 0 else 0.0
                positions[symbol] = new_qty
                if prev_qty <= 0:
                    holding_source[symbol] = {"entry_reason_code": "MONTHLY_REBALANCE_ENTRY", "entry_date": day.date().isoformat()}
                trade_rows.append({"date": day.date().isoformat(), "symbol": symbol, "side": "BUY", "net_amount": round(net, 2), "reason_code": "MONTHLY_REBALANCE_ENTRY" if current_qty <= 0 else "MONTHLY_REBALANCE_ADD", "rank": int(desired_ranks.get(symbol, 10**9))})
                if effective_execution_start_date is None:
                    effective_execution_start_date = day.date().isoformat()
        market_value = 0.0
        top_positions = []
        for symbol, qty in sorted(positions.items()):
            mark_px = _mark_price_for_nav(day, symbol, close_idx=close_idx, open_idx=open_idx, last_close_map=last_close_map, avg_cost=avg_cost)
            position_value = float(qty) * float(mark_px)
            market_value += position_value
            top_positions.append((symbol, position_value))
        nav = float(cash) + float(market_value)
        peak_nav = max(peak_nav, nav)
        turnover_ratio = traded_value / prev_nav if prev_nav > 0 else 0.0
        daily_rows.append({"date": day.date().isoformat(), "nav": nav, "cash": float(cash), "market_value": market_value, "positions_count": int(len(positions)), "turnover": turnover_ratio, "turnover_pct": turnover_ratio, "drawdown": nav / peak_nav - 1.0 if peak_nav > 0 else 0.0, "selected_count": selected_count, "top_positions_json": json.dumps([{"symbol": sym, "market_value": round(val, 2)} for sym, val in sorted(top_positions, key=lambda x: x[1], reverse=True)[:10]], ensure_ascii=False)})
        prev_nav = float(nav)
        todays_close = normalized[normalized["date"] == day][["symbol", "close"]]
        for row in todays_close.itertuples(index=False):
            if pd.notna(row.close) and float(row.close) > 0.0:
                last_close_map[str(row.symbol)] = float(row.close)
    portfolio_daily = pd.DataFrame(daily_rows)
    portfolio_trades = pd.DataFrame(trade_rows)
    perf_daily = _build_perf_daily_frame(portfolio_daily, effective_execution_start_date)
    nav_frame = _build_nav_frame(portfolio_daily, effective_execution_start_date)
    perf = _empty_perf_payload()
    if not perf_daily.empty:
        trades_for_perf = portfolio_trades.copy()
        if not trades_for_perf.empty and effective_execution_start_date:
            trades_for_perf = trades_for_perf[pd.to_datetime(trades_for_perf["date"]) >= pd.Timestamp(effective_execution_start_date)]
        perf = compute_backtest_metrics(perf_daily, trades_for_perf, max_positions=max(int(selection["rank"].max()) if not selection.empty and pd.notna(selection["rank"].max()) else 10, 1))
    return {"portfolio_daily": portfolio_daily, "portfolio_trades": portfolio_trades, "nav": nav_frame, "perf": perf}


def _build_ranked_frames() -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame, pd.DataFrame, list[pd.Timestamp]]:
    request_payload = dict(json.loads(RUN_META.read_text(encoding="utf-8"))["request_payload"])
    provider, cfg_snapshot, _ = _create_provider_from_payload(request_payload)
    initial_capital, lot_size, costs = _extract_runtime_costs(cfg_snapshot)
    start_date = date.fromisoformat("2012-01-04")
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
    full_price = provider.load_ohlcv_daily(union_symbols, warmup_start, end_date, source="absnetmf_dynamic_audit")
    full_mf = provider.load_stock_moneyflow(union_symbols, warmup_start, end_date, table="pit_stock_moneyflow_v2")
    full_price["date"] = pd.to_datetime(full_price["date"], errors="coerce").dt.normalize()
    full_price["symbol"] = full_price["symbol"].astype(str).str.lower()
    full_price["close"] = pd.to_numeric(full_price.get("close"), errors="coerce")
    full_price["adj_factor"] = pd.to_numeric(full_price.get("adj_factor"), errors="coerce")
    full_price["hfq_close"] = full_price["close"] * full_price["adj_factor"]
    full_price = full_price.sort_values(["symbol", "date"]).reset_index(drop=True)
    full_price["hfq_ret1"] = full_price.groupby("symbol")["hfq_close"].pct_change()
    full_price["vol20_annual"] = full_price.groupby("symbol")["hfq_ret1"].transform(lambda s: s.rolling(20, min_periods=20).std(ddof=0) * np.sqrt(252.0))
    full_mf["trade_date"] = pd.to_datetime(full_mf.get("trade_date", full_mf.get("date")), errors="coerce").dt.normalize()
    full_mf["symbol"] = full_mf["symbol"].astype(str).str.lower()
    full_mf["net_mf_amount"] = pd.to_numeric(full_mf.get("net_mf_amount"), errors="coerce")
    full_mf["abs_net_mf_amount"] = full_mf["net_mf_amount"].abs()
    full_mf = full_mf.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    full_mf["absnetmf_ma20_count"] = full_mf.groupby("symbol")["abs_net_mf_amount"].transform(lambda s: s.rolling(20, min_periods=20).count())
    full_mf["absnetmf_ma20"] = full_mf.groupby("symbol")["abs_net_mf_amount"].transform(lambda s: s.rolling(20, min_periods=20).mean())
    filter_cfg = UniverseFilterConfig(exclude_st=True, exclude_delisted=True, exclude_suspended=True, exclude_star_market=False, exclude_chinext=False, min_list_days=1, min_avg_turnover_20d=0.0, min_avg_turnover_rate_20d=0.0, min_price=0.0)
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
        candidate_rows = build_month_end_candidate_snapshot(full_price[(full_price["symbol"].isin(active_symbols)) & (full_price["date"] >= obs_ts - pd.Timedelta(days=450)) & (full_price["date"] <= obs_ts)].copy(), [obs], security_master=security_master, st_history=st_history)
        filtered_rows, _, excluded_counts = apply_universe_filters(candidate_rows, filter_cfg)
        tradable_symbols = sorted(filtered_rows["symbol"].dropna().astype(str).str.lower().unique().tolist())
        denominator_count = len(tradable_symbols)
        mf_chunk = full_mf[(full_mf["symbol"].isin(active_symbols)) & (full_mf["trade_date"] >= obs_ts - pd.Timedelta(days=90)) & (full_mf["trade_date"] <= obs_ts)].copy()
        mf_day = mf_chunk[mf_chunk["trade_date"] == obs_ts].copy()
        if tradable_symbols:
            mf_day = mf_day[mf_day["symbol"].isin(tradable_symbols)].copy()
        row_cov = float(mf_day["symbol"].nunique() / denominator_count) if denominator_count > 0 else 0.0
        net_cov = float(mf_day[mf_day["net_mf_amount"].notna()]["symbol"].nunique() / denominator_count) if denominator_count > 0 else 0.0
        can_rebalance = bool(pd.notna(exec_ts) and denominator_count > 0 and row_cov >= 0.95 and net_cov >= 0.90)
        gate_status = "tradable" if can_rebalance else "skipped_low_coverage"
        schedule_rows.append({"observation_date": obs_ts, "execution_date": exec_ts, "gate_status": gate_status, "pit_member_count": len(active_symbols), "coverage_denominator_count": denominator_count, "row_coverage_ratio": row_cov, "net_amount_coverage_ratio": net_cov, "excluded_counts_json": json.dumps(excluded_counts, ensure_ascii=False, sort_keys=True)})
        abs_rows = mf_chunk[(mf_chunk["trade_date"] == obs_ts) & (mf_chunk["absnetmf_ma20_count"] == 20.0) & (mf_chunk["absnetmf_ma20"].notna())][["symbol", "absnetmf_ma20"]].copy()
        vol_day = full_price[full_price["date"] == obs_ts][["symbol", "vol20_annual"]].copy()
        joined = filtered_rows.merge(abs_rows, on="symbol", how="inner").merge(vol_day, on="symbol", how="left")
        if joined.empty:
            continue
        joined["observation_date"] = obs_ts
        joined["execution_date"] = exec_ts
        joined["month"] = obs_ts.to_period("M").to_timestamp()
        joined["gate_status"] = gate_status
        joined["industry_l1"] = joined["symbol"].map(_industry_map_for(industry_history, obs_ts, joined["symbol"].astype(str).str.lower().tolist())).fillna("UNKNOWN")
        joined = joined.sort_values(["absnetmf_ma20", "symbol"]).reset_index(drop=True)
        joined["rank_all"] = np.arange(1, len(joined) + 1)
        joined["liquidity_percentile"] = pd.to_numeric(joined["avg_turnover_20d"], errors="coerce").rank(method="average", pct=True)
        joined["volatility_percentile"] = pd.to_numeric(joined["vol20_annual"], errors="coerce").rank(method="average", pct=True)
        ranked_rows.append(joined[["observation_date", "month", "execution_date", "symbol", "rank_all", "absnetmf_ma20", "avg_turnover_20d", "avg_turnover_rate_20d", "vol20_annual", "liquidity_percentile", "volatility_percentile", "industry_l1", "gate_status"]].copy())
        if can_rebalance:
            sel = joined.head(10).copy()
            sel["rank"] = np.arange(1, len(sel) + 1)
            selected_rows.append(sel[["observation_date", "month", "execution_date", "symbol", "rank", "rank_all", "absnetmf_ma20", "avg_turnover_20d", "avg_turnover_rate_20d", "vol20_annual", "liquidity_percentile", "volatility_percentile", "industry_l1", "gate_status"]].copy())
    return (
        {"provider": provider, "initial_capital": float(initial_capital), "lot_size": int(lot_size), "costs": costs, "full_price": full_price},
        pd.DataFrame(schedule_rows),
        pd.concat(ranked_rows, ignore_index=True) if ranked_rows else pd.DataFrame(),
        pd.concat(selected_rows, ignore_index=True) if selected_rows else pd.DataFrame(),
        [pd.Timestamp(d).normalize() for d in trading_days],
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    context, schedule_df, ranked_df, selected_df, trading_days = _build_ranked_frames()
    base_summary = json.loads((SOURCE_DIR / "summary.json").read_text(encoding="utf-8"))
    base_perf = dict(base_summary["abs_perf"])
    base_selection_src = pd.read_csv(SOURCE_DIR / "abs_selection.csv")
    base_selection_src["observation_date"] = pd.to_datetime(base_selection_src["observation_date"], errors="coerce").dt.normalize()
    base_selection_src["execution_date"] = pd.to_datetime(base_selection_src["execution_date"], errors="coerce").dt.normalize()
    base_selection_src["symbol"] = base_selection_src["symbol"].astype(str).str.lower()
    base_daily = pd.read_csv(SOURCE_DIR / "abs_portfolio_daily.csv")
    base_trades = pd.read_csv(SOURCE_DIR / "abs_portfolio_trades.csv")
    base_nav = pd.read_csv(SOURCE_DIR / "abs_nav.csv")

    freq = base_selection_src.groupby("symbol").size().reset_index(name="selection_count").sort_values(["selection_count", "symbol"], ascending=[False, True]).reset_index(drop=True)
    total_selection_rows = int(len(base_selection_src))
    freq["selection_share"] = freq["selection_count"] / total_selection_rows if total_selection_rows > 0 else np.nan
    contrib_df, _ = _symbol_contribution(base_trades, base_daily, base_nav, context["initial_capital"])
    top10 = freq.head(10).merge(contrib_df[["symbol", "pnl_contribution", "return_points", "contribution_share_of_total_pnl"]], on="symbol", how="left").fillna(0.0)
    top3_symbols = freq.head(3)["symbol"].tolist()
    top5_symbols = freq.head(5)["symbol"].tolist()

    def build_variant_selection(excluded_symbols: list[str]) -> pd.DataFrame:
        excluded = {str(s).lower() for s in excluded_symbols}
        rows = []
        for _, grp in ranked_df.groupby("observation_date"):
            frame = grp.sort_values(["rank_all", "symbol"])
            frame = frame[~frame["symbol"].isin(excluded)].copy().head(10)
            if frame.empty:
                continue
            frame["rank"] = np.arange(1, len(frame) + 1)
            rows.append(frame[["observation_date", "month", "execution_date", "symbol", "rank"]].copy())
        return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["observation_date", "month", "execution_date", "symbol", "rank"])

    replay_symbols = sorted(set(ranked_df["symbol"].dropna().astype(str).str.lower().tolist()))
    replay_price = context["provider"].load_ohlcv_daily(replay_symbols, date.fromisoformat("2012-01-04"), date.fromisoformat("2026-03-16"), source="absnetmf_dynamic_audit_replay")
    stress_rows = [
        {
            "variant": "base",
            "excluded_symbols": "",
            "total_return": float(base_perf.get("total_return") or 0.0),
            "cagr": float(base_perf.get("cagr") or 0.0),
            "sharpe": float(base_perf.get("sharpe") or 0.0),
            "max_drawdown": float(base_perf.get("max_drawdown") or 0.0),
            "trades": int(base_perf.get("trades") or 0),
            "distinct_symbols": int(base_selection_src["symbol"].nunique()),
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
        stress_rows.append(
            {
                "variant": name,
                "excluded_symbols": ",".join(excluded),
                "total_return": float(perf.get("total_return") or 0.0),
                "cagr": float(perf.get("cagr") or 0.0),
                "sharpe": float(perf.get("sharpe") or 0.0),
                "max_drawdown": float(perf.get("max_drawdown") or 0.0),
                "trades": int(perf.get("trades") or 0),
                "distinct_symbols": int(variant_sel["symbol"].nunique()),
            }
        )
        variant_sel.to_csv(OUT_DIR / f"{name}_selection.csv", index=False, encoding="utf-8-sig")
        replay["portfolio_daily"].to_csv(OUT_DIR / f"{name}_portfolio_daily.csv", index=False, encoding="utf-8-sig")
        replay["portfolio_trades"].to_csv(OUT_DIR / f"{name}_portfolio_trades.csv", index=False, encoding="utf-8-sig")
        replay["nav"].to_csv(OUT_DIR / f"{name}_nav.csv", index=False, encoding="utf-8-sig")
    stress_df = pd.DataFrame(stress_rows)

    selected_profile = selected_df.merge(base_selection_src[["observation_date", "execution_date", "symbol", "rank"]], on=["observation_date", "execution_date", "symbol"], how="inner")
    industry_distribution = selected_profile.groupby("industry_l1", as_index=False).size().rename(columns={"size": "selection_count"}).sort_values(["selection_count", "industry_l1"], ascending=[False, True]).reset_index(drop=True)
    if not industry_distribution.empty:
        industry_distribution["selection_share"] = industry_distribution["selection_count"] / len(selected_profile)
    reuse_rows = []
    prev_set: set[str] | None = None
    for obs, grp in base_selection_src.groupby("observation_date"):
        current = set(grp["symbol"].tolist())
        reuse_count = len(current & prev_set) if prev_set is not None else np.nan
        reuse_rate = reuse_count / len(current) if prev_set is not None and len(current) > 0 else np.nan
        reuse_rows.append({"observation_date": obs, "selected_count": len(current), "reused_count_vs_prev": reuse_count, "reuse_rate_vs_prev": reuse_rate})
        prev_set = current
    reuse_df = pd.DataFrame(reuse_rows)
    annual_df = _annual_returns(base_nav)
    phase_df = _phase_metrics(base_nav)

    style_summary = {
        "selection_rows": int(len(selected_profile)),
        "distinct_symbols": int(selected_profile["symbol"].nunique()) if not selected_profile.empty else 0,
        "top10_selection_share": float(freq.head(10)["selection_count"].sum() / total_selection_rows) if total_selection_rows > 0 else 0.0,
        "liquidity_avg_turnover_20d_mean": float(pd.to_numeric(selected_profile["avg_turnover_20d"], errors="coerce").mean()) if not selected_profile.empty else None,
        "liquidity_avg_turnover_20d_median": float(pd.to_numeric(selected_profile["avg_turnover_20d"], errors="coerce").median()) if not selected_profile.empty else None,
        "liquidity_percentile_mean_vs_ranked_universe": float(pd.to_numeric(selected_profile["liquidity_percentile"], errors="coerce").mean()) if not selected_profile.empty else None,
        "liquidity_percentile_median_vs_ranked_universe": float(pd.to_numeric(selected_profile["liquidity_percentile"], errors="coerce").median()) if not selected_profile.empty else None,
        "vol20_annual_mean": float(pd.to_numeric(selected_profile["vol20_annual"], errors="coerce").mean()) if not selected_profile.empty else None,
        "vol20_annual_median": float(pd.to_numeric(selected_profile["vol20_annual"], errors="coerce").median()) if not selected_profile.empty else None,
        "volatility_percentile_mean_vs_ranked_universe": float(pd.to_numeric(selected_profile["volatility_percentile"], errors="coerce").mean()) if not selected_profile.empty else None,
        "volatility_percentile_median_vs_ranked_universe": float(pd.to_numeric(selected_profile["volatility_percentile"], errors="coerce").median()) if not selected_profile.empty else None,
        "reuse_rate_vs_prev_mean": float(pd.to_numeric(reuse_df["reuse_rate_vs_prev"], errors="coerce").mean()) if not reuse_df.empty else None,
        "reuse_rate_vs_prev_median": float(pd.to_numeric(reuse_df["reuse_rate_vs_prev"], errors="coerce").median()) if not reuse_df.empty else None,
        "top1_industry_share": float(industry_distribution["selection_share"].iloc[0]) if len(industry_distribution) >= 1 else None,
        "top3_industry_share": float(industry_distribution["selection_share"].head(3).sum()) if len(industry_distribution) >= 1 else None,
    }
    summary = {
        "base_performance": {"total_return": float(base_perf.get("total_return") or 0.0), "cagr": float(base_perf.get("cagr") or 0.0), "sharpe": float(base_perf.get("sharpe") or 0.0), "max_drawdown": float(base_perf.get("max_drawdown") or 0.0), "trades": int(base_perf.get("trades") or 0), "effective_execution_start_date": str(base_perf.get("effective_execution_start_date") or "")},
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
    top10.to_csv(OUT_DIR / "top10_frequency_contribution.csv", index=False, encoding="utf-8-sig")
    stress_df.to_csv(OUT_DIR / "stress_test_comparison.csv", index=False, encoding="utf-8-sig")
    selected_profile.to_csv(OUT_DIR / "selected_profile.csv", index=False, encoding="utf-8-sig")
    industry_distribution.to_csv(OUT_DIR / "industry_distribution.csv", index=False, encoding="utf-8-sig")
    selected_profile[["observation_date", "execution_date", "symbol", "industry_l1"]].to_csv(OUT_DIR / "industry_selected_rows.csv", index=False, encoding="utf-8-sig")
    selected_profile[["observation_date", "execution_date", "symbol", "avg_turnover_20d", "avg_turnover_rate_20d", "liquidity_percentile"]].to_csv(OUT_DIR / "liquidity_profile_selected_rows.csv", index=False, encoding="utf-8-sig")
    selected_profile[["observation_date", "execution_date", "symbol", "vol20_annual", "volatility_percentile"]].to_csv(OUT_DIR / "volatility_profile_selected_rows.csv", index=False, encoding="utf-8-sig")
    reuse_df.to_csv(OUT_DIR / "selection_reuse_by_month.csv", index=False, encoding="utf-8-sig")
    annual_df.to_csv(OUT_DIR / "annual_returns.csv", index=False, encoding="utf-8-sig")
    phase_df.to_csv(OUT_DIR / "phase_metrics.csv", index=False, encoding="utf-8-sig")
    ranked_df.to_csv(OUT_DIR / "ranked_rows.csv", index=False, encoding="utf-8-sig")
    report = "\n".join(
        [
            "# ABSNETMF_MA20 Dynamic PIT Audit",
            "",
            "## 结论",
            "",
            f"- corrected strict dynamic 基线: total_return={base_perf.get('total_return'):.4f}, cagr={base_perf.get('cagr'):.4f}, sharpe={base_perf.get('sharpe'):.4f}, max_drawdown={base_perf.get('max_drawdown'):.4f}",
            f"- 前10高频股票入选占比={freq.head(10)['selection_count'].sum() / total_selection_rows:.4f}, PnL贡献占比={float(top10['contribution_share_of_total_pnl'].sum()) if not top10.empty else 0.0:.4f}",
            f"- 去掉前3高频股票后: total_return={stress_df.loc[stress_df['variant'].eq('exclude_top3'), 'total_return'].iloc[0]:.4f}, sharpe={stress_df.loc[stress_df['variant'].eq('exclude_top3'), 'sharpe'].iloc[0]:.4f}",
            f"- 去掉前5高频股票后: total_return={stress_df.loc[stress_df['variant'].eq('exclude_top5'), 'total_return'].iloc[0]:.4f}, sharpe={stress_df.loc[stress_df['variant'].eq('exclude_top5'), 'sharpe'].iloc[0]:.4f}",
            f"- 风格暴露: 流动性分位均值={style_summary['liquidity_percentile_mean_vs_ranked_universe']:.4f}, 波动率分位均值={style_summary['volatility_percentile_mean_vs_ranked_universe']:.4f}, 月度名单复用率均值={style_summary['reuse_rate_vs_prev_mean']:.4f}",
        ]
    )
    (OUT_DIR / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
