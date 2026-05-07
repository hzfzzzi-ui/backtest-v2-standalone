from __future__ import annotations

import copy
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.core.tools.experiment_runtime_access import run_experiment_sync

ROOT = Path(__file__).resolve().parents[3]
BASELINE_ROOT = ROOT / "outputs" / "baselines"
OPS_ROOT = ROOT / "outputs" / "ops"

BASELINE_V10_1_ID = "baseline_V10_1"
DATA_ROLE_V10_2 = "v2_canonical"
ASSET_SCOPE = "cn_a_equity"

WINDOWS = [
    {
        "window_key": "2016_2026",
        "label": "2016-2026",
        "start": "2016-03-01",
        "end": "2026-03-01",
    },
    {
        "window_key": "2007_2017",
        "label": "2007-2017",
        "start": "2007-01-04",
        "end": "2017-12-29",
    },
    {
        "window_key": "2007_2026",
        "label": "2007-2026",
        "start": "2007-01-04",
        "end": "2026-03-16",
    },
]

OPS_DIR = OPS_ROOT / "formal_comparison_baseline_v10_1_v10_2_three_windows_20260320"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid json root: {path}")
    return payload


def _base_config() -> dict[str, Any]:
    return _load_json(BASELINE_ROOT / BASELINE_V10_1_ID / "config.json")


def _build_config(source_cfg: dict[str, Any], *, start: str, end: str, data_role: str | None) -> dict[str, Any]:
    cfg = copy.deepcopy(source_cfg)
    universe = dict(cfg.get("universe") or {})
    universe["start"] = start
    universe["end"] = end
    universe["membership_mode"] = "PIT_DYNAMIC"
    cfg["universe"] = universe
    if data_role:
        data_source = dict(cfg.get("data_source") or {})
        data_source["data_role"] = data_role
        cfg["data_source"] = data_source
    else:
        cfg.pop("data_source", None)
    return cfg


def _run(cfg: dict[str, Any]) -> str:
    result = run_experiment_sync(
        {
            "preset": "single",
            "asset_scope": ASSET_SCOPE,
            "workbench_config": cfg,
        }
    )
    if not isinstance(result, dict):
        raise RuntimeError("runtime service returned non-dict result")
    exp_id = str(result.get("exp_id") or "").strip()
    status = str(result.get("status") or "").strip().upper()
    if not exp_id or status != "OK":
        raise RuntimeError(f"experiment run failed: {result!r}")
    return exp_id


def _exp_dir(exp_id: str) -> Path:
    path = ROOT / "outputs" / "experiments" / exp_id
    if not path.exists():
        raise RuntimeError(f"missing experiment dir: {path}")
    return path


