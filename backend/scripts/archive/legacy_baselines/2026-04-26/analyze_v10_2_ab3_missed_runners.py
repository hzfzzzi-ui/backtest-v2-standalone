from __future__ import annotations

import json
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
OPS_DIR = OPS_ROOT / "analyze_v10_2_ab3_missed_runners_20260322"

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


def _safe_json(text: str) -> dict[str, Any]:
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


def _load_daily(exp_id: str) -> pd.DataFrame:
    frame = pd.read_csv(_exp_dir(exp_id) / "portfolio_daily.csv", encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for col in ("positions_count", "gross_exposure"):
        frame[col] = pd.to_numeric(frame.get(col), errors="coerce").fillna(0.0)
    for col in ("market_state", "trade_mode", "market_state_5"):
        frame[col] = frame.get(col, "").fillna("").astype(str).str.strip()
    return frame[
        ["date", "market_state", "trade_mode", "market_state_5", "positions_count", "gross_exposure"]
    ].copy()


def _load_candidates(exp_id: str) -> pd.DataFrame:
    frame = pd.read_csv(_exp_dir(exp_id) / "portfolio_candidates.csv", encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.strip()
    frame["selected"] = frame["selected"].fillna(False).astype(bool)
    return frame


def _load_closed_trades(exp_id: str) -> pd.DataFrame:
    frame = pd.read_csv(_exp_dir(exp_id) / "portfolio_trades.csv", encoding="utf-8-sig")
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
            entry_date_actual=("date", "min"),
            buy_meta=("meta_json", "first"),
        )
    )
    sells = (
        frame[frame["side"] == "SELL"]
        .groupby(["symbol", "entry_date"], as_index=False)
        .agg(
            sell_value=("net_amount", "sum"),
            exit_reason=("reason_code", lambda s: s.iloc[-1]),
            exit_date=("date", "max"),
        )
    )
    closed = buys.merge(sells, on=["symbol", "entry_date"], how="inner")
    closed["pnl"] = closed["sell_value"] - closed["buy_cost"]
    closed["ret"] = closed["pnl"] / closed["buy_cost"].replace(0.0, np.nan)
    closed["ret"] = closed["ret"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    closed["hold_days"] = (closed["exit_date"] - closed["entry_date_actual"]).dt.days.astype(int)

    meta_series = closed["buy_meta"].apply(_safe_json)
    for col in FEATURE_COLUMNS:
        closed[col] = meta_series.apply(lambda payload, key=col: _safe_float(payload.get(key)))
    return closed


def _enrich_with_states(trades: pd.DataFrame, ref_daily: pd.DataFrame) -> pd.DataFrame:
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
    trades = trades.merge(entry_ref, on="entry_date_actual", how="left")
    trades = trades.merge(exit_ref, on="exit_date", how="left")
    return trades


def main() -> None:
    OPS_DIR.mkdir(parents=True, exist_ok=True)

    baseline_daily = _load_daily(BASELINE_EXP_ID)
    ab3_daily = _load_daily(AB3_EXP_ID)
    baseline_closed = _enrich_with_states(_load_closed_trades(BASELINE_EXP_ID), baseline_daily)
    ab3_closed = _enrich_with_states(_load_closed_trades(AB3_EXP_ID), baseline_daily)
    ab3_candidates = _load_candidates(AB3_EXP_ID)

    baseline_only = baseline_closed.merge(
        ab3_closed[["symbol", "entry_date"]],
        on=["symbol", "entry_date"],
        how="left",
        indicator=True,
    )
    baseline_only = baseline_only[baseline_only["_merge"] == "left_only"].drop(columns=["_merge"])

    positive_baseline_only = baseline_only[baseline_only["pnl"] > 0].copy()
    positive_pnl_total = float(positive_baseline_only["pnl"].sum()) if not positive_baseline_only.empty else 0.0

    # "早期趋势 runner" 用最小、可解释的定义：
    # 1) baseline-only
    # 2) 正收益
    # 3) 以 RISK_OFF_EXIT 收尾，说明是被趋势持有器收掉
    # 4) 持有 >=20 天 或 单笔收益 >=20%，排除一日噪声单
    runner_candidates = baseline_only[
        (baseline_only["pnl"] > 0)
        & (baseline_only["exit_reason"] == "RISK_OFF_EXIT")
        & ((baseline_only["hold_days"] >= 20) | (baseline_only["ret"] >= 0.20))
    ].copy()
    runner_candidates = runner_candidates.sort_values("pnl", ascending=False)
    runner_candidates["positive_pnl_share"] = runner_candidates["pnl"] / positive_pnl_total if positive_pnl_total else 0.0
    runner_candidates["positive_pnl_cum_share"] = runner_candidates["pnl"].cumsum() / positive_pnl_total if positive_pnl_total else 0.0

    ab3_buys = ab3_closed[["symbol", "entry_date", "entry_date_actual", "ret", "hold_days"]].rename(
        columns={
            "entry_date": "ab3_entry_signal_date",
            "entry_date_actual": "ab3_entry_date_actual",
            "ret": "ab3_ret",
            "hold_days": "ab3_hold_days",
        }
    )

    follow_rows: list[dict[str, Any]] = []
    for _, row in runner_candidates.iterrows():
        symbol = str(row["symbol"])
        entry_date = pd.Timestamp(row["entry_date_actual"]).normalize()
        exit_date = pd.Timestamp(row["exit_date"]).normalize()

        ab3_daily_row = ab3_daily.loc[ab3_daily["date"] == entry_date]
        if ab3_daily_row.empty:
            continue
        ab3_daily_row = ab3_daily_row.iloc[0]

        same_day_candidate = ab3_candidates.loc[
            (ab3_candidates["symbol"] == symbol) & (ab3_candidates["date"] == entry_date)
        ]
        later_symbol_trades = ab3_buys.loc[
            (ab3_buys["symbol"] == symbol) & (ab3_buys["ab3_entry_date_actual"] > entry_date)
        ].sort_values("ab3_entry_date_actual")
        during_baseline_hold = later_symbol_trades.loc[later_symbol_trades["ab3_entry_date_actual"] <= exit_date]

        if not same_day_candidate.empty:
            candidate_mode = "same_day_candidate_rejected"
            same_day_reject = str(same_day_candidate.iloc[0].get("reject_reason", ""))
            same_day_selected = bool(same_day_candidate.iloc[0]["selected"])
        else:
            candidate_mode = "same_day_signal_absent"
            same_day_reject = ""
            same_day_selected = False

        follow_rows.append(
            {
                "symbol": symbol,
                "entry_date_actual": entry_date,
                "exit_date": exit_date,
                "pnl": float(row["pnl"]),
                "ret": float(row["ret"]),
                "hold_days": int(row["hold_days"]),
                "entry_market_state": str(row["entry_market_state"]),
                "entry_trade_mode": str(row["entry_trade_mode"]),
                "positive_pnl_share": float(row["positive_pnl_share"]),
                "positive_pnl_cum_share": float(row["positive_pnl_cum_share"]),
                "ab3_trade_mode_on_entry": str(ab3_daily_row["trade_mode"]),
                "ab3_market_state_on_entry": str(ab3_daily_row["market_state"]),
                "ab3_positions_count_on_entry": int(ab3_daily_row["positions_count"]),
                "ab3_gross_exposure_on_entry": float(ab3_daily_row["gross_exposure"]),
                "candidate_mode": candidate_mode,
                "ab3_same_day_candidate": not same_day_candidate.empty,
                "ab3_same_day_selected": same_day_selected,
                "ab3_same_day_reject_reason": same_day_reject,
                "ab3_has_later_same_symbol_trade": not later_symbol_trades.empty,
                "ab3_has_trade_during_baseline_hold": not during_baseline_hold.empty,
                "ab3_first_later_entry_date": (
                    later_symbol_trades.iloc[0]["ab3_entry_date_actual"] if not later_symbol_trades.empty else pd.NaT
                ),
                "ab3_first_later_delay_days": (
                    int((later_symbol_trades.iloc[0]["ab3_entry_date_actual"] - entry_date).days)
                    if not later_symbol_trades.empty
                    else np.nan
                ),
            }
        )

    follow_df = pd.DataFrame(follow_rows).sort_values("pnl", ascending=False)
    follow_df.to_csv(OPS_DIR / "missed_runner_candidates.csv", index=False, encoding="utf-8-sig")

    mode_profile = (
        follow_df.groupby("candidate_mode", dropna=False)
        .agg(
            trades=("symbol", "count"),
            total_pnl=("pnl", "sum"),
            mean_ret=("ret", "mean"),
            pnl_share=("positive_pnl_share", "sum"),
        )
        .reset_index()
        .sort_values("total_pnl", ascending=False)
    )
    mode_profile.to_csv(OPS_DIR / "missed_runner_mode_profile.csv", index=False, encoding="utf-8-sig")

    feature_profile = pd.DataFrame(
        [
            {
                "cohort": "runner_candidates",
                **runner_candidates[FEATURE_COLUMNS + ["ret", "hold_days"]].mean(numeric_only=True).to_dict(),
            },
            {
                "cohort": "baseline_only_rest",
                **baseline_only.drop(runner_candidates.index)[FEATURE_COLUMNS + ["ret", "hold_days"]]
                .mean(numeric_only=True)
                .to_dict(),
            },
        ]
    )
    feature_profile.to_csv(OPS_DIR / "runner_feature_profile.csv", index=False, encoding="utf-8-sig")

    summary = {
        "baseline_exp_id": BASELINE_EXP_ID,
        "ab3_exp_id": AB3_EXP_ID,
        "baseline_only_trades": int(len(baseline_only)),
        "positive_baseline_only_trades": int(len(positive_baseline_only)),
        "runner_candidate_definition": {
            "pnl_gt_zero": True,
            "exit_reason": "RISK_OFF_EXIT",
            "hold_days_gte": 20,
            "or_ret_gte": 0.20,
        },
        "runner_candidate_count": int(len(runner_candidates)),
        "runner_candidate_positive_pnl_share": float(runner_candidates["pnl"].sum() / positive_pnl_total) if positive_pnl_total else 0.0,
        "runner_candidate_symbols": sanitize_json(
            follow_df[
                [
                    "symbol",
                    "entry_date_actual",
                    "pnl",
                    "ret",
                    "hold_days",
                    "candidate_mode",
                    "ab3_same_day_reject_reason",
                    "ab3_has_later_same_symbol_trade",
                    "ab3_first_later_delay_days",
                ]
            ].to_dict(orient="records")
        ),
        "mode_profile": sanitize_json(mode_profile.to_dict(orient="records")),
        "feature_profile": sanitize_json(feature_profile.to_dict(orient="records")),
    }
    (OPS_DIR / "summary.json").write_text(
        json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report = f"""# baseline-only 早期 trend runner 拆解

## 结论

- 我把 `baseline-only` 里的“本来就该做”的交易，收敛成了一组 **早期 trend runner 候选**：
  - `pnl > 0`
  - `exit_reason = RISK_OFF_EXIT`
  - `hold_days >= 20` 或 `ret >= 20%`
- 这组只有 **{len(runner_candidates)} 笔**，但贡献了 `baseline-only` 正收益的 **{(runner_candidates['pnl'].sum() / positive_pnl_total) if positive_pnl_total else 0.0:.2%}**
- 也就是说，`AB3` 真正漏掉的，不是一堆零散小盈利，而是一小批对净值差距有决定性贡献的早期 runner。

## 这些被漏掉的早期 runner 是谁

见：
- `missed_runner_candidates.csv`

它们的共同点：
- 几乎全部是 `BULL / TREND_MAIN` 入场
- 最终都由 `RISK_OFF_EXIT` 收割
- 其中前 4 笔已经贡献了 runner 候选总收益的大部分

## AB3 是怎么漏掉它们的

分成两类：

1. **同日有候选，但被现金/仓位挤掉**
   - 典型是 `SKIP_NO_CASH`
   - 代表：
     - `sz300394`
     - `sh601698`
2. **同日根本没进入 AB3 候选**
   - 不是 market state 没开闸
   - 而是这套 `AB3` 路径下，信号集合本身已经变了
   - 代表：
     - `sz002353`
     - `sz300418`
     - `sz002405`
     - `sh600519`
     - `sz000826`

也就是说：
- 有一部分是 **cash/slot 挤掉**
- 但更大一部分是 **AB3 根本没有拿到这批早期信号**

## AB3 会不会后来才追进去

多数不会。

在这 {len(runner_candidates)} 笔 runner 候选里：
- 只有极少数同名股票后来在 AB3 又出现
- 真正在 baseline 持有期内被 AB3 追进去的，几乎没有

这说明：
- `AB3` 不是“晚一点买同一批赢家”
- 更像是 **直接错过了这一批早期 runner**

## 这些 runner 的个股特征

见：
- `runner_feature_profile.csv`

对比 `baseline-only` 其余交易，runner 候选更像：
- `sector_strength` 更高
- `conditional_institution_proxy` 更高
- `volume_price_quality` 更高
- `atr_last` 也更高

这说明它们不是“保守、平滑、低波动”的便宜信号，反而更像：
- **板块更强**
- **机构/主导性更强**
- **启动时更有扩散潜力**

## 判断

`AB3` 比 baseline 少掉的关键收益，不是来自一堆普通小单，而是来自一小批：

- **较早进入**
- **BULL 主趋势里启动**
- **最终由 `RISK_OFF_EXIT` 收割**
- **板块和主导性都更强**

的 trend runner。

所以当前更准确的说法是：

**AB3 的问题，不只是“关太严”，而是它把主线最值钱的那批早期趋势 runner 漏掉了。**
"""
    (OPS_DIR / "report.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
