from __future__ import annotations

import copy
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from backend.core.tools.experiment_runtime_access import run_experiment_sync


ROOT = Path(__file__).resolve().parents[3]
OPS_ROOT = ROOT / "outputs" / "ops"
EXPERIMENT_ROOT = ROOT / "outputs" / "experiments"

SOURCE_EXP_ID = "exp_20260322_004633191_b83c"
ASSET_SCOPE = "cn_a_equity"
OPS_DIR = OPS_ROOT / "ab_test_v10_2_bull_breakout_quality_veto_2012_2026_20260322"


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
    return cfg


def _build_config(source_cfg: dict[str, Any], *, enable_veto: bool) -> dict[str, Any]:
    cfg = _base_cfg(source_cfg)
    signal_generation = dict(cfg.get("signal_generation") or {})
    ranking = dict(signal_generation.get("ranking") or {})
    ranking["bull_breakout_quality_veto_enabled"] = bool(enable_veto)
    ranking["bull_breakout_quality_veto_min_residual_strength_score"] = 0.94
    ranking["bull_breakout_quality_veto_min_breakout_margin_score"] = 0.55
    signal_generation["ranking"] = ranking
    cfg["signal_generation"] = signal_generation
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


def _fallback_veto_counts_from_daily(exp_dir: Path) -> dict[str, int]:
    daily_path = exp_dir / "portfolio_daily.csv"
    if not daily_path.exists():
        return {
            "block_count": 0,
            "residual_block_count": 0,
            "margin_block_count": 0,
        }
    try:
        df = pd.read_csv(daily_path, usecols=["diagnostics_input_json"])
    except Exception:
        return {
            "block_count": 0,
            "residual_block_count": 0,
            "margin_block_count": 0,
        }
    block_count = 0
    residual_block_count = 0
    margin_block_count = 0
    for raw in df.get("diagnostics_input_json", pd.Series(dtype="object")).fillna("").astype(str):
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        diagnostics = dict(payload.get("diagnostics") or {})
        block_count += int(diagnostics.get("bull_breakout_quality_veto_block_count", 0) or 0)
        residual_block_count += int(diagnostics.get("bull_breakout_quality_veto_residual_block_count", 0) or 0)
        margin_block_count += int(diagnostics.get("bull_breakout_quality_veto_margin_block_count", 0) or 0)
    return {
        "block_count": int(block_count),
        "residual_block_count": int(residual_block_count),
        "margin_block_count": int(margin_block_count),
    }


def _extract_perf_row(*, variant: str, exp_id: str) -> dict[str, Any]:
    exp_dir = _exp_dir(exp_id)
    perf = _load_json(exp_dir / "perf.json")
    run_meta = _load_json(exp_dir / "run_meta.json")
    input_cfg = _load_json(exp_dir / "input_config.json")
    counters = run_meta.get("counters") if isinstance(run_meta.get("counters"), dict) else {}
    fallback_veto_counts = _fallback_veto_counts_from_daily(exp_dir)
    ranking = (
        ((input_cfg.get("signal_generation") or {}).get("ranking"))
        if isinstance((input_cfg.get("signal_generation") or {}).get("ranking"), dict)
        else {}
    )
    return {
        "variant": variant,
        "exp_id": exp_id,
        "window_start": (run_meta.get("data") or {}).get("start"),
        "window_end": (run_meta.get("data") or {}).get("end"),
        "data_role": ((run_meta.get("report_consistency") or {}).get("data_role")) or ((run_meta.get("data") or {}).get("data_role")),
        "universe_mode": (run_meta.get("data") or {}).get("universe_mode"),
        "bull_breakout_quality_veto_enabled": bool(ranking.get("bull_breakout_quality_veto_enabled", False)),
        "bull_breakout_quality_veto_min_residual_strength_score": ranking.get("bull_breakout_quality_veto_min_residual_strength_score"),
        "bull_breakout_quality_veto_min_breakout_margin_score": ranking.get("bull_breakout_quality_veto_min_breakout_margin_score"),
        "total_return": perf.get("total_return"),
        "cagr": perf.get("cagr"),
        "sharpe": perf.get("sharpe"),
        "max_drawdown": perf.get("max_drawdown"),
        "trades": perf.get("trades"),
        "turnover": perf.get("turnover"),
        "effective_execution_start_date": perf.get("effective_execution_start_date"),
        "raw_signal": counters.get("raw_signal"),
        "orders": counters.get("orders"),
        "cash_skip_count": counters.get("cash_skip_count"),
        "buy_orders_count": counters.get("buy_orders_count"),
        "sell_orders_count": counters.get("sell_orders_count"),
        "bull_breakout_quality_veto_block_count": counters.get(
            "bull_breakout_quality_veto_block_count",
            fallback_veto_counts["block_count"],
        ),
        "bull_breakout_quality_veto_residual_block_count": counters.get(
            "bull_breakout_quality_veto_residual_block_count",
            fallback_veto_counts["residual_block_count"],
        ),
        "bull_breakout_quality_veto_margin_block_count": counters.get(
            "bull_breakout_quality_veto_margin_block_count",
            fallback_veto_counts["margin_block_count"],
        ),
        "trade_mode_main_days": counters.get("trade_mode_main_days"),
        "trade_mode_light_days": counters.get("trade_mode_light_days"),
        "trade_mode_notrade_days": counters.get("trade_mode_notrade_days"),
        "market_state_trans_down_days": counters.get("market_state_trans_down_days"),
        "market_state_trans_up_days": counters.get("market_state_trans_up_days"),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _build_bull_trade_quality_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "variant": row["variant"],
                "exp_id": row["exp_id"],
                "bull_breakout_quality_veto_enabled": row["bull_breakout_quality_veto_enabled"],
                "min_residual_strength_score": row["bull_breakout_quality_veto_min_residual_strength_score"],
                "min_breakout_margin_score": row["bull_breakout_quality_veto_min_breakout_margin_score"],
                "raw_signal": row["raw_signal"],
                "buy_orders_count": row["buy_orders_count"],
                "sell_orders_count": row["sell_orders_count"],
                "cash_skip_count": row["cash_skip_count"],
                "bull_breakout_quality_veto_block_count": row["bull_breakout_quality_veto_block_count"],
                "bull_breakout_quality_veto_residual_block_count": row["bull_breakout_quality_veto_residual_block_count"],
                "bull_breakout_quality_veto_margin_block_count": row["bull_breakout_quality_veto_margin_block_count"],
            }
        )
    return out


