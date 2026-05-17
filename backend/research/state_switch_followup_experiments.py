from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_INPUT_ROOT = Path(
    "outputs/studies/cn_stock_etf/cn_stock_style_industry_state_switch_shadow_v1"
)
DEFAULT_OUTPUT_ROOT = Path(
    "outputs/studies/cn_stock_etf/state_switch_followup_experiments_v1"
)
DEFAULT_VARIANT = "M1_STYLE_STATE"
DEFAULT_WINDOWS = ("1626", "1217", "1226", "recent_2526", "turn_202512_202604")


@dataclass(frozen=True)
class WindowInputs:
    window_key: str
    machine_dir: Path
    style: pd.DataFrame
    industry: pd.DataFrame
    rotation: pd.DataFrame
    entry: pd.DataFrame
    candidate: pd.DataFrame


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(path: Path | str) -> Path:
    raw = Path(path)
    if raw.is_absolute():
        return raw.resolve()
    return (_repo_root() / raw).resolve()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
        frame = frame.loc[frame["date"].notna()].copy()
        frame["date"] = frame["date"].dt.strftime("%Y-%m-%d")
    return frame


def load_window_inputs(input_root: Path, window_key: str, variant: str = DEFAULT_VARIANT) -> WindowInputs:
    machine_dir = input_root / window_key / variant / "machine"
    return WindowInputs(
        window_key=window_key,
        machine_dir=machine_dir,
        style=_read_csv(machine_dir / "style_state_daily.csv"),
        industry=_read_csv(machine_dir / "industry_health_daily.csv"),
        rotation=_read_csv(machine_dir / "rotation_pressure_daily.csv"),
        entry=_read_csv(machine_dir / "entry_candidate_pressure_daily.csv"),
        candidate=_read_csv(machine_dir / "candidate_pool_pressure_daily.csv"),
    )


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(0.0)


def _aggregate_by_label(
    frame: pd.DataFrame,
    *,
    label_col: str,
    extra_cols: tuple[str, ...] = (),
) -> pd.DataFrame:
    if frame.empty or label_col not in frame.columns:
        return pd.DataFrame()
    work = frame.copy()
    work[label_col] = work[label_col].fillna("unknown").astype(str)
    work["stock_ret"] = _numeric(work, "stock_ret")
    work["combo_ret"] = _numeric(work, "combo_ret")
    grouped = (
        work.groupby(label_col, dropna=False)
        .agg(
            days=("date", "count"),
            stock_ret_total=("stock_ret", "sum"),
            stock_ret_mean=("stock_ret", "mean"),
            combo_ret_total=("combo_ret", "sum"),
            combo_ret_mean=("combo_ret", "mean"),
        )
        .reset_index()
        .rename(columns={label_col: "label"})
    )
    for col in extra_cols:
        if col in work.columns:
            values = pd.to_numeric(work[col], errors="coerce")
            extra = values.groupby(work[label_col]).mean().rename(f"avg_{col}").reset_index()
            extra.rename(columns={label_col: "label"}, inplace=True)
            grouped = grouped.merge(extra, on="label", how="left")
    return grouped.sort_values(["stock_ret_total", "days"], ascending=[True, False]).reset_index(drop=True)


def _transition_forward_returns(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    label_col: str,
    horizons: tuple[int, ...] = (5, 20),
) -> pd.DataFrame:
    if left.empty or right.empty or label_col not in left.columns:
        return pd.DataFrame()
    daily = left.loc[:, ["date", label_col]].merge(
        right.loc[:, [c for c in ("date", "stock_ret", "combo_ret") if c in right.columns]],
        on="date",
        how="left",
    )
    daily[label_col] = daily[label_col].fillna("unknown").astype(str)
    daily["prev_label"] = daily[label_col].shift(1)
    changes = daily.loc[daily[label_col].ne(daily["prev_label"])].copy()
    changes = changes.loc[changes["prev_label"].notna()].copy()
    if changes.empty:
        return pd.DataFrame()
    stock_ret = _numeric(daily, "stock_ret")
    combo_ret = _numeric(daily, "combo_ret")
    rows: list[dict[str, Any]] = []
    for idx, row in changes.iterrows():
        out: dict[str, Any] = {
            "date": row["date"],
            "from_label": row["prev_label"],
            "to_label": row[label_col],
        }
        for horizon in horizons:
            start = int(idx) + 1
            end = min(int(idx) + 1 + horizon, len(daily))
            out[f"stock_forward_{horizon}d"] = float(stock_ret.iloc[start:end].sum()) if start < end else 0.0
            out[f"combo_forward_{horizon}d"] = float(combo_ret.iloc[start:end].sum()) if start < end else 0.0
        rows.append(out)
    return pd.DataFrame(rows)


