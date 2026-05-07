from __future__ import annotations

import copy
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.core.tools.experiment_runtime_access import run_experiment_sync


ROOT = Path(__file__).resolve().parents[3]
OPS_ROOT = ROOT / "outputs" / "ops"
EXPERIMENT_ROOT = ROOT / "outputs" / "experiments"

SOURCE_EXP_ID = "exp_20260320_063727806_260c"
FORMAL_REFERENCE_EXP_ID = "exp_20260320_114417022_6e33"
WINDOW_START = "2017-06-01"
WINDOW_END = "2026-03-16"
ASSET_SCOPE = "cn_a_equity"
OPS_DIR = OPS_ROOT / "ab_test_v10_2_regime_high_conf_segment_20260320"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid json root: {path}")
    return payload


def _source_config() -> dict[str, Any]:
    return _load_json(EXPERIMENT_ROOT / SOURCE_EXP_ID / "input_config.json")


def _build_config(source_cfg: dict[str, Any], *, regime_engine: str) -> dict[str, Any]:
    cfg = copy.deepcopy(source_cfg)
    universe = dict(cfg.get("universe") or {})
    universe["start"] = WINDOW_START
    universe["end"] = WINDOW_END
    universe["membership_mode"] = "PIT_DYNAMIC"
    cfg["universe"] = universe
    data_source = dict(cfg.get("data_source") or {})
    data_source["data_role"] = "v2_canonical"
    cfg["data_source"] = data_source
    cfg["regime_engine"] = {
        "engine": regime_engine,
    }
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
        raise RuntimeError(f"experiment failed: {result!r}")
    return exp_id


def _exp_dir(exp_id: str) -> Path:
    exp_dir = EXPERIMENT_ROOT / exp_id
    if not exp_dir.exists():
        raise RuntimeError(f"missing experiment directory: {exp_dir}")
    return exp_dir


def _extract_row(*, variant: str, exp_id: str) -> dict[str, Any]:
    exp_dir = _exp_dir(exp_id)
    perf = _load_json(exp_dir / "perf.json")
    run_meta = _load_json(exp_dir / "run_meta.json")
    data = run_meta.get("data") if isinstance(run_meta.get("data"), dict) else {}
    consistency = run_meta.get("report_consistency") if isinstance(run_meta.get("report_consistency"), dict) else {}
    universe = run_meta.get("universe") if isinstance(run_meta.get("universe"), dict) else {}
    return {
        "variant": variant,
        "exp_id": exp_id,
        "window_start": data.get("start"),
        "window_end": data.get("end"),
        "data_role": consistency.get("data_role") or data.get("data_role") or "v1",
        "membership_mode": universe.get("membership_mode") or "",
        "historical_membership_dynamic": universe.get("historical_membership_dynamic"),
        "total_return": perf.get("total_return"),
        "cagr": perf.get("cagr"),
        "sharpe": perf.get("sharpe"),
        "max_drawdown": perf.get("max_drawdown"),
        "trades": perf.get("trades"),
        "turnover": perf.get("turnover"),
        "effective_execution_start_date": perf.get("effective_execution_start_date"),
    }


def _formal_window_basis() -> dict[str, Any]:
    daily_path = EXPERIMENT_ROOT / FORMAL_REFERENCE_EXP_ID / "portfolio_daily.csv"
    first_full = None
    last_fallback = None
    full_days = 0
    with daily_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            payload = json.loads(row.get("feature_availability_json") or "{}")
            required_ready = bool(payload.get("required_blocks_ready"))
            fallback_active = bool(payload.get("fallback_active"))
            if fallback_active:
                last_fallback = row["date"]
            if required_ready and not fallback_active:
                full_days += 1
                if first_full is None:
                    first_full = row["date"]
    return {
        "reference_formal_exp_id": FORMAL_REFERENCE_EXP_ID,
        "first_full_ready_date": first_full,
        "last_fallback_date": last_fallback,
        "chosen_window_start": WINDOW_START,
        "chosen_window_reason": "conservative_start_after_formal_feature_warmup",
        "reference_full_ready_days": full_days,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
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
    source_cfg = _source_config()

    legacy_exp = _run(_build_config(source_cfg, regime_engine="ma200_legacy"))
    formal_exp = _run(_build_config(source_cfg, regime_engine="market_regime_framework"))

    legacy_row = _extract_row(variant="V10.2_LEGACY", exp_id=legacy_exp)
    formal_row = _extract_row(variant="V10.2_FORMAL", exp_id=formal_exp)
    comparison_rows = [legacy_row, formal_row]
    delta = {
        "legacy_exp_id": legacy_exp,
        "formal_exp_id": formal_exp,
        "delta_total_return": (formal_row["total_return"] or 0.0) - (legacy_row["total_return"] or 0.0),
        "delta_cagr": (formal_row["cagr"] or 0.0) - (legacy_row["cagr"] or 0.0),
        "delta_sharpe": (formal_row["sharpe"] or 0.0) - (legacy_row["sharpe"] or 0.0),
        "delta_max_drawdown": (formal_row["max_drawdown"] or 0.0) - (legacy_row["max_drawdown"] or 0.0),
        "delta_trades": int((formal_row["trades"] or 0) - (legacy_row["trades"] or 0)),
        "delta_turnover": (formal_row["turnover"] or 0.0) - (legacy_row["turnover"] or 0.0),
    }
    basis = _formal_window_basis()

    summary = {
        "generated_at": datetime.now().isoformat(),
        "comparison_name": "v10_2_regime_high_conf_segment_minimal_ab",
        "source_exp_id": SOURCE_EXP_ID,
        "window": {"start": WINDOW_START, "end": WINDOW_END},
        "window_basis": basis,
        "variants": comparison_rows,
        "delta": delta,
        "notes": [
            "This is a minimal AB test on top of V10.2 shell.",
            "The only intended experimental difference is regime_engine.",
            "Window start is chosen conservatively after formal feature warmup.",
        ],
    }

    _write_csv(OPS_DIR / "performance_comparison.csv", comparison_rows)
    _write_csv(OPS_DIR / "delta.csv", [delta])
    (OPS_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    report_lines = [
        "# V10.2 Regime Minimal AB (High-Confidence Segment)",
        "",
        "## 结论",
        "",
        "- 这是一轮只改 `regime_engine` 的最小 AB。",
        f"- 窗口选在 `{WINDOW_START} ~ {WINDOW_END}`，原因是 formal regime 参考实验在 `{basis['first_full_ready_date']}` 起脱离 fallback；这里额外留出保守缓冲。",
        "",
        "## 对照表",
        "",
        "| Variant | Exp ID | Data Role | Membership | Total Return | CAGR | Sharpe | MaxDD | Trades | Turnover |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in comparison_rows:
        report_lines.append(
            f"| {row['variant']} | `{row['exp_id']}` | `{row['data_role']}` | `{row['membership_mode']}` | "
            f"{_fmt_num(row['total_return'])} | {_fmt_num(row['cagr'])} | {_fmt_num(row['sharpe'])} | "
            f"{_fmt_num(row['max_drawdown'])} | {row['trades']} | {_fmt_num(row['turnover'], 6)} |"
        )
    report_lines.extend(
        [
            "",
            "## Formal - Legacy",
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
