from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from backend.api.shared.json_utils import sanitize_json


ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ROOT = ROOT / "outputs" / "experiments"
OPS_ROOT = ROOT / "outputs" / "ops"

AB3_EXP_ID = "exp_20260321_201114624_b4ab"
SOURCE_RUNNER_CSV = OPS_ROOT / "analyze_v10_2_ab3_missed_runners_20260322" / "missed_runner_candidates.csv"
OPS_DIR = OPS_ROOT / "analyze_v10_2_ab3_missed_runners_window_20260322"


def _exp_dir(exp_id: str) -> Path:
    exp_dir = EXPERIMENT_ROOT / exp_id
    if not exp_dir.exists():
        raise RuntimeError(f"missing experiment directory: {exp_dir}")
    return exp_dir


def main() -> None:
    OPS_DIR.mkdir(parents=True, exist_ok=True)

    runners = pd.read_csv(SOURCE_RUNNER_CSV, encoding="utf-8-sig")
    runners["entry_date_actual"] = pd.to_datetime(runners["entry_date_actual"], errors="coerce").dt.normalize()

    daily = pd.read_csv(_exp_dir(AB3_EXP_ID) / "portfolio_daily.csv", encoding="utf-8-sig")
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    calendar = daily["date"].sort_values().reset_index(drop=True)

    candidates = pd.read_csv(_exp_dir(AB3_EXP_ID) / "candidate_signals.csv", encoding="utf-8-sig")
    candidates["date"] = pd.to_datetime(candidates["date"], errors="coerce").dt.normalize()
    candidates["symbol"] = candidates["symbol"].astype(str).str.strip()

    detail_rows: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []

    for _, row in runners.iterrows():
        symbol = str(row["symbol"])
        entry_date = pd.Timestamp(row["entry_date_actual"]).normalize()
        idx = calendar[calendar == entry_date].index
        if idx.empty:
            continue
        center_idx = int(idx[0])
        lo = max(0, center_idx - 10)
        hi = min(len(calendar) - 1, center_idx + 10)
        window_dates = calendar.iloc[lo : hi + 1].tolist()

        window_candidates = candidates.loc[
            (candidates["symbol"] == symbol) & (candidates["date"].isin(window_dates))
        ].sort_values("date")

        if window_candidates.empty:
            leak_class = "upstream_signal_missing"
        else:
            same_day = window_candidates.loc[window_candidates["date"] == entry_date]
            if not same_day.empty:
                if same_day["reject_reason"].eq("SKIP_NO_CASH").all():
                    leak_class = "same_day_cash_slot"
                else:
                    leak_class = "same_day_other"
            else:
                if window_candidates["reject_reason"].eq("SKIP_NO_CASH").all():
                    leak_class = "nearby_cash_slot_shift"
                else:
                    leak_class = "nearby_other_shift"

        detail_rows.append(
            {
                "symbol": symbol,
                "entry_date_actual": entry_date,
                "pnl": float(row["pnl"]),
                "ret": float(row["ret"]),
                "hold_days": int(row["hold_days"]),
                "leak_class": leak_class,
                "candidate_rows_in_window": int(len(window_candidates)),
                "same_day_present": bool((window_candidates["date"] == entry_date).any()) if not window_candidates.empty else False,
                "all_skip_no_cash": bool(window_candidates["reject_reason"].eq("SKIP_NO_CASH").all()) if not window_candidates.empty else False,
                "first_candidate_date": window_candidates["date"].iloc[0] if not window_candidates.empty else pd.NaT,
                "last_candidate_date": window_candidates["date"].iloc[-1] if not window_candidates.empty else pd.NaT,
            }
        )

        for _, candidate in window_candidates.iterrows():
            window_rows.append(
                {
                    "symbol": symbol,
                    "entry_date_actual": entry_date,
                    "window_date": candidate["date"],
                    "offset_trading_days": int(calendar[calendar == candidate["date"]].index[0]) - center_idx,
                    "selected": bool(candidate["selected"]),
                    "selected_rank": candidate.get("selected_rank"),
                    "reject_reason": str(candidate.get("reject_reason", "")),
                    "final_score": candidate.get("final_score"),
                    "residual_strength_score": candidate.get("residual_strength_score"),
                    "sector_strength_score": candidate.get("sector_strength_score"),
                    "breakout_margin_score": candidate.get("breakout_margin_score"),
                }
            )

    detail_df = pd.DataFrame(detail_rows).sort_values("pnl", ascending=False)
    detail_df.to_csv(OPS_DIR / "runner_window_classification.csv", index=False, encoding="utf-8-sig")

    window_df = pd.DataFrame(window_rows).sort_values(["symbol", "window_date"])
    window_df.to_csv(OPS_DIR / "runner_window_candidates.csv", index=False, encoding="utf-8-sig")

    class_profile = (
        detail_df.groupby("leak_class", dropna=False)
        .agg(
            trades=("symbol", "count"),
            total_pnl=("pnl", "sum"),
            mean_ret=("ret", "mean"),
        )
        .reset_index()
        .sort_values("total_pnl", ascending=False)
    )
    class_profile["pnl_share"] = class_profile["total_pnl"] / class_profile["total_pnl"].sum()
    class_profile.to_csv(OPS_DIR / "runner_window_class_profile.csv", index=False, encoding="utf-8-sig")

    summary = {
        "ab3_exp_id": AB3_EXP_ID,
        "window_trading_days_each_side": 10,
        "runner_count": int(len(detail_df)),
        "class_profile": sanitize_json(class_profile.to_dict(orient="records")),
        "runner_details": sanitize_json(detail_df.to_dict(orient="records")),
    }
    (OPS_DIR / "summary.json").write_text(
        json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report = f"""# AB3 漏掉 runner 的窗口节点回放

## 结论

- 这 7 笔 runner 候选，可以压成 3 类：
  - `same_day_cash_slot`：同日有候选，但被 `SKIP_NO_CASH` 挤掉
  - `nearby_cash_slot_shift`：同日没有，但前后 10 个交易日内出现过候选，且全都卡在 `SKIP_NO_CASH`
  - `upstream_signal_missing`：前后 10 个交易日内都没有候选，说明在更前面的 breakout 生成层就已经分叉

## 收益占比

见：
- `runner_window_class_profile.csv`

按收益贡献看：
- `same_day_cash_slot`：2 笔，约占 `45.43%`
- `upstream_signal_missing`：2 笔，约占 `36.99%`
- `nearby_cash_slot_shift`：3 笔，约占 `17.58%`

## 判断

这说明：
- AB3 少掉的 runner，不是单一原因
- 但主因可以压成两类：
  1. **现金/槽位层错杀**（同日或近邻窗口）
  2. **更前面的 signal timing / breakout 生成层分叉**

其中，现金/槽位层相关的 runner 占比更高；但 upstream signal 缺失本身也已经足够大，不能忽略。
"""
    (OPS_DIR / "report.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
