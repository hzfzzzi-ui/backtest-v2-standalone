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

REUSE_BASELINE_EXP_ID = "exp_20260320_211021410_dfa5"
SOURCE_EXP_ID = REUSE_BASELINE_EXP_ID
ASSET_SCOPE = "cn_a_equity"
OPS_DIR = OPS_ROOT / "ab_test_v10_2_legacy_market_filter_ab_sequence_2012_2026_20260322"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid json root: {path}")
    return payload


def _source_config() -> dict[str, Any]:
    return _load_json(EXPERIMENT_ROOT / SOURCE_EXP_ID / "input_config.json")


def _base_cfg(source_cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = copy.deepcopy(source_cfg)
    universe = dict(cfg.get("universe") or {})
    universe["membership_mode"] = "PIT_DYNAMIC"
    cfg["universe"] = universe
    data_source = dict(cfg.get("data_source") or {})
    data_source["data_role"] = "v2_canonical"
    cfg["data_source"] = data_source
    cfg["regime_engine"] = {"engine": "ma200_legacy"}
    pos_risk = dict(cfg.get("position_risk") or {})
    market_filter = dict(pos_risk.get("market_filter") or {})
    market_filter["enabled"] = True
    market_filter.setdefault("bull_multiplier", 1.8)
    market_filter.setdefault("light_multiplier", 0.6)
    market_filter.setdefault("slope_ma_period", 50)
    market_filter.setdefault("slope_window", 10)
    pos_risk["market_filter"] = market_filter
    cfg["position_risk"] = pos_risk
    return cfg


def _build_config(source_cfg: dict[str, Any], *, variant: str) -> dict[str, Any]:
    cfg = _base_cfg(source_cfg)
    market_filter = dict(cfg["position_risk"]["market_filter"])
    market_filter["long_ma_window"] = 200
    market_filter["trans_down_multiplier"] = 0.5
    market_filter["trans_up_multiplier"] = 0.25
    market_filter["freeze_trans_up_entries"] = False

    if variant == "ab2":
        market_filter["freeze_trans_up_entries"] = True
    elif variant == "ab3":
        market_filter["freeze_trans_up_entries"] = True
        market_filter["long_ma_window"] = 160
    elif variant != "ab1":
        raise ValueError(f"unsupported variant: {variant}")

    cfg["position_risk"]["market_filter"] = market_filter
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
    input_cfg = _load_json(exp_dir / "input_config.json")
    consistency = run_meta.get("report_consistency") if isinstance(run_meta.get("report_consistency"), dict) else {}
    counters = run_meta.get("counters") if isinstance(run_meta.get("counters"), dict) else {}
    market_filter = consistency.get("market_filter") if isinstance(consistency.get("market_filter"), dict) else {}
    if not market_filter:
        market_filter = (
            (input_cfg.get("position_risk") or {}).get("market_filter")
            if isinstance((input_cfg.get("position_risk") or {}).get("market_filter"), dict)
            else {}
        )
    return {
        "variant": variant,
        "exp_id": exp_id,
        "window_start": (run_meta.get("data") or {}).get("start"),
        "window_end": (run_meta.get("data") or {}).get("end"),
        "data_role": consistency.get("data_role") or ((run_meta.get("data") or {}).get("data_role")) or "v1",
        "regime_engine": consistency.get("regime_engine") or "ma200_legacy",
        "long_ma_window": market_filter.get("long_ma_window"),
        "trans_down_multiplier": market_filter.get("trans_down_multiplier"),
        "trans_up_multiplier": market_filter.get("trans_up_multiplier"),
        "freeze_trans_up_entries": market_filter.get("freeze_trans_up_entries"),
        "total_return": perf.get("total_return"),
        "cagr": perf.get("cagr"),
        "sharpe": perf.get("sharpe"),
        "max_drawdown": perf.get("max_drawdown"),
        "trades": perf.get("trades"),
        "turnover": perf.get("turnover"),
        "effective_execution_start_date": perf.get("effective_execution_start_date"),
        "market_filter_bull_days": counters.get("market_filter_bull_days"),
        "market_filter_bear_days": counters.get("market_filter_bear_days"),
        "market_state_trans_down_days": counters.get("market_state_trans_down_days"),
        "market_state_trans_up_days": counters.get("market_state_trans_up_days"),
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
    ab1_exp = _run(_build_config(source_cfg, variant="ab1"))
    ab2_exp = _run(_build_config(source_cfg, variant="ab2"))
    ab3_exp = _run(_build_config(source_cfg, variant="ab3"))

    rows = [
        _extract_perf_row(variant="BASELINE_V10.2_LEGACY", exp_id=REUSE_BASELINE_EXP_ID),
        _extract_perf_row(variant="AB1_SPLIT_MULTIPLIER", exp_id=ab1_exp),
        _extract_perf_row(variant="AB2_TRANS_UP_FREEZE", exp_id=ab2_exp),
        _extract_perf_row(variant="AB3_LONG_MA_160", exp_id=ab3_exp),
    ]
    baseline = rows[0]
    deltas: list[dict[str, Any]] = []
    for row in rows[1:]:
        deltas.append(
            {
                "base_variant": baseline["variant"],
                "compare_variant": row["variant"],
                "delta_total_return": float((row["total_return"] or 0.0) - (baseline["total_return"] or 0.0)),
                "delta_cagr": float((row["cagr"] or 0.0) - (baseline["cagr"] or 0.0)),
                "delta_sharpe": float((row["sharpe"] or 0.0) - (baseline["sharpe"] or 0.0)),
                "delta_max_drawdown": float((row["max_drawdown"] or 0.0) - (baseline["max_drawdown"] or 0.0)),
                "delta_trades": int((row["trades"] or 0) - (baseline["trades"] or 0)),
            }
        )

    summary = {
        "generated_at": datetime.now().isoformat(),
        "comparison_name": "v10_2_legacy_market_filter_ab_sequence",
        "source_exp_id": SOURCE_EXP_ID,
        "window": {
            "start": source_cfg.get("universe", {}).get("start"),
            "end": source_cfg.get("universe", {}).get("end"),
        },
        "assumptions": {
            "ab1": {
                "trans_down_multiplier": 0.5,
                "trans_up_multiplier": 0.25,
                "freeze_trans_up_entries": False,
                "long_ma_window": 200,
            },
            "ab2": {
                "trans_down_multiplier": 0.5,
                "trans_up_multiplier": 0.25,
                "freeze_trans_up_entries": True,
                "long_ma_window": 200,
            },
            "ab3": {
                "trans_down_multiplier": 0.5,
                "trans_up_multiplier": 0.25,
                "freeze_trans_up_entries": True,
                "long_ma_window": 160,
            },
        },
        "variants": rows,
        "delta_vs_baseline": deltas,
        "notes": [
            "AB1 only splits TRANS_UP / TRANS_DOWN multipliers.",
            "AB2 adds TRANS_UP freeze for new entries on top of AB1.",
            "AB3 changes legacy long_ma_window from 200 to 160 on top of AB2.",
        ],
    }

    _write_csv(OPS_DIR / "performance_comparison.csv", rows)
    _write_csv(OPS_DIR / "delta_vs_baseline.csv", deltas)
    (OPS_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    report_lines = [
        "# Baseline V10.2 Legacy Market Filter AB Sequence",
        "",
        "## 结论",
        "",
        "- 这轮按顺序执行 `AB1 -> AB2 -> AB3`。",
        "- 基线保持 `ma200_legacy` 与个股主线不变。",
        "- 唯一 intended diff 是 legacy market filter 的三个最小旋钮。",
        "",
        "## 对照表",
        "",
        "| Variant | Exp ID | long_ma_window | TD mult | TU mult | Freeze TU Entries | Total Return | CAGR | Sharpe | MaxDD | Trades |",
        "|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        report_lines.append(
            f"| {row['variant']} | `{row['exp_id']}` | {row['long_ma_window']} | "
            f"{row['trans_down_multiplier']} | {row['trans_up_multiplier']} | "
            f"`{row['freeze_trans_up_entries']}` | {_fmt_num(row['total_return'])} | "
            f"{_fmt_num(row['cagr'])} | {_fmt_num(row['sharpe'])} | "
            f"{_fmt_num(row['max_drawdown'])} | {row['trades']} |"
        )
    report_lines.extend(
        [
            "",
            "## Delta vs Baseline",
            "",
            "| Compare | Delta Total Return | Delta CAGR | Delta Sharpe | Delta MaxDD | Delta Trades |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for delta in deltas:
        report_lines.append(
            f"| {delta['compare_variant']} | {_fmt_num(delta['delta_total_return'])} | "
            f"{_fmt_num(delta['delta_cagr'])} | {_fmt_num(delta['delta_sharpe'])} | "
            f"{_fmt_num(delta['delta_max_drawdown'])} | {delta['delta_trades']} |"
        )
    (OPS_DIR / "report.md").write_text("\n".join(report_lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
