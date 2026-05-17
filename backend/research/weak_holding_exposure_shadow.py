from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_INPUT_ROOT = Path(
    "outputs/studies/cn_stock_etf/cn_stock_style_industry_state_switch_shadow_v1"
)
DEFAULT_OUTPUT_ROOT = Path(
    "outputs/studies/cn_stock_etf/weak_holding_exposure_shadow_v1"
)
DEFAULT_VARIANT = "M1_STYLE_STATE"
DEFAULT_WINDOWS = ("1626", "1217", "1226", "recent_2526", "turn_202512_202604")
DEFAULT_THRESHOLDS = (0.20, 0.35, 0.50)
DEFAULT_HORIZONS = (5, 20)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(path: Path | str) -> Path:
    raw = Path(path)
    if raw.is_absolute():
        return raw.resolve()
    return (_repo_root() / raw).resolve()


def _read_rotation_daily(input_root: Path, window_key: str, variant: str) -> pd.DataFrame:
    path = input_root / window_key / variant / "machine" / "rotation_pressure_daily.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.loc[frame["date"].notna()].copy()
    frame.sort_values("date", inplace=True)
    frame["date"] = frame["date"].dt.strftime("%Y-%m-%d")
    for col in ("held_stock_count", "held_weak_ratio", "held_healthy_ratio", "stock_ret", "combo_ret"):
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0.0)
    return frame.reset_index(drop=True)


def _forward_sum(series: pd.Series, idx: int, horizon: int) -> float:
    start = idx + 1
    end = min(idx + 1 + horizon, len(series))
    if start >= end:
        return 0.0
    return float(series.iloc[start:end].sum())