def round2_market_state(inputs: WindowInputs) -> dict[str, pd.DataFrame]:
    merged = inputs.style.merge(inputs.rotation, on="date", how="left", suffixes=("", "_rotation"))
    by_state = _aggregate_by_label(
        merged,
        label_col="style_state_label",
        extra_cols=(
            "avg_ret20",
            "avg_ret60",
            "worst_drawdown60",
            "held_weak_ratio",
            "held_healthy_ratio",
        ),
    )
    transitions = _transition_forward_returns(inputs.style, inputs.rotation, label_col="style_state_label")
    transition_summary = _aggregate_by_label(
        transitions.rename(columns={"to_label": "label", "stock_forward_5d": "stock_ret", "combo_forward_5d": "combo_ret"}),
        label_col="label",
        extra_cols=(),
    )
    if not transition_summary.empty:
        transition_summary.rename(
            columns={
                "stock_ret_total": "transition_stock_forward_5d_total",
                "stock_ret_mean": "transition_stock_forward_5d_mean",
                "combo_ret_total": "transition_combo_forward_5d_total",
                "combo_ret_mean": "transition_combo_forward_5d_mean",
            },
            inplace=True,
        )
    return {
        "round2_market_state_by_label": by_state,
        "round2_market_state_transitions": transitions,
        "round2_market_state_transition_summary": transition_summary,
    }


def round3_industry_health(inputs: WindowInputs) -> dict[str, pd.DataFrame]:
    merged = inputs.industry.merge(inputs.rotation, on="date", how="left", suffixes=("", "_rotation"))
    by_market = _aggregate_by_label(
        merged,
        label_col="industry_market_health_label",
        extra_cols=(
            "industry_breadth_healthy",
            "industry_breadth_weak",
            "held_weak_ratio",
            "held_healthy_ratio",
        ),
    )
    rotation = inputs.rotation.copy()
    if not rotation.empty:
        rotation["held_weak_ratio_bucket"] = pd.cut(
            pd.to_numeric(rotation.get("held_weak_ratio"), errors="coerce"),
            bins=[-0.001, 0.0, 0.2, 0.5, 1.0],
            labels=["none", "low", "medium", "high"],
            include_lowest=True,
        ).astype(str)
    by_held_weak_bucket = _aggregate_by_label(
        rotation,
        label_col="held_weak_ratio_bucket",
        extra_cols=("held_weak_ratio", "held_healthy_ratio"),
    )
    return {
        "round3_industry_market_by_label": by_market,
        "round3_held_weak_ratio_buckets": by_held_weak_bucket,
    }


def round4_candidate_alignment(inputs: WindowInputs) -> dict[str, pd.DataFrame]:
    by_entry_alignment = _aggregate_by_label(
        inputs.entry,
        label_col="entry_vs_held_alignment_label",
        extra_cols=("entry_weak_ratio", "entry_healthy_ratio", "held_weak_ratio", "held_healthy_ratio"),
    )
    by_candidate_diagnosis = _aggregate_by_label(
        inputs.candidate,
        label_col="candidate_vs_held_diagnosis_label",
        extra_cols=(
            "candidate_weak_ratio",
            "candidate_healthy_ratio",
            "cash_blocked_stock_count",
            "held_weak_ratio",
            "held_healthy_ratio",
        ),
    )
    problem_days = pd.DataFrame()
    if not inputs.candidate.empty:
        labels = {"selection_health_mismatch", "deployment_blocked_with_weak_holdings", "signal_pool_weak"}
        problem_days = inputs.candidate.loc[
            inputs.candidate.get("candidate_vs_held_diagnosis_label", pd.Series(dtype=str)).isin(labels)
        ].copy()
    return {
        "round4_entry_alignment_by_label": by_entry_alignment,
        "round4_candidate_diagnosis_by_label": by_candidate_diagnosis,
        "round4_candidate_problem_days": problem_days,
    }


def _frame_records(frame: pd.DataFrame, limit: int = 12) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    clean = frame.head(limit).replace({pd.NA: None})
    return json.loads(clean.to_json(orient="records", force_ascii=False))