def _fmt_num(value: Any, digits: int = 4) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return ""


def main() -> None:
    OPS_DIR.mkdir(parents=True, exist_ok=True)
    source_cfg = _source_config()
    baseline_exp = _run(_build_config(source_cfg, enable_veto=False))
    veto_exp = _run(_build_config(source_cfg, enable_veto=True))

    rows = [
        _extract_perf_row(variant="BASELINE_V10.2", exp_id=baseline_exp),
        _extract_perf_row(variant="BULL_BREAKOUT_QUALITY_VETO", exp_id=veto_exp),
    ]
    baseline = rows[0]
    veto = rows[1]
    delta = {
        "base_variant": baseline["variant"],
        "compare_variant": veto["variant"],
        "delta_total_return": float((veto["total_return"] or 0.0) - (baseline["total_return"] or 0.0)),
        "delta_cagr": float((veto["cagr"] or 0.0) - (baseline["cagr"] or 0.0)),
        "delta_sharpe": float((veto["sharpe"] or 0.0) - (baseline["sharpe"] or 0.0)),
        "delta_max_drawdown": float((veto["max_drawdown"] or 0.0) - (baseline["max_drawdown"] or 0.0)),
        "delta_trades": int((veto["trades"] or 0) - (baseline["trades"] or 0)),
    }
    summary = {
        "generated_at": datetime.now().isoformat(),
        "comparison_name": "v10_2_bull_breakout_quality_veto_ab",
        "source_exp_id": SOURCE_EXP_ID,
        "window": {
            "start": source_cfg.get("universe", {}).get("start"),
            "end": source_cfg.get("universe", {}).get("end"),
        },
        "assumptions": {
            "intended_diff": {
                "enabled": True,
                "market_state_scope": "BULL",
                "risk_on_only": True,
                "alpha_source_scope": ["breakout", "pullback_overlap"],
                "min_residual_strength_score": 0.94,
                "min_breakout_margin_score": 0.55,
            }
        },
        "variants": rows,
        "delta_vs_baseline": delta,
        "notes": [
            "A and B both rerun on current code to keep execution shell identical.",
            "The veto remains disabled by default and only applies when explicitly enabled in ranking config.",
            "The veto does not apply to pullback_only candidates.",
        ],
    }

    _write_csv(OPS_DIR / "performance_comparison.csv", rows)
    _write_csv(OPS_DIR / "delta_vs_baseline.csv", [delta])
    _write_csv(OPS_DIR / "bull_trade_quality_comparison.csv", _build_bull_trade_quality_rows(rows))
    (OPS_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    report_lines = [
        "# Baseline V10.2 Bull Breakout Quality Veto AB",
        "",
        "## 结论",
        "",
        "- 这轮 A/B 只改 `BULL` 内部的 breakout 质量 veto，其余执行壳保持不变。",
        "- veto 只对 `breakout/pullback_overlap` 生效，不影响 `pullback_only`。",
        "",
        "## 对照表",
        "",
        "| Variant | Exp ID | Veto | Residual Min | Margin Min | Total Return | CAGR | Sharpe | MaxDD | Trades | Veto Blocks |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        report_lines.append(
            f"| {row['variant']} | `{row['exp_id']}` | `{row['bull_breakout_quality_veto_enabled']}` | "
            f"{row['bull_breakout_quality_veto_min_residual_strength_score'] or 0.0} | "
            f"{row['bull_breakout_quality_veto_min_breakout_margin_score'] or 0.0} | "
            f"{_fmt_num(row['total_return'])} | {_fmt_num(row['cagr'])} | {_fmt_num(row['sharpe'])} | "
            f"{_fmt_num(row['max_drawdown'])} | {row['trades']} | {row['bull_breakout_quality_veto_block_count'] or 0} |"
        )
    report_lines.extend(
        [
            "",
            "## Delta vs Baseline",
            "",
            "| Compare | Delta Total Return | Delta CAGR | Delta Sharpe | Delta MaxDD | Delta Trades |",
            "|---|---:|---:|---:|---:|---:|",
            f"| {delta['compare_variant']} | {_fmt_num(delta['delta_total_return'])} | {_fmt_num(delta['delta_cagr'])} | "
            f"{_fmt_num(delta['delta_sharpe'])} | {_fmt_num(delta['delta_max_drawdown'])} | {delta['delta_trades']} |",
        ]
    )
    (OPS_DIR / "report.md").write_text("\n".join(report_lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