def build_trigger_detail(
    rotation_daily: pd.DataFrame,
    *,
    window_key: str,
    thresholds: tuple[float, ...] = DEFAULT_THRESHOLDS,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> pd.DataFrame:
    if rotation_daily.empty:
        return pd.DataFrame()
    work = rotation_daily.copy()
    stock_ret = pd.to_numeric(work.get("stock_ret"), errors="coerce").fillna(0.0)
    combo_ret = pd.to_numeric(work.get("combo_ret"), errors="coerce").fillna(0.0)
    rows: list[dict[str, Any]] = []
    for threshold in thresholds:
        trigger = (
            pd.to_numeric(work.get("held_stock_count"), errors="coerce").fillna(0.0).gt(0)
            & pd.to_numeric(work.get("held_weak_ratio"), errors="coerce").fillna(0.0).ge(threshold)
        )
        prev_trigger = trigger.shift(1, fill_value=False)
        episode_id = (trigger & ~prev_trigger).cumsum().where(trigger, 0).astype(int)
        for idx, row in work.loc[trigger].iterrows():
            out: dict[str, Any] = {
                "window_key": window_key,
                "threshold": threshold,
                "date": row["date"],
                "episode_id": int(episode_id.loc[idx]),
                "held_stock_count": int(row.get("held_stock_count", 0) or 0),
                "held_weak_ratio": float(row.get("held_weak_ratio", 0.0) or 0.0),
                "held_healthy_ratio": float(row.get("held_healthy_ratio", 0.0) or 0.0),
                "rotation_pressure_label": row.get("rotation_pressure_label", ""),
                "stock_ret": float(stock_ret.iloc[idx]),
                "combo_ret": float(combo_ret.iloc[idx]),
            }
            for horizon in horizons:
                out[f"stock_forward_{horizon}d"] = _forward_sum(stock_ret, int(idx), horizon)
                out[f"combo_forward_{horizon}d"] = _forward_sum(combo_ret, int(idx), horizon)
            rows.append(out)
    return pd.DataFrame(rows)


def summarize_triggers(
    trigger_detail: pd.DataFrame,
    *,
    window_key: str,
    thresholds: tuple[float, ...] = DEFAULT_THRESHOLDS,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for threshold in thresholds:
        sub = trigger_detail.loc[trigger_detail.get("threshold", pd.Series(dtype=float)).eq(threshold)].copy()
        if sub.empty:
            rows.append(
                {
                    "window_key": window_key,
                    "threshold": threshold,
                    "trigger_days": 0,
                    "episode_count": 0,
                    "avg_episode_length": 0.0,
                    "stock_ret_total": 0.0,
                    "stock_ret_mean": 0.0,
                    "combo_ret_total": 0.0,
                    "combo_ret_mean": 0.0,
                    "stock_forward_5d_mean": 0.0,
                    "stock_forward_20d_mean": 0.0,
                    "combo_forward_5d_mean": 0.0,
                    "combo_forward_20d_mean": 0.0,
                }
            )
            continue
        episode_lengths = sub.groupby("episode_id")["date"].count()
        row: dict[str, Any] = {
            "window_key": window_key,
            "threshold": threshold,
            "trigger_days": int(len(sub)),
            "episode_count": int(sub["episode_id"].nunique()),
            "avg_episode_length": float(episode_lengths.mean()) if not episode_lengths.empty else 0.0,
            "stock_ret_total": float(pd.to_numeric(sub["stock_ret"], errors="coerce").fillna(0.0).sum()),
            "stock_ret_mean": float(pd.to_numeric(sub["stock_ret"], errors="coerce").fillna(0.0).mean()),
            "combo_ret_total": float(pd.to_numeric(sub["combo_ret"], errors="coerce").fillna(0.0).sum()),
            "combo_ret_mean": float(pd.to_numeric(sub["combo_ret"], errors="coerce").fillna(0.0).mean()),
        }
        for horizon in DEFAULT_HORIZONS:
            for prefix in ("stock", "combo"):
                col = f"{prefix}_forward_{horizon}d"
                row[f"{col}_mean"] = float(pd.to_numeric(sub.get(col), errors="coerce").fillna(0.0).mean())
                row[f"{col}_median"] = float(pd.to_numeric(sub.get(col), errors="coerce").fillna(0.0).median())
        rows.append(row)
    return pd.DataFrame(rows)


def build_episode_detail(trigger_detail: pd.DataFrame) -> pd.DataFrame:
    if trigger_detail.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for (window_key, threshold, episode_id), group in trigger_detail.groupby(["window_key", "threshold", "episode_id"]):
        group = group.sort_values("date")
        rows.append(
            {
                "window_key": window_key,
                "threshold": threshold,
                "episode_id": int(episode_id),
                "start_date": group["date"].iloc[0],
                "end_date": group["date"].iloc[-1],
                "days": int(len(group)),
                "max_held_weak_ratio": float(group["held_weak_ratio"].max()),
                "avg_held_weak_ratio": float(group["held_weak_ratio"].mean()),
                "stock_ret_total": float(group["stock_ret"].sum()),
                "combo_ret_total": float(group["combo_ret"].sum()),
                "first_stock_forward_5d": float(group["stock_forward_5d"].iloc[0]) if "stock_forward_5d" in group else 0.0,
                "first_stock_forward_20d": float(group["stock_forward_20d"].iloc[0]) if "stock_forward_20d" in group else 0.0,
                "first_combo_forward_5d": float(group["combo_forward_5d"].iloc[0]) if "combo_forward_5d" in group else 0.0,
                "first_combo_forward_20d": float(group["combo_forward_20d"].iloc[0]) if "combo_forward_20d" in group else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values(["window_key", "threshold", "start_date"]).reset_index(drop=True)


def _write_csv(path: Path, frame: pd.DataFrame) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)


def _records(frame: pd.DataFrame, limit: int = 12) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return json.loads(frame.head(limit).to_json(orient="records", force_ascii=False))


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Weak Holding Exposure Shadow V1",
        "",
        "## Scope",
        "",
        "- research_only: true",
        "- baseline_mutation: false",
        "- nav_recompute: false",
        "- single_variable: held_weak_ratio",
        "",
        "## Window Summary",
        "",
    ]
    for window in summary["windows"]:
        lines.extend([f"### {window['window_key']}", ""])
        for item in window["threshold_summary"]:
            lines.append(
                "- threshold {threshold:.0%}: days={trigger_days}, episodes={episode_count}, "
                "stock_ret_total={stock_ret_total:.4f}, stock_fwd5_mean={stock_forward_5d_mean:.4f}, "
                "stock_fwd20_mean={stock_forward_20d_mean:.4f}".format(**item)
            )
        lines.append("")
    lines.extend(
        [
            "## Guardrails",
            "",
            "- This is a shadow diagnostic, not a sell rule.",
            "- Forward returns are measured from existing daily shadow output and are not an executable NAV counterfactual.",
            "- Thresholds are coarse fixed cuts, not optimized parameters.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_weak_holding_exposure_shadow(
    *,
    input_root: Path = DEFAULT_INPUT_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    windows: tuple[str, ...] = DEFAULT_WINDOWS,
    variant: str = DEFAULT_VARIANT,
    thresholds: tuple[float, ...] = DEFAULT_THRESHOLDS,
) -> dict[str, Any]:
    input_root = _resolve(input_root)
    output_root = _resolve(output_root)
    summary: dict[str, Any] = {
        "research_only": True,
        "baseline_mutation": False,
        "nav_recompute": False,
        "single_variable": "held_weak_ratio",
        "thresholds": list(thresholds),
        "input_root": str(input_root),
        "variant": variant,
        "windows": [],
        "outputs": {},
    }
    for window_key in windows:
        rotation_daily = _read_rotation_daily(input_root, window_key, variant)
        trigger_detail = build_trigger_detail(rotation_daily, window_key=window_key, thresholds=thresholds)
        threshold_summary = summarize_triggers(trigger_detail, window_key=window_key, thresholds=thresholds)
        episode_detail = build_episode_detail(trigger_detail)
        window_dir = output_root / window_key
        summary["outputs"][f"{window_key}/trigger_detail"] = _write_csv(window_dir / "trigger_detail.csv", trigger_detail)
        summary["outputs"][f"{window_key}/threshold_summary"] = _write_csv(window_dir / "threshold_summary.csv", threshold_summary)
        summary["outputs"][f"{window_key}/episode_detail"] = _write_csv(window_dir / "episode_detail.csv", episode_detail)
        summary["windows"].append(
            {
                "window_key": window_key,
                "input_rows": int(len(rotation_daily)),
                "threshold_summary": _records(threshold_summary, 10),
                "worst_episodes": _records(episode_detail.sort_values("stock_ret_total", ascending=True), 8),
            }
        )
    output_root.mkdir(parents=True, exist_ok=True)
    summary_path = output_root / "summary.json"
    report_path = output_root / "summary.md"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_render_report(summary), encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    summary["report_path"] = str(report_path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Weak holding exposure shadow")
    parser.add_argument("--input-root", default=str(DEFAULT_INPUT_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--variant", default=DEFAULT_VARIANT)
    parser.add_argument("--windows", default=",".join(DEFAULT_WINDOWS))
    parser.add_argument("--thresholds", default=",".join(str(item) for item in DEFAULT_THRESHOLDS))
    args = parser.parse_args()
    windows = tuple(item.strip() for item in args.windows.split(",") if item.strip())
    thresholds = tuple(float(item.strip()) for item in args.thresholds.split(",") if item.strip())
    result = run_weak_holding_exposure_shadow(
        input_root=Path(args.input_root),
        output_root=Path(args.output_root),
        windows=windows,
        variant=args.variant,
        thresholds=thresholds,
    )
    print(json.dumps({"summary_path": result["summary_path"], "report_path": result["report_path"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
