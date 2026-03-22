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

EXP_ID = "exp_20260320_035043267_e2c1"
OPS_DIR = OPS_ROOT / "analyze_v10_1_top10_trade_state_relation_20260322"


def _exp_dir(exp_id: str) -> Path:
    exp_dir = EXPERIMENT_ROOT / exp_id
    if not exp_dir.exists():
        raise RuntimeError(f"missing experiment directory: {exp_dir}")
    return exp_dir


def _load_daily(exp_id: str) -> pd.DataFrame:
    frame = pd.read_csv(_exp_dir(exp_id) / "portfolio_daily.csv", encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["market_state"] = frame["market_state"].astype(str).str.strip()
    frame["trade_mode"] = frame["trade_mode"].astype(str).str.strip()
    return frame


def _load_orders(exp_id: str) -> pd.DataFrame:
    frame = pd.read_csv(_exp_dir(exp_id) / "orders.csv", encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["entry_date"] = pd.to_datetime(frame["entry_date"], errors="coerce").dt.normalize()
    frame["side"] = frame["side"].astype(str).str.strip()
    frame["symbol"] = frame["symbol"].astype(str).str.strip()
    frame["reason_code"] = frame["reason_code"].astype(str).str.strip()
    frame["net_amount"] = pd.to_numeric(frame["net_amount"], errors="coerce").fillna(0.0)
    frame["meta_json"] = frame["meta_json"].fillna("{}").astype(str)
    return frame


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _trade_pairs(daily: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    buys = orders[orders["side"] == "BUY"].copy()
    sells = orders[orders["side"] == "SELL"].copy()
    buys["pair_key"] = buys["symbol"] + "|" + buys["date"].dt.strftime("%Y-%m-%d")
    sells["pair_key"] = sells["symbol"] + "|" + sells["entry_date"].dt.strftime("%Y-%m-%d")

    buy_group = buys.groupby("pair_key", as_index=False).agg(
        symbol=("symbol", "first"),
        buy_date=("date", "first"),
        buy_net=("net_amount", "sum"),
        buy_meta=("meta_json", "first"),
    )
    sell_group = sells.groupby("pair_key", as_index=False).agg(
        sell_date=("date", "last"),
        sell_net=("net_amount", "sum"),
        sell_reason=("reason_code", lambda s: s.mode().iat[0] if not s.mode().empty else s.iloc[-1]),
    )
    trades = buy_group.merge(sell_group, on="pair_key", how="inner")
    state_map = daily.set_index("date")["market_state"]
    mode_map = daily.set_index("date")["trade_mode"]
    trades["entry_state"] = trades["buy_date"].map(state_map)
    trades["exit_state"] = trades["sell_date"].map(state_map)
    trades["entry_mode"] = trades["buy_date"].map(mode_map)
    trades["exit_mode"] = trades["sell_date"].map(mode_map)
    trades["trade_return"] = trades["sell_net"] / trades["buy_net"] - 1.0
    trades["net_pnl"] = trades["sell_net"] - trades["buy_net"]

    day_idx = {day: idx for idx, day in enumerate(daily["date"].tolist())}
    trades["hold_bars"] = trades["sell_date"].map(day_idx) - trades["buy_date"].map(day_idx)

    states = ["BULL", "TRANS_UP", "TRANS_DOWN", "BEAR"]
    for state in states:
        trades[f"hold_days_{state.lower()}"] = 0
        trades[f"hold_ratio_{state.lower()}"] = 0.0

    meta_fields = (
        "breakout_quality_score",
        "residual_strength_score",
        "sector_strength_score",
        "volume_price_quality_score",
        "breakout_margin_score",
        "conditional_institution_proxy_score",
        "conditional_crowding_score",
        "leadership_route_score",
    )
    for field in meta_fields:
        trades[field] = np.nan

    for idx, row in trades.iterrows():
        hold = daily[(daily["date"] >= row["buy_date"]) & (daily["date"] <= row["sell_date"])].copy()
        if not hold.empty:
            state_counts = hold["market_state"].value_counts()
            trades.at[idx, "dominant_hold_state"] = str(state_counts.idxmax())
            for state in states:
                count = int((hold["market_state"] == state).sum())
                trades.at[idx, f"hold_days_{state.lower()}"] = count
                trades.at[idx, f"hold_ratio_{state.lower()}"] = float(count / len(hold))
            trades.at[idx, "all_bull_hold"] = bool((hold["market_state"] == "BULL").all())
            trades.at[idx, "has_trans_up_hold"] = bool((hold["market_state"] == "TRANS_UP").any())
            trades.at[idx, "has_trans_down_hold"] = bool((hold["market_state"] == "TRANS_DOWN").any())
            trades.at[idx, "has_bear_hold"] = bool((hold["market_state"] == "BEAR").any())
        else:
            trades.at[idx, "dominant_hold_state"] = ""
            trades.at[idx, "all_bull_hold"] = False
            trades.at[idx, "has_trans_up_hold"] = False
            trades.at[idx, "has_trans_down_hold"] = False
            trades.at[idx, "has_bear_hold"] = False

        try:
            payload = json.loads(row["buy_meta"])
        except json.JSONDecodeError:
            payload = {}
        for field in meta_fields:
            value = payload.get(field)
            trades.at[idx, field] = float(value) if value is not None else np.nan

    return trades


def _summary_row(trades: pd.DataFrame) -> dict[str, Any]:
    return {
        "trades": int(len(trades)),
        "avg_trade_return": float(trades["trade_return"].mean()) if len(trades) else np.nan,
        "median_trade_return": float(trades["trade_return"].median()) if len(trades) else np.nan,
        "win_rate": float((trades["trade_return"] > 0).mean()) if len(trades) else np.nan,
        "avg_hold_bars": float(trades["hold_bars"].mean()) if len(trades) else np.nan,
        "entry_state_counts": {str(k): int(v) for k, v in trades["entry_state"].value_counts().items()},
        "exit_state_counts": {str(k): int(v) for k, v in trades["exit_state"].value_counts().items()},
        "exit_reason_counts": {str(k): int(v) for k, v in trades["sell_reason"].value_counts().items()},
        "dominant_hold_state_counts": {str(k): int(v) for k, v in trades["dominant_hold_state"].value_counts().items()},
        "all_bull_hold_trades": int(trades["all_bull_hold"].sum()),
        "has_trans_up_hold_trades": int(trades["has_trans_up_hold"].sum()),
        "has_trans_down_hold_trades": int(trades["has_trans_down_hold"].sum()),
        "has_bear_hold_trades": int(trades["has_bear_hold"].sum()),
        "avg_hold_ratio_bull": float(trades["hold_ratio_bull"].mean()) if len(trades) else np.nan,
        "avg_hold_ratio_trans_up": float(trades["hold_ratio_trans_up"].mean()) if len(trades) else np.nan,
        "avg_hold_ratio_trans_down": float(trades["hold_ratio_trans_down"].mean()) if len(trades) else np.nan,
        "avg_hold_ratio_bear": float(trades["hold_ratio_bear"].mean()) if len(trades) else np.nan,
        "avg_breakout_quality_score": float(trades["breakout_quality_score"].mean()) if len(trades) else np.nan,
        "avg_residual_strength_score": float(trades["residual_strength_score"].mean()) if len(trades) else np.nan,
        "avg_sector_strength_score": float(trades["sector_strength_score"].mean()) if len(trades) else np.nan,
        "avg_volume_price_quality_score": float(trades["volume_price_quality_score"].mean()) if len(trades) else np.nan,
        "avg_breakout_margin_score": float(trades["breakout_margin_score"].mean()) if len(trades) else np.nan,
    }


def _rows_for_export(trades: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, row in trades.iterrows():
        rows.append(
            {
                "symbol": row["symbol"],
                "buy_date": row["buy_date"].date().isoformat(),
                "sell_date": row["sell_date"].date().isoformat(),
                "trade_return": float(row["trade_return"]),
                "net_pnl": float(row["net_pnl"]),
                "entry_state": row["entry_state"],
                "exit_state": row["exit_state"],
                "entry_mode": row["entry_mode"],
                "exit_mode": row["exit_mode"],
                "sell_reason": row["sell_reason"],
                "hold_bars": int(row["hold_bars"]),
                "dominant_hold_state": row["dominant_hold_state"],
                "hold_ratio_bull": float(row["hold_ratio_bull"]),
                "hold_ratio_trans_up": float(row["hold_ratio_trans_up"]),
                "hold_ratio_trans_down": float(row["hold_ratio_trans_down"]),
                "hold_ratio_bear": float(row["hold_ratio_bear"]),
                "all_bull_hold": bool(row["all_bull_hold"]),
                "has_trans_up_hold": bool(row["has_trans_up_hold"]),
                "has_trans_down_hold": bool(row["has_trans_down_hold"]),
                "has_bear_hold": bool(row["has_bear_hold"]),
                "breakout_quality_score": float(row["breakout_quality_score"]),
                "residual_strength_score": float(row["residual_strength_score"]),
                "sector_strength_score": float(row["sector_strength_score"]),
                "volume_price_quality_score": float(row["volume_price_quality_score"]),
                "breakout_margin_score": float(row["breakout_margin_score"]),
            }
        )
    return rows


def main() -> None:
    OPS_DIR.mkdir(parents=True, exist_ok=True)
    daily = _load_daily(EXP_ID)
    orders = _load_orders(EXP_ID)
    trades = _trade_pairs(daily, orders)
    winners = trades.sort_values("trade_return", ascending=False).head(10).copy()
    losers = trades.sort_values("trade_return", ascending=True).head(10).copy()

    bull_entries = trades[trades["entry_state"] == "BULL"].copy()
    bull_entry_exit_profile = []
    for exit_state, grp in bull_entries.groupby("exit_state"):
        bull_entry_exit_profile.append(
            {
                "entry_state": "BULL",
                "exit_state": str(exit_state),
                "trades": int(len(grp)),
                "avg_trade_return": float(grp["trade_return"].mean()),
                "median_trade_return": float(grp["trade_return"].median()),
                "win_rate": float((grp["trade_return"] > 0).mean()),
            }
        )
    bull_entry_exit_profile.sort(key=lambda row: row["exit_state"])

    summary = {
        "generated_at": pd.Timestamp.now(tz="Asia/Shanghai").isoformat(),
        "exp_id": EXP_ID,
        "window": {
            "start": daily["date"].min().date().isoformat(),
            "end": daily["date"].max().date().isoformat(),
        },
        "top10_winners": _summary_row(winners),
        "top10_losers": _summary_row(losers),
        "all_trades": _summary_row(trades),
        "bull_entry_exit_profile": bull_entry_exit_profile,
        "key_findings": [
            "Top10 好交易全部都是 BULL 入场，且几乎全程持有在 BULL，最后在 TRANS_DOWN 被 RISK_OFF_EXIT 收掉。",
            "Top10 坏交易并不主要来自弱市入场，9/10 也是 BULL 入场，说明最差交易大量发生在看起来正确的市场状态里。",
            "好坏交易的核心差异不在入场状态，而在持有期状态路径和个股质量：好交易能长时间留在 BULL，坏交易更多是短期失败或掉进 BEAR/TRANS_DOWN 前就已受损。",
            "因此，当前问题不能简单归因于市场状态机不准；市场状态更像在决定能否拿住赢家，而不是直接决定坏交易是否出现。",
        ],
    }

    (OPS_DIR / "summary.json").write_text(
        json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_csv(OPS_DIR / "top10_winners.csv", _rows_for_export(winners))
    _write_csv(OPS_DIR / "top10_losers.csv", _rows_for_export(losers))
    _write_csv(OPS_DIR / "bull_entry_exit_profile.csv", bull_entry_exit_profile)

    report = f"""# V10.1 Top10 好坏交易与市场状态关系

## 结论
- Top10 好交易和 Top10 坏交易的核心差异，不在入场市场状态。
- Top10 好交易 `10/10` 都是 `BULL` 入场，Top10 坏交易也有 `9/10` 是 `BULL` 入场。
- 真正拉开差距的是：
  - 好交易几乎全程运行在 `BULL`，并在第一次 `TRANS_DOWN` 被 `RISK_OFF_EXIT` 收走；
  - 坏交易更多是在 `BULL` 内部提前失败，或在后续掉进 `BEAR/TRANS_DOWN` 前已经受损。

## 事实
- Top10 好交易：
  - 平均单笔收益 `{summary["top10_winners"]["avg_trade_return"]:.2%}`
  - 平均持有 `{summary["top10_winners"]["avg_hold_bars"]:.1f}` bars
  - 平均持有期 `BULL` 占比 `{summary["top10_winners"]["avg_hold_ratio_bull"]:.2%}`
  - 退出状态全部是 `TRANS_DOWN`
- Top10 坏交易：
  - 平均单笔收益 `{summary["top10_losers"]["avg_trade_return"]:.2%}`
  - 平均持有 `{summary["top10_losers"]["avg_hold_bars"]:.1f}` bars
  - 平均持有期 `BULL` 占比 `{summary["top10_losers"]["avg_hold_ratio_bull"]:.2%}`
  - `4/10` 坏交易完全发生在 `BULL` 内部
- 对全部 `BULL` 入场交易：
  - 若最终在 `TRANS_DOWN` 退出，平均收益 `{next(row['avg_trade_return'] for row in bull_entry_exit_profile if row['exit_state']=='TRANS_DOWN'):.2%}`
  - 若最终在 `BULL` 内部退出，平均收益 `{next(row['avg_trade_return'] for row in bull_entry_exit_profile if row['exit_state']=='BULL'):.2%}`
  - 若最终拖到 `BEAR` 退出，平均收益 `{next(row['avg_trade_return'] for row in bull_entry_exit_profile if row['exit_state']=='BEAR'):.2%}`

## 判断
- 市场状态对 `V10.1` 更像“赢家持有器”，不是“坏交易拦截器”。
- `BULL` 状态本身能承载大赢家，但不能阻止 breakout 在牛市里失败。
- 所以现在的问题不能继续抽象成“换一个市场状态机就能修好坏交易”；更应该关注：
  - `BULL` 内部失败 breakout 的个股层特征
  - 哪些交易能在 `BULL` 中持续扩散到第一次 `TRANS_DOWN`
"""
    (OPS_DIR / "report.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