def _write_frame(path: Path, frame: pd.DataFrame) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# State Switch Follow-up Experiments V1",
        "",
        "## Scope",
        "",
        "- research_only: true",
        "- baseline_mutation: false",
        "- nav_recompute: false",
        "- source: existing M1/I1/R1/R2/R3 shadow CSV outputs",
        "",
        "## Windows",
        "",
    ]
    for window in summary["windows"]:
        lines.extend(
            [
                f"### {window['window_key']}",
                "",
                f"- round2 worst state labels: {window['round2']['worst_labels']}",
                f"- round2 transition count: {window['round2']['transition_count']}",
                f"- round3 weakest industry states: {window['round3']['worst_labels']}",
                f"- round3 weakest held weak-ratio buckets: {window['round3']['worst_buckets']}",
                f"- round4 weakest entry alignment labels: {window['round4']['worst_entry_labels']}",
                f"- round4 weakest candidate diagnosis labels: {window['round4']['worst_candidate_labels']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Interpretation Guardrails",
            "",
            "- These are shadow diagnostics, not causal AB results.",
            "- R3 candidate rows are rejected/diagnostic candidates, not a complete candidate pool.",
            "- Stock and combo returns are same-day grouped returns from existing shadow outputs.",
        ]
    )
    return "\n".join(lines) + "\n"


def _window_summary(window_key: str, outputs: dict[str, pd.DataFrame], input_dir: Path) -> dict[str, Any]:
    r2 = outputs["round2_market_state_by_label"]
    r2_transitions = outputs["round2_market_state_transitions"]
    r3_market = outputs["round3_industry_market_by_label"]
    r3_bucket = outputs["round3_held_weak_ratio_buckets"]
    r4_entry = outputs["round4_entry_alignment_by_label"]
    r4_candidate = outputs["round4_candidate_diagnosis_by_label"]
    return {
        "window_key": window_key,
        "input_dir": str(input_dir),
        "round2": {
            "worst_labels": _frame_records(r2, 5),
            "transition_count": int(len(r2_transitions)),
            "transition_summary": _frame_records(outputs["round2_market_state_transition_summary"], 8),
        },
        "round3": {
            "worst_labels": _frame_records(r3_market, 5),
            "worst_buckets": _frame_records(r3_bucket, 5),
        },
        "round4": {
            "worst_entry_labels": _frame_records(r4_entry, 8),
            "worst_candidate_labels": _frame_records(r4_candidate, 8),
            "problem_day_count": int(len(outputs["round4_candidate_problem_days"])),
        },
    }


def run_followup_experiments(
    *,
    input_root: Path = DEFAULT_INPUT_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    windows: tuple[str, ...] = DEFAULT_WINDOWS,
    variant: str = DEFAULT_VARIANT,
) -> dict[str, Any]:
    input_root = _resolve(input_root)
    output_root = _resolve(output_root)
    summary: dict[str, Any] = {
        "research_only": True,
        "baseline_mutation": False,
        "nav_recompute": False,
        "input_root": str(input_root),
        "variant": variant,
        "windows": [],
        "outputs": {},
    }
    for window_key in windows:
        inputs = load_window_inputs(input_root, window_key, variant)
        outputs: dict[str, pd.DataFrame] = {}
        outputs.update(round2_market_state(inputs))
        outputs.update(round3_industry_health(inputs))
        outputs.update(round4_candidate_alignment(inputs))
        window_dir = output_root / window_key
        for name, frame in outputs.items():
            summary["outputs"][f"{window_key}/{name}"] = _write_frame(window_dir / f"{name}.csv", frame)
        summary["windows"].append(_window_summary(window_key, outputs, inputs.machine_dir))
    output_root.mkdir(parents=True, exist_ok=True)
    summary_path = output_root / "summary.json"
    report_path = output_root / "summary.md"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_render_report(summary), encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    summary["report_path"] = str(report_path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="State-switch follow-up shadow experiments")
    parser.add_argument("--input-root", default=str(DEFAULT_INPUT_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--variant", default=DEFAULT_VARIANT)
    parser.add_argument("--windows", default=",".join(DEFAULT_WINDOWS))
    args = parser.parse_args()
    windows = tuple(item.strip() for item in args.windows.split(",") if item.strip())
    result = run_followup_experiments(
        input_root=Path(args.input_root),
        output_root=Path(args.output_root),
        windows=windows,
        variant=args.variant,
    )
    print(json.dumps({"summary_path": result["summary_path"], "report_path": result["report_path"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
