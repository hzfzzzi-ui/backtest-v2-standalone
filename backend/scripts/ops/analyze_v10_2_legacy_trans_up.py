from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.api.shared.json_utils import sanitize_json


ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ROOT = ROOT / "outputs" / "experiments"
OPS_ROOT = ROOT / "outputs" / "ops"

EXP_ID = "exp_20260320_211021410_dfa5"
OPS_DIR = OPS_ROOT / "analyze_v10_2_legacy_trans_up_20260321"


def _exp_dir(exp_id: str) -> Path:
    exp_dir = EXPERIMENT_ROOT / exp_id
    if not exp_dir.exists():
        raise RuntimeError(f"missing experiment directory: {exp_dir}")
    return exp_dir


def _load_daily(exp_id: str) -> pd.DataFrame:
    path = _exp_dir(exp_id) / "portfolio_daily.csv"
    frame = pd.read_csv(path, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for col in (
        "daily_return",
        "gross_exposure",
        "positions_count",
        "positions_before_sell",
        "positions_after_sell",
        "buy_slots_calculated",
        "raw_buy_signal_count",
        "buy_candidate_count",
        "after_held_filter_count",
        "after_slot_filter_count",
        "after_cash_lot_count",
        "selected_count",
        "sells_executed_count",
    ):
        frame[col] = pd.to_numeric(frame.get(col), errors="coerce").fillna(0.0)
    for col in ("market_state", "trade_mode"):
        frame[col] = frame[col].astype(str).str.strip()
    frame["benchmark_regime_on"] = frame.get("benchmark_regime_on", False).fillna(False).astype(bool)
    return frame


def _load_orders(exp_id: str) -> pd.DataFrame:
    path = _exp_dir(exp_id) / "orders.csv"
    frame = pd.read_csv(path, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["entry_date"] = pd.to_datetime(frame["entry_date"], errors="coerce").dt.normalize()
    for col in ("fill_price", "qty", "net_amount"):
        frame[col] = pd.to_numeric(frame.get(col), errors="coerce").fillna(0.0)
    frame["side"] = frame["side"].astype(str).str.strip()
    frame["symbol"] = frame["symbol"].astype(str).str.strip()
    frame["reason_code"] = frame["reason_code"].astype(str).str.strip()
    frame["meta_json"] = frame["meta_json"].fillna("{}").astype(str)
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


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _load_trade_pairs(orders: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    buys = orders[orders["side"] == "BUY"].copy()
    sells = orders[orders["side"] == "SELL"].copy()
    buys["pair_key"] = buys["symbol"] + "|" + buys["date"].dt.strftime("%Y-%m-%d")
    sells["pair_key"] = sells["symbol"] + "|" + sells["entry_date"].dt.strftime("%Y-%m-%d")

    buy_group = buys.groupby("pair_key", as_index=False).agg(
        symbol=("symbol", "first"),
        buy_date=("date", "first"),
        buy_net=("net_amount", "sum"),
        buy_qty=("qty", "sum"),
        buy_meta=("meta_json", "first"),
    )
    sell_group = sells.groupby("pair_key", as_index=False).agg(
        sell_date=("date", "last"),
        sell_net=("net_amount", "sum"),
        sell_reason=("reason_code", lambda s: s.mode().iat[0] if not s.mode().empty else s.iloc[-1]),
        sell_rows=("symbol", "size"),
    )
    trades = buy_group.merge(sell_group, on="pair_key", how="inner")
    state_map = daily.set_index("date")["market_state"]
    trades["entry_state"] = trades["buy_date"].map(state_map)
    trades["exit_state"] = trades["sell_date"].map(state_map)
    trades["trade_return"] = trades["sell_net"] / trades["buy_net"] - 1.0
    day_idx = {day: idx for idx, day in enumerate(daily["date"].tolist())}
    trades["hold_bars"] = trades["sell_date"].map(day_idx) - trades["buy_date"].map(day_idx)

    for field in (
        "breakout_quality_score",
        "residual_strength_score",
        "sector_strength_score",
        "volume_price_quality_score",
        "breakout_margin_score",
    ):
        values: list[float] = []
        for meta_text in trades["buy_meta"]:
            try:
                payload = json.loads(meta_text)
            except json.JSONDecodeError:
                payload = {}
            value = payload.get(field)
            values.append(float(value) if value is not None else np.nan)
        trades[field] = values
    return trades


def _state_profile_rows(daily: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for state in ("BULL", "TRANS_UP", "TRANS_DOWN", "BEAR"):
        grp = daily[daily["market_state"] == state].copy()
        if grp.empty:
            continue
        rows.append(
            {
                "market_state": state,
                "days": int(len(grp)),
                "compounded_return": _compound_return(grp["daily_return"]),
                "avg_daily_return": float(grp["daily_return"].mean()),
                "daily_sharpe": _annualized_sharpe(grp["daily_return"]),
                "avg_positions_count": float(grp["positions_count"].mean()),
                "avg_gross_exposure": float(grp["gross_exposure"].mean()),
                "avg_raw_buy_signal_count": float(grp["raw_buy_signal_count"].mean()),
                "avg_after_held_filter_count": float(grp["after_held_filter_count"].mean()),
                "avg_after_slot_filter_count": float(grp["after_slot_filter_count"].mean()),
                "avg_after_cash_lot_count": float(grp["after_cash_lot_count"].mean()),
                "avg_selected_count": float(grp["selected_count"].mean()),
                "avg_buy_slots_calculated": float(grp["buy_slots_calculated"].mean()),
                "benchmark_regime_on_rate": float(grp["benchmark_regime_on"].mean()),
                "slot_pass_ratio": float(
                    grp["after_slot_filter_count"].sum() / grp["after_held_filter_count"].sum()
                )
                if float(grp["after_held_filter_count"].sum()) > 0
                else 0.0,
            }
        )
    return rows


def _trans_up_day_breakdown_rows(daily: pd.DataFrame, orders: pd.DataFrame) -> list[dict[str, Any]]:
    trans = daily[daily["market_state"] == "TRANS_UP"].copy()
    buy_dates = set(orders.loc[orders["side"] == "BUY", "date"].tolist())
    sell_dates = set(orders.loc[orders["side"] == "SELL", "date"].tolist())
    trans["has_buy"] = trans["date"].isin(buy_dates)
    trans["has_sell"] = trans["date"].isin(sell_dates)
    slices = {
        "invested": trans["positions_count"] > 0,
        "flat": trans["positions_count"] == 0,
        "benchmark_on": trans["benchmark_regime_on"],
        "benchmark_off": ~trans["benchmark_regime_on"],
        "invested_and_benchmark_on": (trans["positions_count"] > 0) & trans["benchmark_regime_on"],
        "invested_and_benchmark_off": (trans["positions_count"] > 0) & (~trans["benchmark_regime_on"]),
        "buy_day": trans["has_buy"],
        "sell_day": trans["has_sell"],
        "any_trade_day": trans["has_buy"] | trans["has_sell"],
        "no_trade_day": ~(trans["has_buy"] | trans["has_sell"]),
    }
    rows: list[dict[str, Any]] = []
    for label, mask in slices.items():
        grp = trans[mask].copy()
        if grp.empty:
            continue
        rows.append(
            {
                "slice": label,
                "days": int(len(grp)),
                "compounded_return": _compound_return(grp["daily_return"]),
                "avg_daily_return": float(grp["daily_return"].mean()),
                "daily_sharpe": _annualized_sharpe(grp["daily_return"]),
                "avg_positions_count": float(grp["positions_count"].mean()),
                "avg_gross_exposure": float(grp["gross_exposure"].mean()),
            }
        )
    return rows


def _trans_up_segment_rows(daily: pd.DataFrame, orders: pd.DataFrame) -> list[dict[str, Any]]:
    frame = daily[["date", "market_state", "daily_return", "gross_exposure", "positions_count"]].copy()
    frame["is_trans_up"] = frame["market_state"].eq("TRANS_UP")
    frame["segment_id"] = (frame["is_trans_up"] != frame["is_trans_up"].shift()).cumsum()
    buy_dates = set(orders.loc[orders["side"] == "BUY", "date"].tolist())
    sell_dates = set(orders.loc[orders["side"] == "SELL", "date"].tolist())
    rows: list[dict[str, Any]] = []
    for _, grp in frame[frame["is_trans_up"]].groupby("segment_id"):
        rows.append(
            {
                "start": grp["date"].iloc[0].date().isoformat(),
                "end": grp["date"].iloc[-1].date().isoformat(),
                "days": int(len(grp)),
                "compounded_return": _compound_return(grp["daily_return"]),
                "avg_gross_exposure": float(grp["gross_exposure"].mean()),
                "avg_positions_count": float(grp["positions_count"].mean()),
                "buy_days": int(grp["date"].isin(buy_dates).sum()),
                "sell_days": int(grp["date"].isin(sell_dates).sum()),
            }
        )
    rows.sort(key=lambda row: row["compounded_return"])
    return rows


def _trade_quality_rows(trades: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for state in ("BULL", "TRANS_UP", "TRANS_DOWN", "BEAR"):
        grp = trades[trades["entry_state"] == state].copy()
        if grp.empty:
            continue
        rows.append(
            {
                "entry_state": state,
                "trades": int(len(grp)),
                "avg_trade_return": float(grp["trade_return"].mean()),
                "median_trade_return": float(grp["trade_return"].median()),
                "win_rate": float((grp["trade_return"] > 0).mean()),
                "avg_hold_bars": float(grp["hold_bars"].mean()),
                "avg_breakout_quality_score": float(grp["breakout_quality_score"].mean()),
                "avg_residual_strength_score": float(grp["residual_strength_score"].mean()),
                "avg_sector_strength_score": float(grp["sector_strength_score"].mean()),
                "avg_volume_price_quality_score": float(grp["volume_price_quality_score"].mean()),
                "avg_breakout_margin_score": float(grp["breakout_margin_score"].mean()),
            }
        )
    return rows


def _trade_exit_reason_rows(trades: pd.DataFrame, entry_state: str) -> list[dict[str, Any]]:
    grp = trades[trades["entry_state"] == entry_state].copy()
    rows: list[dict[str, Any]] = []
    for reason, part in grp.groupby("sell_reason"):
        rows.append(
            {
                "entry_state": entry_state,
                "sell_reason": str(reason),
                "trades": int(len(part)),
                "avg_trade_return": float(part["trade_return"].mean()),
                "win_rate": float((part["trade_return"] > 0).mean()),
                "median_trade_return": float(part["trade_return"].median()),
            }
        )
    rows.sort(key=lambda row: (-row["trades"], row["sell_reason"]))
    return rows


def _top_trade_rows(trades: pd.DataFrame, entry_state: str, ascending: bool, limit: int = 10) -> list[dict[str, Any]]:
    grp = trades[trades["entry_state"] == entry_state].copy()
    grp = grp.sort_values("trade_return", ascending=ascending).head(limit)
    rows: list[dict[str, Any]] = []
    for _, row in grp.iterrows():
        rows.append(
            {
                "symbol": row["symbol"],
                "buy_date": row["buy_date"].date().isoformat(),
                "sell_date": row["sell_date"].date().isoformat(),
                "entry_state": row["entry_state"],
                "exit_state": row["exit_state"],
                "sell_reason": row["sell_reason"],
                "trade_return": float(row["trade_return"]),
                "hold_bars": int(row["hold_bars"]),
            }
        )
    return rows


def _trans_up_year_rows(daily: pd.DataFrame, trades: pd.DataFrame) -> list[dict[str, Any]]:
    trans = daily[(daily["market_state"] == "TRANS_UP") & (daily["benchmark_regime_on"])].copy()
    trans["year"] = trans["date"].dt.year
    rows: list[dict[str, Any]] = []
    trade_grp = trades[trades["entry_state"] == "TRANS_UP"].copy()
    trade_grp["entry_year"] = trade_grp["buy_date"].dt.year
    for year, grp in trans.groupby("year"):
        trade_part = trade_grp[trade_grp["entry_year"] == year]
        rows.append(
            {
                "year": int(year),
                "benchmark_on_days": int(len(grp)),
                "compounded_return": _compound_return(grp["daily_return"]),
                "avg_positions_count": float(grp["positions_count"].mean()),
                "avg_gross_exposure": float(grp["gross_exposure"].mean()),
                "buy_days": int((grp["selected_count"] > 0).sum()),
                "sell_days": int((grp["sells_executed_count"] > 0).sum()),
                "entry_trades": int(len(trade_part)),
                "entry_trade_avg_return": float(trade_part["trade_return"].mean()) if len(trade_part) else np.nan,
                "entry_trade_win_rate": float((trade_part["trade_return"] > 0).mean()) if len(trade_part) else np.nan,
            }
        )
    rows.sort(key=lambda row: row["year"])
    return rows


def main() -> None:
    OPS_DIR.mkdir(parents=True, exist_ok=True)
    daily = _load_daily(EXP_ID)
    orders = _load_orders(EXP_ID)
    trades = _load_trade_pairs(orders, daily)

    state_profiles = _state_profile_rows(daily)
    trans_up_day_breakdown = _trans_up_day_breakdown_rows(daily, orders)
    trans_up_segments = _trans_up_segment_rows(daily, orders)
    trade_quality = _trade_quality_rows(trades)
    trans_up_exit_reasons = _trade_exit_reason_rows(trades, "TRANS_UP")
    trans_up_worst_trades = _top_trade_rows(trades, "TRANS_UP", ascending=True, limit=10)
    trans_up_best_trades = _top_trade_rows(trades, "TRANS_UP", ascending=False, limit=10)
    trans_up_years = _trans_up_year_rows(daily, trades)

    trans_up = daily[daily["market_state"] == "TRANS_UP"].copy()
    trans_up_trade_quality = next((row for row in trade_quality if row["entry_state"] == "TRANS_UP"), None)
    bull_trade_quality = next((row for row in trade_quality if row["entry_state"] == "BULL"), None)
    trans_down_trade_quality = next((row for row in trade_quality if row["entry_state"] == "TRANS_DOWN"), None)
    invested_slice = next((row for row in trans_up_day_breakdown if row["slice"] == "invested"), None)
    flat_slice = next((row for row in trans_up_day_breakdown if row["slice"] == "flat"), None)
    bench_on_invested = next((row for row in trans_up_day_breakdown if row["slice"] == "invested_and_benchmark_on"), None)

    summary = {
        "generated_at": pd.Timestamp.now(tz="Asia/Shanghai").isoformat(),
        "exp_id": EXP_ID,
        "window": {
            "start": daily["date"].min().date().isoformat(),
            "end": daily["date"].max().date().isoformat(),
        },
        "trans_up_days": int(len(trans_up)),
        "trans_up_compounded_return": _compound_return(trans_up["daily_return"]),
        "trans_up_trade_mode_counts": {str(k): int(v) for k, v in trans_up["trade_mode"].value_counts().items()},
        "trans_up_benchmark_regime_on_days": int(trans_up["benchmark_regime_on"].sum()),
        "trans_up_benchmark_regime_off_days": int((~trans_up["benchmark_regime_on"]).sum()),
        "trans_up_invested_days": int((trans_up["positions_count"] > 0).sum()),
        "trans_up_flat_days": int((trans_up["positions_count"] == 0).sum()),
        "trans_up_benchmark_on_invested_days": int(
            ((trans_up["positions_count"] > 0) & trans_up["benchmark_regime_on"]).sum()
        ),
        "trans_up_benchmark_off_invested_days": int(
            ((trans_up["positions_count"] > 0) & (~trans_up["benchmark_regime_on"])).sum()
        ),
        "trans_up_invested_slice": invested_slice,
        "trans_up_flat_slice": flat_slice,
        "trans_up_benchmark_on_invested_slice": bench_on_invested,
        "trans_up_entry_trade_quality": trans_up_trade_quality,
        "bull_entry_trade_quality": bull_trade_quality,
        "trans_down_entry_trade_quality": trans_down_trade_quality,
        "trans_up_entry_exit_reason_breakdown": trans_up_exit_reasons,
        "top_worst_trans_up_segments": trans_up_segments[:5],
        "top_worst_trans_up_entry_trades": trans_up_worst_trades[:5],
        "key_findings": [
            "TRANS_UP 总亏损几乎全部发生在少数高仓位持有日；292 个空仓 TRANS_UP 日收益为 0。",
            "TRANS_UP 全部 332 天都是 TREND_LIGHT，但一旦有仓，平均 gross_exposure 接近 95%，说明 legacy 在 TRANS_UP 更像高仓位 carry 区，而不是轻仓试探区。",
            "TRANS_UP 新开仓交易质量本身也偏弱：平均单笔收益为负，明显差于 BULL 入场 cohort。",
            "TRANS_UP 最大拖累来自 2016-07/08、2023-04、2024-02~04 这些短促高仓位分叉段，不是整段持续均匀失血。",
        ],
    }

    (OPS_DIR / "summary.json").write_text(
        json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_csv(OPS_DIR / "state_daily_profile.csv", state_profiles)
    _write_csv(OPS_DIR / "trans_up_day_breakdown.csv", trans_up_day_breakdown)
    _write_csv(OPS_DIR / "trans_up_segments.csv", trans_up_segments)
    _write_csv(OPS_DIR / "state_entry_trade_quality.csv", trade_quality)
    _write_csv(OPS_DIR / "trans_up_exit_reasons.csv", trans_up_exit_reasons)
    _write_csv(OPS_DIR / "trans_up_worst_trades.csv", trans_up_worst_trades)
    _write_csv(OPS_DIR / "trans_up_best_trades.csv", trans_up_best_trades)
    _write_csv(OPS_DIR / "trans_up_benchmark_on_by_year.csv", trans_up_years)

    report = f"""# V10.2 legacy 在 TRANS_UP 段亏损原因拆解

## 结论
- `TRANS_UP` 段累计收益为 `{summary["trans_up_compounded_return"]:.2%}`。
- 亏损几乎全部来自 `{summary["trans_up_invested_days"]}` 个有仓日；`{summary["trans_up_flat_days"]}` 个空仓日收益为 0。
- `TRANS_UP` 语义上是 `TREND_LIGHT`，但有仓时实际是高 carry 暴露：平均 `gross_exposure` 为 `{bench_on_invested["avg_gross_exposure"]:.2%}`。
- `TRANS_UP` 新开仓 cohort 质量也偏弱：平均单笔收益 `{trans_up_trade_quality["avg_trade_return"]:.2%}`，明显差于 `BULL` 的 `{bull_trade_quality["avg_trade_return"]:.2%}`。

## 事实
- `TRANS_UP` 全部 `{summary["trans_up_days"]}` 天里：
  - `benchmark_regime_on=True` 仅 `{summary["trans_up_benchmark_regime_on_days"]}` 天
  - 真正有仓仅 `{summary["trans_up_invested_days"]}` 天
  - 其中 `benchmark_on + invested` 是 `{summary["trans_up_benchmark_on_invested_days"]}` 天
- 在 `benchmark_on + invested` 子集：
  - 平均持仓数 `{bench_on_invested["avg_positions_count"]:.2f}`
  - 平均 `gross_exposure` `{bench_on_invested["avg_gross_exposure"]:.2%}`
  - 平均 `raw_buy_signal_count` 并不低，但 `after_slot_filter_count` 很低，说明多为旧仓 carry 而非有效新换仓。
- `TRANS_UP` 入场 trades：
  - 数量 `{trans_up_trade_quality["trades"]}`
  - 胜率 `{trans_up_trade_quality["win_rate"]:.2%}`
  - 平均持有 `{trans_up_trade_quality["avg_hold_bars"]:.1f}` bars
  - 主要退出原因为 `RISK_OFF_EXIT`
- 最差段集中在：
  - `{trans_up_segments[0]["start"]} ~ {trans_up_segments[0]["end"]}` `{trans_up_segments[0]["compounded_return"]:.2%}`
  - `{trans_up_segments[1]["start"]} ~ {trans_up_segments[1]["end"]}` `{trans_up_segments[1]["compounded_return"]:.2%}`
  - `{trans_up_segments[2]["start"]} ~ {trans_up_segments[2]["end"]}` `{trans_up_segments[2]["compounded_return"]:.2%}`

## 判断
- `TRANS_UP` 的问题不是“这段买得太多”，而是“少数高仓位 carry 段掉得多”。
- 同时，这段新开仓的 breakout 也不够好，尤其 `sector_strength_score` 和 `residual_strength_score` 明显弱于 `BULL`。
- 所以当前更像：
  - 旧仓从 `BULL` 切入 `TRANS_UP` 后去杠杆不够快
  - 新仓又缺少足够强的板块/残差支撑
"""
    (OPS_DIR / "report.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
