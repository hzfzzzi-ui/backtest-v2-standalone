from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.data.cached_provider import clear_ohlcv_cache_files, get_ohlcv_cache_paths  # noqa: E402
from backend.scripts._internal_helper import (  # noqa: E402
    candidate_presets_api,
    read_json_artifact,
    resolve_internal_results_dir,
    stabilize_internal_experiment_result,
)
from backend.core.tools.experiment_runner import run_experiment  # noqa: E402

CANDIDATE_PRESETS = candidate_presets_api()


BASELINE_REF_EXP_ID = "exp_20260307_051743747_77d8"
ATR_REF_EXP_ID = "exp_20260307_171750033_eb7b"
BR35_REF_EXP_ID = "exp_20260307_194430192_e932"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_db_runtime(cfg: dict[str, Any]) -> None:
    db = cfg.setdefault("db", {})
    if str(db.get("host") or "").strip() == "pams-postgres":
        db["host"] = str(os.environ.get("PGHOST") or "localhost")
    if os.environ.get("PGPORT"):
        db["port"] = int(os.environ["PGPORT"])
    if os.environ.get("PGDATABASE"):
        db["dbname"] = str(os.environ["PGDATABASE"])
    if os.environ.get("PGUSER"):
        db["user"] = str(os.environ["PGUSER"])
    if not str(db.get("password") or "").strip():
        password = str(os.environ.get("PGPASSWORD") or os.environ.get("PAMS_PG_PASSWORD") or "").strip()
        if password:
            db["password"] = password


def _build_overrides(base_cfg: dict[str, Any], base_meta: dict[str, Any]) -> dict[str, Any]:
    universe = dict(base_cfg.get("universe") or {})
    counters = dict(base_meta.get("counters") or {})
    data = dict(base_meta.get("data") or {})
    return {
        "universe_mode": str(data.get("universe_mode") or "HS300_ZZ500"),
        "start_date": str(universe.get("start") or ""),
        "end_date": str(universe.get("end") or ""),
        "benchmark": str(universe.get("benchmark") or ""),
        "initial_capital": float(base_cfg.get("initial_capital") or 1_000_000),
        "max_positions": int(counters.get("max_positions") or 10),
        "base_order_value": float((base_cfg.get("sizing") or {}).get("order_value", 0.0) or 0.0),
        "fast_mode": bool((base_meta.get("code") or {}).get("fast_mode", True)),
        "price_adj": "hfq",
        "config_conflict_policy": "clean_data_rebuild",
    }


def _historical_metrics(exp_id: str) -> dict[str, Any]:
    exp_dir = ROOT / "outputs" / "experiments" / exp_id
    perf = _load_json(exp_dir / "perf.json")
    run_meta = _load_json(exp_dir / "run_meta.json")
    counters = dict(run_meta.get("counters") or {})
    return {
        "historical_exp_id": exp_id,
        "historical_results_dir": str(exp_dir),
        "historical_cagr": float(perf.get("cagr", 0.0) or 0.0),
        "historical_max_drawdown": float(perf.get("max_drawdown", 0.0) or 0.0),
        "historical_sharpe": float(perf.get("sharpe", 0.0) or 0.0),
        "historical_calmar": float(perf.get("calmar", 0.0) or 0.0),
        "historical_total_return": float(perf.get("total_return", 0.0) or 0.0),
        "historical_trades": int(perf.get("trades", 0) or 0),
        "historical_turnover": float(perf.get("turnover", 0.0) or 0.0),
        "historical_raw_signal": int(counters.get("raw_signal", 0) or 0),
        "historical_avg_positions": float(counters.get("avg_positions", 0.0) or 0.0),
        "historical_slots_left": float(counters.get("slots_left", 0.0) or 0.0),
    }


def _current_metrics(result: dict[str, Any], results_dir: Path) -> dict[str, Any]:
    perf = read_json_artifact(results_dir=results_dir, artifact_key="perf", fallback_rel_path="perf.json")
    run_meta = read_json_artifact(results_dir=results_dir, artifact_key="run_meta", fallback_rel_path="run_meta.json")
    counters = dict(run_meta.get("counters") or {})
    return {
        "exp_id": str(result.get("exp_id") or ""),
        "results_dir": str(results_dir),
        "cagr": float(perf.get("cagr", 0.0) or 0.0),
        "max_drawdown": float(perf.get("max_drawdown", 0.0) or 0.0),
        "sharpe": float(perf.get("sharpe", 0.0) or 0.0),
        "calmar": float(perf.get("calmar", 0.0) or 0.0),
        "total_return": float(perf.get("total_return", 0.0) or 0.0),
        "trades": int(perf.get("trades", 0) or 0),
        "turnover": float(perf.get("turnover", 0.0) or 0.0),
        "raw_signal": int(counters.get("raw_signal", 0) or 0),
        "avg_positions": float(counters.get("avg_positions", 0.0) or 0.0),
        "slots_left": float(counters.get("slots_left", 0.0) or 0.0),
        "utilization": (
            float(counters.get("avg_positions", 0.0) or 0.0) / float(counters.get("max_positions", 10) or 10)
            if float(counters.get("max_positions", 10) or 10) > 0
            else 0.0
        ),
    }


