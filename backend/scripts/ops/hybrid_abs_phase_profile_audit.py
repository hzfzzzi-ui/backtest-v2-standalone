from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from backend.api.shared.json_utils import sanitize_json


HYBRID_DIR = REPO / "outputs/ops/hybrid_regime_switch_v10_1_absnetmf_1226_20260320"
OUT_DIR = REPO / "outputs/ops/hybrid_abs_phase_profile_audit_20260320"


def _load_hybrid() -> pd.DataFrame:
    df = pd.read_csv(HYBRID_DIR / "hybrid_nav.csv")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in ("daily_return", "baseline_daily_return", "abs_daily_return"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["benchmark_regime_on"] = pd.to_numeric(df["benchmark_regime_on"], errors="coerce").fillna(0.0)
    return df.sort_values("date").reset_index(drop=True)


def _build_abs_segments(df: pd.DataFrame) -> pd.DataFrame:
    seg_id = (df["source"] != df["source"].shift(1)).cumsum()
    rows: list[dict[str, object]] = []
    for sid, g in df.groupby(seg_id):
        if g["source"].iloc[0] != "ABSNETMF_HALF_CASH":
            continue
        market_counts = g["market_state"].astype(str).value_counts().to_dict()
        trade_counts = g["trade_mode"].astype(str).value_counts().to_dict()
        abs_return = float((1.0 + g["abs_daily_return"]).prod() - 1.0)
        baseline_return = float((1.0 + g["baseline_daily_return"]).prod() - 1.0)
        rows.append(
            {
                "segment_id": int(sid),
                "start_date": g["date"].iloc[0].date().isoformat(),
                "end_date": g["date"].iloc[-1].date().isoformat(),
                "days": int(len(g)),
                "abs_return": abs_return,
                "hybrid_return": float((1.0 + g["daily_return"]).prod() - 1.0),
                "baseline_return": baseline_return,
                "baseline_minus_abs": baseline_return - abs_return,
                "benchmark_regime_on_ratio": float(g["benchmark_regime_on"].mean()),
                "dominant_market_state": max(market_counts, key=market_counts.get),
                "dominant_trade_mode": max(trade_counts, key=trade_counts.get),
                "market_state_counts_json": json.dumps(market_counts, ensure_ascii=False),
                "trade_mode_counts_json": json.dumps(trade_counts, ensure_ascii=False),
                "abs_daily_vol": float(g["abs_daily_return"].std(ddof=0)),
                "baseline_daily_vol": float(g["baseline_daily_return"].std(ddof=0)),
            }
        )
    return pd.DataFrame(rows).sort_values("start_date").reset_index(drop=True)


def _profile(frame: pd.DataFrame, group_col: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    return (
        frame.groupby(group_col, dropna=False)
        .agg(
            segments=("segment_id", "size"),
            positive=("abs_return", lambda s: int((s > 0).sum())),
            negative=("abs_return", lambda s: int((s < 0).sum())),
            mean_abs_return=("abs_return", "mean"),
            median_abs_return=("abs_return", "median"),
            mean_days=("days", "mean"),
            mean_baseline_return=("baseline_return", "mean"),
            mean_baseline_minus_abs=("baseline_minus_abs", "mean"),
            mean_benchmark_regime_on_ratio=("benchmark_regime_on_ratio", "mean"),
        )
        .reset_index()
        .sort_values("segments", ascending=False)
        .reset_index(drop=True)
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    hybrid = _load_hybrid()
    segments = _build_abs_segments(hybrid)
    pos = segments[segments["abs_return"] > 0].copy().sort_values("abs_return", ascending=False)
    neg = segments[segments["abs_return"] < 0].copy().sort_values("abs_return")

    profile_by_state = _profile(segments, "dominant_market_state")
    profile_by_mode = _profile(segments, "dominant_trade_mode")

    summary = sanitize_json(
        {
            "hybrid_run_id": "hybrid_regime_switch_v10_1_absnetmf_1226_20260320",
            "segment_definition": "contiguous ABSNETMF_HALF_CASH phases in the hybrid shell",
            "segment_count": int(len(segments)),
            "positive_count": int(len(pos)),
            "negative_count": int(len(neg)),
            "positive_mean_days": float(pos["days"].mean()) if not pos.empty else None,
            "negative_mean_days": float(neg["days"].mean()) if not neg.empty else None,
            "positive_mean_abs_return": float(pos["abs_return"].mean()) if not pos.empty else None,
            "negative_mean_abs_return": float(neg["abs_return"].mean()) if not neg.empty else None,
            "positive_mean_baseline_same_window": float(pos["baseline_return"].mean()) if not pos.empty else None,
            "negative_mean_baseline_same_window": float(neg["baseline_return"].mean()) if not neg.empty else None,
            "profile_by_state": profile_by_state.to_dict(orient="records"),
            "profile_by_mode": profile_by_mode.to_dict(orient="records"),
            "top_positive": pos.head(10).to_dict(orient="records"),
            "top_negative": neg.head(10).to_dict(orient="records"),
        }
    )

    report = "\n".join(
        [
            "# 混合壳中 ABS 阶段画像审计",
            "",
            "## 结论",
            "",
            f"- 按严格口径重算后，连续 ABS 阶段共 `{len(segments)}` 段，其中正收益 `{len(pos)}` 段，负收益 `{len(neg)}` 段。",
            "- 正收益段不是集中在少数极短窗口，但也没有形成明确、稳定的“所有熊市都能用”规律。",
            "- 负收益段更多出现在 `TREND_LIGHT` 主导的过渡下行阶段，也大量出现在长时间 `NO_TRADE/BEAR` 段。",
            "- 所以当前最可靠的判断是：ABSNETMF 不是通用非牛市替代器，只能在部分风险关闭较深、但资金扰动仍可控的区间发挥作用。",
            "",
            "## 事实",
            "",
            f"- 正收益段均值：`{float(pos['abs_return'].mean()):.4f}`；负收益段均值：`{float(neg['abs_return'].mean()):.4f}`",
            f"- 正收益段平均时长：`{float(pos['days'].mean()):.1f}` 天；负收益段平均时长：`{float(neg['days'].mean()):.1f}` 天",
            f"- 正收益段同窗 baseline 平均收益：`{float(pos['baseline_return'].mean()):.4f}`",
            f"- 负收益段同窗 baseline 平均收益：`{float(neg['baseline_return'].mean()):.4f}`",
            "",
            "## 风险边界",
            "",
            "- 这是混合壳内的连续 ABS 段画像，不是独立 ABS 策略全样本画像。",
            "- 这里的“可用/不可用”只表示在当前混合切换口径下的阶段表现，不等于可直接用于正式策略规则。",
        ]
    )

    segments.to_csv(OUT_DIR / "abs_segments.csv", index=False, encoding="utf-8-sig")
    pos.to_csv(OUT_DIR / "positive_segments.csv", index=False, encoding="utf-8-sig")
    neg.to_csv(OUT_DIR / "negative_segments.csv", index=False, encoding="utf-8-sig")
    profile_by_state.to_csv(OUT_DIR / "profile_by_state.csv", index=False, encoding="utf-8-sig")
    profile_by_mode.to_csv(OUT_DIR / "profile_by_mode.csv", index=False, encoding="utf-8-sig")
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "report.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
