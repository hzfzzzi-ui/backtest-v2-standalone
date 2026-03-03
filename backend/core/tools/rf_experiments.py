"""RegimeFilter 对照实验。

实验设计:
  A. RF OFF (baseline) — r2 config, 旧 regime router
  B. RF ON (default) — r3 config, 三层过滤, threshold=0.3
  C. RF ON, MR disabled — r3 config + rsi_buy_threshold=0 (只有趋势信号)
  D. RF ON, threshold=0.5
  E. RF ON, threshold=0.7

目的: 隔离 per-stock 双分支 vs 信号质量 vs threshold 对表现的影响。
"""
from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.core.tools.experiment_runner import run_experiment


def run_and_report(label: str, cfg_path: str, overrides: dict) -> dict:
    t0 = time.perf_counter()
    print(f"Running: {label} ...", flush=True)
    result = run_experiment(cfg_path, preset="single", overrides=overrides)
    elapsed = time.perf_counter() - t0
    print(f"  done in {elapsed:.1f}s — trades={result['trades']}, return={result['total_return']:.4f}, sharpe={result['sharpe']:.4f}")
    result["_label"] = label
    result["_elapsed"] = elapsed
    return result


def main():
    r2_path = str(ROOT / "backend" / "configs" / "sweep" / "r2_atr_trailonly_csi800.json")
    r3_path = str(ROOT / "backend" / "configs" / "sweep" / "r3_regime_filter_csi800.json")
    sweep_ov = {"universe_mode": "HS300_ZZ500", "max_positions": 10}

    results = []

    # ── A. RF OFF (baseline) ──
    results.append(run_and_report("A: RF OFF (baseline)", r2_path, sweep_ov))

    # ── B. RF ON (default threshold=0.3) ──
    results.append(run_and_report("B: RF ON (thr=0.3)", r3_path, sweep_ov))

    # ── C. RF ON, MR disabled (rsi_buy_threshold=0) ──
    # Modify r3 config inline via workbench_config override
    r3_raw = json.loads(Path(r3_path).read_text(encoding="utf-8-sig"))
    r3_no_mr = copy.deepcopy(r3_raw)
    r3_no_mr["strategy"]["mr_params"]["rsi_buy_threshold"] = 0.0  # RSI never hits 0
    # Write temp config
    tmp_c = ROOT / "outputs" / "_tmp_rf_no_mr.json"
    tmp_c.parent.mkdir(parents=True, exist_ok=True)
    tmp_c.write_text(json.dumps(r3_no_mr, ensure_ascii=False, indent=2), encoding="utf-8")
    results.append(run_and_report("C: RF ON, no MR", str(tmp_c), sweep_ov))

    # ── D. RF ON, threshold=0.5 ──
    r3_t05 = copy.deepcopy(r3_raw)
    r3_t05["strategy"]["regime_filter"]["regime_threshold"] = 0.5
    tmp_d = ROOT / "outputs" / "_tmp_rf_t05.json"
    tmp_d.write_text(json.dumps(r3_t05, ensure_ascii=False, indent=2), encoding="utf-8")
    results.append(run_and_report("D: RF ON (thr=0.5)", str(tmp_d), sweep_ov))

    # ── E. RF ON, threshold=0.7 ──
    r3_t07 = copy.deepcopy(r3_raw)
    r3_t07["strategy"]["regime_filter"]["regime_threshold"] = 0.7
    tmp_e = ROOT / "outputs" / "_tmp_rf_t07.json"
    tmp_e.write_text(json.dumps(r3_t07, ensure_ascii=False, indent=2), encoding="utf-8")
    results.append(run_and_report("E: RF ON (thr=0.7)", str(tmp_e), sweep_ov))

    # ── F. RF ON, threshold=0.3, alpha_m=5 (更陡峭的 market gate) ──
    r3_steep = copy.deepcopy(r3_raw)
    r3_steep["strategy"]["regime_filter"]["alpha_m"] = 5.0
    r3_steep["strategy"]["regime_filter"]["alpha_sec"] = 5.0
    r3_steep["strategy"]["regime_filter"]["alpha_i"] = 5.0
    tmp_f = ROOT / "outputs" / "_tmp_rf_steep.json"
    tmp_f.write_text(json.dumps(r3_steep, ensure_ascii=False, indent=2), encoding="utf-8")
    results.append(run_and_report("F: RF ON (alpha=5.0)", str(tmp_f), sweep_ov))

    # ── G. RF ON, MR disabled + threshold=0.5 ──
    r3_no_mr_t05 = copy.deepcopy(r3_raw)
    r3_no_mr_t05["strategy"]["mr_params"]["rsi_buy_threshold"] = 0.0
    r3_no_mr_t05["strategy"]["regime_filter"]["regime_threshold"] = 0.5
    tmp_g = ROOT / "outputs" / "_tmp_rf_no_mr_t05.json"
    tmp_g.write_text(json.dumps(r3_no_mr_t05, ensure_ascii=False, indent=2), encoding="utf-8")
    results.append(run_and_report("G: RF ON, no MR, thr=0.5", str(tmp_g), sweep_ov))

    # ── Summary ──
    print("\n" + "=" * 90)
    print(f"{'Experiment':<30} {'Return':>10} {'Sharpe':>10} {'CAGR':>10} {'MaxDD':>10} {'Trades':>8}")
    print("-" * 90)
    for r in results:
        print(
            f"{r['_label']:<30} "
            f"{r['total_return']:>10.4f} "
            f"{r['sharpe']:>10.4f} "
            f"{r['cagr']:>10.4f} "
            f"{r['max_drawdown']:>10.4f} "
            f"{r['trades']:>8d}"
        )
    print("=" * 90)


if __name__ == "__main__":
    main()