def _run_one(
    *,
    label: str,
    runtime_cfg: dict[str, Any],
    stabilize_cfg: dict[str, Any],
    overrides: dict[str, Any],
    progress_prefix: str,
) -> tuple[dict[str, Any], Path]:
    execution_cfg = json.loads(json.dumps(runtime_cfg))
    _normalize_db_runtime(execution_cfg)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
        json.dump(execution_cfg, tmp, ensure_ascii=False, indent=2)
        tmp_path = tmp.name

    t0 = time.perf_counter()
    print(f"\n{'=' * 72}")
    print(f"{progress_prefix}: {label}")
    print(f"{'=' * 72}")

    def progress(pct: int, message: str) -> None:
        elapsed = time.perf_counter() - t0
        print(f"  [{pct:3d}%] {message} ({elapsed:.1f}s)")

    try:
        result = run_experiment(tmp_path, preset="single", overrides=overrides, progress_hook=progress)
        stabilized = stabilize_internal_experiment_result(
            bt_root=ROOT,
            result=result if isinstance(result, dict) else {},
            base_cfg=stabilize_cfg,
            overrides=overrides,
            run_profile_summary=result.get("run_profile_summary") if isinstance(result, dict) else None,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    results_dir = resolve_internal_results_dir(
        exp_id=str(stabilized.get("exp_id") or "") or None,
        results_dir=str(stabilized.get("results_dir") or "") or None,
    )
    metrics = _current_metrics(stabilized, results_dir)
    print(
        "  CAGR={cagr:+.2%}  MaxDD={max_drawdown:.2%}  Sharpe={sharpe:.2f}  Trades={trades}".format(
            **metrics
        )
    )
    return stabilized, results_dir


def _write_summary(
    *,
    out_dir: Path,
    cache_info: dict[str, Any],
    static_audit: dict[str, Any],
    baseline_row: dict[str, Any],
    atr_row: dict[str, Any],
    br35_row: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [baseline_row, atr_row, br35_row]
    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "ab_summary.csv", index=False)

    summary = {
        "generated_at": datetime.now().isoformat(),
        "purpose": "clean_data_standard_rerun",
        "cache_info": cache_info,
        "static_audit": static_audit,
        "baseline_ref_exp_id": BASELINE_REF_EXP_ID,
        "atr_ref_exp_id": ATR_REF_EXP_ID,
        "br35_ref_exp_id": BR35_REF_EXP_ID,
        "results": rows,
    }
    _write_json(out_dir / "summary.json", summary)

    lines = [
        "# Clean Data Standard Rerun",
        "",
        f"- baseline_ref_exp_id: `{BASELINE_REF_EXP_ID}`",
        f"- atr_ref_exp_id: `{ATR_REF_EXP_ID}`",
        f"- br35_ref_exp_id: `{BR35_REF_EXP_ID}`",
        f"- cache_removed: `{json.dumps(cache_info.get('removed') or [], ensure_ascii=False)}`",
        f"- cache_paths: `{json.dumps(cache_info.get('paths') or {}, ensure_ascii=False)}`",
        f"- static_audit_mode: `{str(static_audit.get('audit_mode') or '')}`",
        "",
        "| variant | historical_exp_id | clean_exp_id | raw_signal(old->new) | avg_pos(old->new) | CAGR(old->new) | MaxDD(old->new) | Sharpe(old->new) | Trades(old->new) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {variant} | `{historical_exp_id}` | `{exp_id}` | {historical_raw_signal} -> {raw_signal} | "
            "{historical_avg_positions:.2f} -> {avg_positions:.2f} | {historical_cagr:.2%} -> {cagr:.2%} | "
            "{historical_max_drawdown:.2%} -> {max_drawdown:.2%} | {historical_sharpe:.2f} -> {sharpe:.2f} | "
            "{historical_trades} -> {trades} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## 审计结论",
            "",
            "- 本轮只重跑标准实验，不改策略逻辑和 candidate 定义。",
            "- 已在运行前清理 OHLCV parquet 缓存，避免旧缓存遮挡数据库修复。",
            "- T+1 静态契约继续由现有 locked-candidate 审计守卫覆盖。",
        ]
    )
    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    baseline_cfg = CANDIDATE_PRESETS.load_locked_baseline_config(CANDIDATE_PRESETS.BREAKOUT_ATR_STOP_K10_CANDIDATE)
    baseline_meta = CANDIDATE_PRESETS.load_locked_baseline_meta(CANDIDATE_PRESETS.BREAKOUT_ATR_STOP_K10_CANDIDATE)
    atr_cfg, atr_candidate_meta = CANDIDATE_PRESETS.build_breakout_atr_stop_k10_candidate_cfg()
    br35_cfg, br35_candidate_meta = CANDIDATE_PRESETS.build_breakout_br35_atr10_candidate_cfg()

    cache_info = {
        "removed": clear_ohlcv_cache_files(),
        "paths": get_ohlcv_cache_paths(),
    }
    static_audit = CANDIDATE_PRESETS._build_static_t1_guard()
    overrides = _build_overrides(baseline_cfg, baseline_meta)

    baseline_result, baseline_dir = _run_one(
        label="locked_baseline",
        runtime_cfg=baseline_cfg,
        stabilize_cfg=baseline_cfg,
        overrides=dict(overrides, config_source="clean_data_locked_baseline"),
        progress_prefix="run",
    )

    atr_result, atr_dir = _run_one(
        label="atr_stop_k10_candidate",
        runtime_cfg=atr_cfg,
        stabilize_cfg=atr_cfg,
        overrides=dict(
            overrides,
            config_source="clean_data_locked_candidate",
            candidate_context=atr_candidate_meta,
        ),
        progress_prefix="run",
    )
    atr_candidate_artifacts = CANDIDATE_PRESETS.write_breakout_atr_stop_k10_candidate_artifacts(
        results_dir=atr_dir,
        result=atr_result,
        candidate_meta=atr_candidate_meta,
    )

    br35_result, br35_dir = _run_one(
        label="br35_atr10_candidate",
        runtime_cfg=br35_cfg,
        stabilize_cfg=br35_cfg,
        overrides=dict(
            overrides,
            config_source="clean_data_locked_candidate",
            candidate_context=br35_candidate_meta,
        ),
        progress_prefix="run",
    )
    br35_candidate_artifacts = CANDIDATE_PRESETS.write_breakout_br35_atr10_candidate_artifacts(
        results_dir=br35_dir,
        result=br35_result,
        candidate_meta=br35_candidate_meta,
    )

    baseline_row = {
        "variant": "locked_baseline",
        "historical_exp_id": BASELINE_REF_EXP_ID,
        **_historical_metrics(BASELINE_REF_EXP_ID),
        **_current_metrics(baseline_result, baseline_dir),
        "candidate_status": None,
    }
    atr_row = {
        "variant": CANDIDATE_PRESETS.BREAKOUT_ATR_STOP_K10_CANDIDATE,
        "historical_exp_id": ATR_REF_EXP_ID,
        **_historical_metrics(ATR_REF_EXP_ID),
        **_current_metrics(atr_result, atr_dir),
        "candidate_status": str(atr_candidate_artifacts.get("status") or ""),
        "candidate_summary_path": str(atr_candidate_artifacts.get("candidate_summary_path") or ""),
        "candidate_summary_json_path": str(atr_candidate_artifacts.get("candidate_summary_json_path") or ""),
        "candidate_assessment_path": str((atr_dir / "candidate_summary.json")),
        "assessment": CANDIDATE_PRESETS.assess_breakout_atr_stop_k10_candidate_results(atr_dir),
    }
    br35_row = {
        "variant": CANDIDATE_PRESETS.BREAKOUT_BR35_ATR10_CANDIDATE,
        "historical_exp_id": BR35_REF_EXP_ID,
        **_historical_metrics(BR35_REF_EXP_ID),
        **_current_metrics(br35_result, br35_dir),
        "candidate_status": str(br35_candidate_artifacts.get("status") or ""),
        "candidate_summary_path": str(br35_candidate_artifacts.get("candidate_summary_path") or ""),
        "candidate_summary_json_path": str(br35_candidate_artifacts.get("candidate_summary_json_path") or ""),
        "candidate_assessment_path": str((br35_dir / "candidate_summary.json")),
        "assessment": CANDIDATE_PRESETS.assess_breakout_br35_atr10_candidate_results(br35_dir),
    }

    out_dir = ROOT / "outputs" / "ops" / f"clean_data_standard_rerun_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    _write_summary(
        out_dir=out_dir,
        cache_info=cache_info,
        static_audit=static_audit,
        baseline_row=baseline_row,
        atr_row=atr_row,
        br35_row=br35_row,
    )
    print(f"\nsummary_dir={out_dir}")


if __name__ == "__main__":
    main()