def _extract_row(*, baseline_id: str, window_key: str, window_label: str, exp_id: str) -> dict[str, Any]:
    exp_dir = _exp_dir(exp_id)
    perf = _load_json(exp_dir / "perf.json")
    run_meta = _load_json(exp_dir / "run_meta.json")
    data = run_meta.get("data") if isinstance(run_meta.get("data"), dict) else {}
    consistency = run_meta.get("report_consistency") if isinstance(run_meta.get("report_consistency"), dict) else {}
    universe = run_meta.get("universe") if isinstance(run_meta.get("universe"), dict) else {}
    return {
        "window_key": window_key,
        "window_label": window_label,
        "baseline_id": baseline_id,
        "exp_id": exp_id,
        "window_start": data.get("start"),
        "window_end": data.get("end"),
        "data_role": consistency.get("data_role") or data.get("data_role") or "v1",
        "stocks_table": data.get("stocks_table") or "",
        "membership_mode": universe.get("membership_mode") or "",
        "membership_source": universe.get("membership_source") or "",
        "historical_membership_dynamic": universe.get("historical_membership_dynamic"),
        "total_return": perf.get("total_return"),
        "cagr": perf.get("cagr"),
        "sharpe": perf.get("sharpe"),
        "max_drawdown": perf.get("max_drawdown"),
        "trades": perf.get("trades"),
        "turnover": perf.get("turnover"),
        "effective_execution_start_date": perf.get("effective_execution_start_date"),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _fmt_num(value: Any, digits: int = 4) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return ""


def main() -> None:
    OPS_DIR.mkdir(parents=True, exist_ok=True)
    source_cfg = _base_config()
    all_rows: list[dict[str, Any]] = []
    delta_rows: list[dict[str, Any]] = []

    for window in WINDOWS:
        start = window["start"]
        end = window["end"]
        v101_exp = _run(_build_config(source_cfg, start=start, end=end, data_role=None))
        v102_exp = _run(_build_config(source_cfg, start=start, end=end, data_role=DATA_ROLE_V10_2))
        v101_row = _extract_row(
            baseline_id="baseline_V10_1",
            window_key=window["window_key"],
            window_label=window["label"],
            exp_id=v101_exp,
        )
        v102_row = _extract_row(
            baseline_id="baseline_V10_2",
            window_key=window["window_key"],
            window_label=window["label"],
            exp_id=v102_exp,
        )
        all_rows.extend([v101_row, v102_row])
        delta_rows.append(
            {
                "window_key": window["window_key"],
                "window_label": window["label"],
                "v10_1_exp_id": v101_exp,
                "v10_2_exp_id": v102_exp,
                "delta_total_return": (v102_row["total_return"] or 0.0) - (v101_row["total_return"] or 0.0),
                "delta_cagr": (v102_row["cagr"] or 0.0) - (v101_row["cagr"] or 0.0),
                "delta_sharpe": (v102_row["sharpe"] or 0.0) - (v101_row["sharpe"] or 0.0),
                "delta_max_drawdown": (v102_row["max_drawdown"] or 0.0) - (v101_row["max_drawdown"] or 0.0),
                "delta_trades": int((v102_row["trades"] or 0) - (v101_row["trades"] or 0)),
                "delta_turnover": (v102_row["turnover"] or 0.0) - (v101_row["turnover"] or 0.0),
            }
        )

    _write_csv(OPS_DIR / "performance_comparison.csv", all_rows)
    _write_csv(OPS_DIR / "delta_by_window.csv", delta_rows)

    summary = {
        "generated_at": datetime.now().isoformat(),
        "comparison_name": "baseline_V10.1_vs_V10.2_three_windows_formal",
        "windows": WINDOWS,
        "results": all_rows,
        "delta_by_window": delta_rows,
        "notes": [
            "This is a formal baseline comparison page, not a same-shell alpha comparison.",
            "Strategy logic stays at baseline_V10.1 on both sides.",
            "The primary material difference is data path: V10.1 uses legacy v1; V10.2 uses v2_canonical.",
        ],
    }
    with (OPS_DIR / "summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    report_lines = [
        "# baseline_V10.1 vs baseline_V10.2 三窗口正式对照",
        "",
        "## 结论",
        "",
        "- 这是正式 baseline 对照页，不是同壳 alpha 裁决页。",
        "- 两边策略逻辑都保持 `baseline_V10.1`，核心差异是数据路径：`V10.1=v1`，`V10.2=v2_canonical`。",
        "",
        "## 窗口对照",
        "",
        "| 窗口 | Baseline | Exp ID | Data Role | Total Return | CAGR | Sharpe | MaxDD | Trades | Turnover |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for window in WINDOWS:
        rows = [r for r in all_rows if r["window_key"] == window["window_key"]]
        for row in rows:
            report_lines.append(
                f"| {row['window_label']} | {row['baseline_id']} | `{row['exp_id']}` | `{row['data_role']}` | "
                f"{_fmt_num(row['total_return'])} | {_fmt_num(row['cagr'])} | {_fmt_num(row['sharpe'])} | "
                f"{_fmt_num(row['max_drawdown'])} | {row['trades']} | {_fmt_num(row['turnover'], 6)} |"
            )
        delta = next(d for d in delta_rows if d["window_key"] == window["window_key"])
        report_lines.extend(
            [
                "",
                f"### {window['label']} 差值 (V10.2 - V10.1)",
                "",
                f"- `total_return`: {_fmt_num(delta['delta_total_return'])}",
                f"- `cagr`: {_fmt_num(delta['delta_cagr'])}",
                f"- `sharpe`: {_fmt_num(delta['delta_sharpe'])}",
                f"- `max_drawdown`: {_fmt_num(delta['delta_max_drawdown'])}",
                f"- `trades`: {delta['delta_trades']}",
                f"- `turnover`: {_fmt_num(delta['delta_turnover'], 6)}",
                "",
            ]
        )

    (OPS_DIR / "report.md").write_text("\n".join(report_lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
