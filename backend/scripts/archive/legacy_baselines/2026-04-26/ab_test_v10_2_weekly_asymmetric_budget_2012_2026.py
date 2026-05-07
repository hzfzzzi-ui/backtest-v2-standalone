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
ASSET_SCOPE = "cn_a_equity"
OPS_DIR = OPS_ROOT / "ab_test_v10_2_weekly_asymmetric_budget_2012_2026_20260321"
REUSE_LEGACY_EXP_ID = "exp_20260321_055552903_8bd6"
REUSE_BUDGET5_EXP_ID = "exp_20260321_060110695_90ef"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid json root: {path}")
    return payload


def _source_config() -> dict[str, Any]:
    return _load_json(EXPERIMENT_ROOT / SOURCE_EXP_ID / "input_config.json")


def _build_config(source_cfg: dict[str, Any], *, variant: str) -> dict[str, Any]:
    cfg = copy.deepcopy(source_cfg)
    universe = dict(cfg.get("universe") or {})
    universe["membership_mode"] = "PIT_DYNAMIC"
    cfg["universe"] = universe
    data_source = dict(cfg.get("data_source") or {})
    data_source["data_role"] = "v2_canonical"
    cfg["data_source"] = data_source
    if variant == "legacy":
        cfg["regime_engine"] = {"engine": "ma200_legacy"}
        return cfg

    risk_budget_mode = "asymmetric_budget" if variant == "weekly_asymmetric" else "five_state"
    cfg["regime_engine"] = {
        "engine": "weekly_five_state",
        "benchmark": "000001.SH",
        "weekly_five_state": {
            "benchmark": "000001.SH",
            "ma_window": 120,
            "ma_slope_lookback": 20,
            "ret_short_window": 60,
            "ret_long_window": 120,
            "adx_window": 20,
            "weekly_rule": "W-FRI",
            "upgrade_confirm_weeks": 2,
            "downgrade_confirm_weeks": 1,
            "turn_weak_budget": 0.15,
            "risk_budget_mode": risk_budget_mode,
        },
        "fallback": {
            "on_feature_unavailable": "ma200_legacy",
            "required_blocks": [],
            "emit_feature_availability": True,
        },
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


def _extract_perf_row(*, variant: str, exp_id: str) -> dict[str, Any]:
    exp_dir = _exp_dir(exp_id)
    perf = _load_json(exp_dir / "perf.json")
    run_meta = _load_json(exp_dir / "run_meta.json")
    regime = run_meta.get("regime") if isinstance(run_meta.get("regime"), dict) else {}
    data = run_meta.get("data") if isinstance(run_meta.get("data"), dict) else {}
    consistency = run_meta.get("report_consistency") if isinstance(run_meta.get("report_consistency"), dict) else {}
    counters = run_meta.get("counters") if isinstance(run_meta.get("counters"), dict) else {}
    weekly_cfg = regime.get("weekly_five_state") if isinstance(regime.get("weekly_five_state"), dict) else {}
    return {
        "variant": variant,
        "exp_id": exp_id,
        "window_start": data.get("start"),
        "window_end": data.get("end"),
        "data_role": consistency.get("data_role") or data.get("data_role") or "v1",
        "regime_engine": regime.get("engine") or consistency.get("regime_engine") or "ma200_legacy",
        "risk_budget_mode": weekly_cfg.get("risk_budget_mode") or "",
        "membership_mode": (run_meta.get("universe") or {}).get("membership_mode"),
        "historical_membership_dynamic": (run_meta.get("universe") or {}).get("historical_membership_dynamic"),
        "total_return": perf.get("total_return"),
        "cagr": perf.get("cagr"),
        "sharpe": perf.get("sharpe"),
        "max_drawdown": perf.get("max_drawdown"),
        "trades": perf.get("trades"),
        "turnover": perf.get("turnover"),
        "effective_execution_start_date": perf.get("effective_execution_start_date"),
        "trade_mode_main_days": counters.get("trade_mode_main_days"),
        "trade_mode_light_days": counters.get("trade_mode_light_days"),
        "trade_mode_notrade_days": counters.get("trade_mode_notrade_days"),
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

    legacy_exp = REUSE_LEGACY_EXP_ID
    budget5_exp = REUSE_BUDGET5_EXP_ID
    asym_exp = _run(_build_config(source_cfg, variant="weekly_asymmetric"))

    rows = [
        _extract_perf_row(variant="V10.2_LEGACY", exp_id=legacy_exp),
        _extract_perf_row(variant="V10.2_WEEKLY_BUDGET5", exp_id=budget5_exp),
        _extract_perf_row(variant="V10.2_WEEKLY_ASYMMETRIC", exp_id=asym_exp),
    ]
    by_variant = {row["variant"]: row for row in rows}
    delta_asym_vs_5 = {
        "base_variant": "V10.2_WEEKLY_BUDGET5",
        "compare_variant": "V10.2_WEEKLY_ASYMMETRIC",
        "delta_total_return": float((by_variant["V10.2_WEEKLY_ASYMMETRIC"]["total_return"] or 0.0) - (by_variant["V10.2_WEEKLY_BUDGET5"]["total_return"] or 0.0)),
        "delta_cagr": float((by_variant["V10.2_WEEKLY_ASYMMETRIC"]["cagr"] or 0.0) - (by_variant["V10.2_WEEKLY_BUDGET5"]["cagr"] or 0.0)),
        "delta_sharpe": float((by_variant["V10.2_WEEKLY_ASYMMETRIC"]["sharpe"] or 0.0) - (by_variant["V10.2_WEEKLY_BUDGET5"]["sharpe"] or 0.0)),
        "delta_max_drawdown": float((by_variant["V10.2_WEEKLY_ASYMMETRIC"]["max_drawdown"] or 0.0) - (by_variant["V10.2_WEEKLY_BUDGET5"]["max_drawdown"] or 0.0)),
        "delta_trades": int((by_variant["V10.2_WEEKLY_ASYMMETRIC"]["trades"] or 0) - (by_variant["V10.2_WEEKLY_BUDGET5"]["trades"] or 0)),
    }

    summary = {
        "generated_at": datetime.now().isoformat(),
        "comparison_name": "v10_2_weekly_asymmetric_budget_minimal_ab",
        "source_exp_id": SOURCE_EXP_ID,
        "window": {
            "start": source_cfg.get("universe", {}).get("start"),
            "end": source_cfg.get("universe", {}).get("end"),
        },
        "variants": rows,
        "delta_asymmetric_vs_budget5": delta_asym_vs_5,
        "notes": [
            "This is a minimal AB on top of baseline_V10.2 shell.",
            "Raw five-state scoring stays unchanged.",
            "The only intended diff between weekly variants is risk_budget_mode.",
        ],
    }

    _write_csv(OPS_DIR / "performance_comparison.csv", rows)
    _write_csv(OPS_DIR / "delta_asymmetric_vs_budget5.csv", [delta_asym_vs_5])
    (OPS_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    report_lines = [
        "# Baseline V10.2: Weekly Asymmetric Budget Minimal AB",
        "",
        "## 结论",
        "",
        "- 这轮 AB 保持 weekly five-state 原始五档状态与打分不变。",
        "- 唯一 intended diff 是执行层 `risk_budget_mode`：`five_state` vs `asymmetric_budget`。",
        "",
        "## 对照表",
        "",
        "| Variant | Exp ID | Regime Engine | Budget Mode | Total Return | CAGR | Sharpe | MaxDD | Trades |",
        "|---|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        report_lines.append(
            f"| {row['variant']} | `{row['exp_id']}` | `{row['regime_engine']}` | `{row['risk_budget_mode'] or 'legacy'}` | "
            f"{_fmt_num(row['total_return'])} | {_fmt_num(row['cagr'])} | {_fmt_num(row['sharpe'])} | {_fmt_num(row['max_drawdown'])} | {row['trades']} |"
        )
    report_lines.extend(
        [
            "",
            "## Asymmetric - Budget5",
            "",
            f"- `total_return`: {_fmt_num(delta_asym_vs_5['delta_total_return'])}",
            f"- `cagr`: {_fmt_num(delta_asym_vs_5['delta_cagr'])}",
            f"- `sharpe`: {_fmt_num(delta_asym_vs_5['delta_sharpe'])}",
            f"- `max_drawdown`: {_fmt_num(delta_asym_vs_5['delta_max_drawdown'])}",
            f"- `trades`: {delta_asym_vs_5['delta_trades']}",
        ]
    )
    (OPS_DIR / "report.md").write_text("\n".join(report_lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
