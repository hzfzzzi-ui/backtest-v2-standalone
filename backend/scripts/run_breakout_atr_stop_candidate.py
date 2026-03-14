from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.services.experiment_artifact_service import stabilize_experiment_output  # noqa: E402
from backend.core.tools.experiment_runner import run_experiment  # noqa: E402


CANDIDATE_NAME = "v2-breakout-atr-stop-k10-candidate"
BASELINE_EXP_ID = "exp_20260307_051743747_77d8"
BASELINE_CFG_PATH = ROOT / "outputs" / "experiments" / BASELINE_EXP_ID / "run_config.json"
BASELINE_META_PATH = ROOT / "outputs" / "experiments" / BASELINE_EXP_ID / "run_meta.json"
ALLOWED_DIFF_PATH = ("strategy", "params", "atr_stop_k")
TARGET_ATR_STOP_K = 1.0


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _path_text(path: tuple[Any, ...]) -> str:
    return ".".join(str(part) for part in path)


def _collect_diffs(base: Any, candidate: Any, path: tuple[Any, ...] = ()) -> list[tuple[tuple[Any, ...], Any, Any]]:
    if isinstance(base, dict) and isinstance(candidate, dict):
        diffs: list[tuple[tuple[Any, ...], Any, Any]] = []
        for key in sorted(set(base.keys()) | set(candidate.keys())):
            if key not in base:
                diffs.append((path + (key,), "<missing>", candidate[key]))
                continue
            if key not in candidate:
                diffs.append((path + (key,), base[key], "<missing>"))
                continue
            diffs.extend(_collect_diffs(base[key], candidate[key], path + (key,)))
        return diffs
    if isinstance(base, list) and isinstance(candidate, list):
        if len(base) != len(candidate):
            return [(path, base, candidate)]
        diffs = []
        for idx, (base_item, candidate_item) in enumerate(zip(base, candidate)):
            diffs.extend(_collect_diffs(base_item, candidate_item, path + (idx,)))
        return diffs
    if base != candidate:
        return [(path, base, candidate)]
    return []


def _assert_single_main_change(base_cfg: dict[str, Any], candidate_cfg: dict[str, Any]) -> None:
    diffs = _collect_diffs(base_cfg, candidate_cfg)
    unexpected = [diff for diff in diffs if diff[0] != ALLOWED_DIFF_PATH]
    if unexpected:
        lines = []
        for diff_path, base_value, candidate_value in unexpected[:10]:
            lines.append(
                f"{_path_text(diff_path)}: baseline={base_value!r}, candidate={candidate_value!r}"
            )
        raise RuntimeError(
            "candidate drifted beyond the allowed main change:\n" + "\n".join(lines)
        )


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


def _build_candidate_cfg(base_cfg: dict[str, Any]) -> dict[str, Any]:
    candidate_cfg = deepcopy(base_cfg)
    candidate_cfg.setdefault("strategy", {}).setdefault("params", {})["atr_stop_k"] = float(TARGET_ATR_STOP_K)
    _assert_single_main_change(base_cfg, candidate_cfg)
    return candidate_cfg


def _build_overrides(base_cfg: dict[str, Any], baseline_meta: dict[str, Any]) -> dict[str, Any]:
    universe = base_cfg.get("universe") or {}
    counters = baseline_meta.get("counters") if isinstance(baseline_meta.get("counters"), dict) else {}
    data = baseline_meta.get("data") if isinstance(baseline_meta.get("data"), dict) else {}
    return {
        "universe_mode": str(data.get("universe_mode") or "HS300_ZZ500"),
        "start_date": str(universe.get("start") or ""),
        "end_date": str(universe.get("end") or ""),
        "benchmark": str(universe.get("benchmark") or ""),
        "initial_capital": float(base_cfg.get("initial_capital") or 1_000_000),
        "max_positions": int(counters.get("max_positions") or 10),
        "base_order_value": float((base_cfg.get("sizing") or {}).get("order_value", 0.0) or 0.0),
        "fast_mode": True,
        "price_adj": "hfq",
    }


def _assert_baseline_contract(base_cfg: dict[str, Any], baseline_meta: dict[str, Any]) -> None:
    strategy_name = str((base_cfg.get("strategy") or {}).get("name") or "").strip().lower()
    if strategy_name != "breakout_trend":
        raise RuntimeError(f"expected breakout_trend baseline, got {strategy_name!r}")
    if str((baseline_meta.get("data") or {}).get("universe_mode") or "") != "HS300_ZZ500":
        raise RuntimeError("baseline universe_mode is not HS300_ZZ500")
    if str((base_cfg.get("universe") or {}).get("benchmark") or "") != "000300.SH":
        raise RuntimeError("baseline benchmark is not 000300.SH")
    atr_stop_k = float((((base_cfg.get("strategy") or {}).get("params") or {}).get("atr_stop_k", 0.0) or 0.0))
    if abs(atr_stop_k - 1.2) > 1e-9:
        raise RuntimeError(f"expected locked baseline atr_stop_k=1.2, got {atr_stop_k!r}")


def _assert_time_alignment_contract() -> dict[str, Any]:
    sim_path = ROOT / "backend" / "core" / "engine_vector" / "portfolio_simulator_strict.py"
    provider_path = ROOT / "backend" / "core" / "engine_vector" / "breakout_signal_provider.py"
    sim_text = sim_path.read_text(encoding="utf-8")
    provider_text = provider_path.read_text(encoding="utf-8")

    required_sim_patterns = (
        "provider.day_signals(day, i, ctx)",
        "pending[next_day] = [",
    )
    missing_sim = [pattern for pattern in required_sim_patterns if pattern not in sim_text]
    if missing_sim:
        raise RuntimeError(f"time-alignment guard failed in {sim_path}: missing {missing_sim!r}")

    required_provider_patterns = (
        "bench_close_s.rolling(regime_ma, min_periods=regime_ma).mean()",
        "self._risk_on = np.ones(t, dtype=bool)",
        "self._risk_on[valid_bench] = self._bench_close[valid_bench] > bench_ma[valid_bench]",
    )
    missing_provider = [pattern for pattern in required_provider_patterns if pattern not in provider_text]
    if missing_provider:
        raise RuntimeError(f"provider audit failed in {provider_path}: missing {missing_provider!r}")

    return {
        "provider_signal_ref": f"{sim_path}:1564",
        "next_day_queue_ref": f"{sim_path}:1657",
        "provider_regime_ref": f"{provider_path}:176",
        "audit_mode": "static_code_contract",
        "t1_execution_confirmed": True,
    }


def _augment_run_meta(
    results_dir: Path,
    *,
    variant_name: str,
    candidate_enabled: bool,
    static_audit: dict[str, Any],
) -> None:
    run_meta_path = results_dir / "run_meta.json"
    if not run_meta_path.exists():
        raise RuntimeError(f"missing run_meta.json: {run_meta_path}")
    run_meta = _load_json(run_meta_path)
    run_meta["candidate_evaluation"] = {
        "candidate_name": CANDIDATE_NAME,
        "variant_name": variant_name,
        "enabled": bool(candidate_enabled),
        "source_baseline_exp_id": BASELINE_EXP_ID,
        "source_baseline_config_path": str(BASELINE_CFG_PATH),
        "main_change_path": _path_text(ALLOWED_DIFF_PATH),
        "main_change_value": float(TARGET_ATR_STOP_K) if candidate_enabled else 1.2,
        "default_behavior_unchanged": True,
        "time_alignment_guard": static_audit,
    }
    _write_json(run_meta_path, run_meta)


def _collect_result_metrics(
    *,
    variant_name: str,
    candidate_enabled: bool,
    result: dict[str, Any],
    results_dir: Path,
) -> dict[str, Any]:
    return {
        "variant": variant_name,
        "candidate_enabled": bool(candidate_enabled),
        "atr_stop_k": float(TARGET_ATR_STOP_K if candidate_enabled else 1.2),
        "exp_id": str(result.get("exp_id") or ""),
        "results_dir": str(results_dir),
        "cagr": float(result.get("cagr", 0.0) or 0.0),
        "max_drawdown": float(result.get("max_drawdown", 0.0) or 0.0),
        "sharpe": float(result.get("sharpe", 0.0) or 0.0),
        "calmar": float(result.get("calmar", 0.0) or 0.0),
        "total_return": float(result.get("total_return", 0.0) or 0.0),
        "trades": int(result.get("trades", 0) or 0),
        "turnover": float(result.get("turnover", 0.0) or 0.0),
        "avg_positions": float(result.get("avg_positions", 0.0) or 0.0),
        "manifest_path": str(results_dir / "manifest.json"),
        "run_meta_path": str(results_dir / "run_meta.json"),
    }


def _find_latest_summary(prefix: str) -> str | None:
    root = ROOT / "outputs" / "experiments"
    candidates = sorted(
        [path for path in root.glob(f"{prefix}*/summary.md") if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return None
    return str(candidates[0])


def _run_one(
    *,
    variant_name: str,
    runtime_cfg: dict[str, Any],
    stabilize_cfg: dict[str, Any],
    overrides: dict[str, Any],
    static_audit: dict[str, Any],
    candidate_enabled: bool,
) -> dict[str, Any]:
    execution_cfg = deepcopy(runtime_cfg)
    _normalize_db_runtime(execution_cfg)

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(execution_cfg, tmp, ensure_ascii=False, indent=2)
    tmp.close()
    tmp_path = tmp.name

    t0 = time.perf_counter()
    print(f"\n{'=' * 72}")
    print(f"{variant_name}: atr_stop_k={TARGET_ATR_STOP_K if candidate_enabled else 1.2}")
    print(f"{'=' * 72}")

    def progress(pct: int, message: str) -> None:
        elapsed = time.perf_counter() - t0
        print(f"  [{pct:3d}%] {message} ({elapsed:.1f}s)")

    try:
        result = run_experiment(tmp_path, preset="single", overrides=overrides, progress_hook=progress)
        stabilized = stabilize_experiment_output(
            bt_root=ROOT,
            result=result if isinstance(result, dict) else {},
            base_cfg=stabilize_cfg,
            overrides=overrides,
            run_profile_summary=result.get("run_profile_summary") if isinstance(result, dict) else None,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    results_dir = Path(str(stabilized.get("results_dir") or "")).resolve()
    _augment_run_meta(
        results_dir,
        variant_name=variant_name,
        candidate_enabled=candidate_enabled,
        static_audit=static_audit,
    )
    metrics = _collect_result_metrics(
        variant_name=variant_name,
        candidate_enabled=candidate_enabled,
        result=stabilized,
        results_dir=results_dir,
    )
    print(
        "  CAGR={cagr:+.2%}  MaxDD={max_drawdown:.2%}  Sharpe={sharpe:.2f}  Trades={trades}".format(
            **metrics
        )
    )
    return metrics


def _write_summary(
    *,
    out_dir: Path,
    base_cfg: dict[str, Any],
    baseline_meta: dict[str, Any],
    static_audit: dict[str, Any],
    results: list[dict[str, Any]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    evidence_refs = {
        "full_sample_research": _find_latest_summary("atr_stop_research_"),
        "local_robustness": _find_latest_summary("atr_stop_local_robustness_"),
        "window_check": _find_latest_summary("atr_stop_window_check_"),
        "terminal_sensitivity": _find_latest_summary("atr_stop_terminal_sensitivity_"),
    }
    summary = {
        "generated_at": datetime.now().isoformat(),
        "candidate_name": CANDIDATE_NAME,
        "baseline_exp_id": BASELINE_EXP_ID,
        "baseline_config_path": str(BASELINE_CFG_PATH),
        "baseline_meta_path": str(BASELINE_META_PATH),
        "main_change_path": _path_text(ALLOWED_DIFF_PATH),
        "candidate_value": float(TARGET_ATR_STOP_K),
        "default_behavior_unchanged": True,
        "static_audit": static_audit,
        "unchanged_contract": {
            "benchmark": str((base_cfg.get("universe") or {}).get("benchmark") or ""),
            "start": str((base_cfg.get("universe") or {}).get("start") or ""),
            "end": str((base_cfg.get("universe") or {}).get("end") or ""),
            "costs": base_cfg.get("costs") or {},
            "execution": base_cfg.get("execution") or {},
            "benchmark_regime": base_cfg.get("benchmark_regime") or {},
            "universe_mode": str((baseline_meta.get("data") or {}).get("universe_mode") or ""),
        },
        "research_evidence_refs": evidence_refs,
        "results": results,
        "conclusion": {
            "status": "formal_candidate_ready",
            "summary": "候选脚本为显式入口，默认 baseline 不变；当前实现只允许 atr_stop_k 单路径漂移。",
            "known_tradeoff": "候选改善全样本并通过终点敏感性，但最近窗口收益弹性弱于 baseline。",
            "enable_instruction": "运行 backend/scripts/run_breakout_atr_stop_candidate.py",
            "rollback_instruction": "停止使用该脚本，继续使用锁定 baseline 或 baseline 变体。",
        },
    }
    _write_json(out_dir / "summary.json", summary)

    rows = []
    for row in results:
        rows.append(
            "| {variant} | {atr_stop_k:.1f} | {cagr:.2%} | {max_drawdown:.2%} | {sharpe:.2f} | {calmar:.2f} | {trades} | `{exp_id}` |".format(
                **row
            )
        )

    evidence_lines = []
    for key, value in evidence_refs.items():
        evidence_lines.append(f"- {key}: `{value or 'missing'}`")

    lines = [
        "# Breakout ATR Stop Candidate",
        "",
        f"- candidate_name: `{CANDIDATE_NAME}`",
        f"- baseline_exp_id: `{BASELINE_EXP_ID}`",
        f"- main_change: `{_path_text(ALLOWED_DIFF_PATH)} = {TARGET_ATR_STOP_K}`",
        f"- default_behavior_unchanged: `true`",
        "",
        "## 最小对照复跑",
        "",
        "| variant | atr_stop_k | CAGR | MaxDD | Sharpe | Calmar | Trades | exp_id |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
        *rows,
        "",
        "## 审计结论",
        "",
        "- 只允许 `strategy.params.atr_stop_k` 漂移，其余配置若发生漂移则脚本直接失败。",
        f"- 静态时序契约检查: `provider.day_signals(day, i, ctx)` 与 `pending[next_day]` 已确认，参考 `{static_audit['provider_signal_ref']}` 与 `{static_audit['next_day_queue_ref']}`。",
        "- baseline 默认入口未被改写；候选仅通过本脚本显式启用。",
        "",
        "## 研究证据引用",
        "",
        *evidence_lines,
        "",
        "## 候选结论",
        "",
        "- 这是一条正式 candidate，不是新 baseline。",
        "- 已知副作用：最近窗口收益弹性弱于 baseline。",
        "- 启用方式：运行本脚本。",
        "- 回退方式：停止使用本脚本，继续使用 baseline。",
    ]
    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if not BASELINE_CFG_PATH.exists():
        raise FileNotFoundError(f"missing baseline config: {BASELINE_CFG_PATH}")
    if not BASELINE_META_PATH.exists():
        raise FileNotFoundError(f"missing baseline meta: {BASELINE_META_PATH}")

    base_cfg = _load_json(BASELINE_CFG_PATH)
    baseline_meta = _load_json(BASELINE_META_PATH)
    _assert_baseline_contract(base_cfg, baseline_meta)
    static_audit = _assert_time_alignment_contract()
    candidate_cfg = _build_candidate_cfg(base_cfg)
    overrides = _build_overrides(base_cfg, baseline_meta)

    print("Audit: candidate path is explicit and default baseline remains unchanged.")
    print("Audit: only strategy.params.atr_stop_k may drift.")
    print("Audit: static code contract confirms day-t signal generation and next-day queue execution.")

    results = [
        _run_one(
            variant_name="baseline",
            runtime_cfg=base_cfg,
            stabilize_cfg=base_cfg,
            overrides=overrides,
            static_audit=static_audit,
            candidate_enabled=False,
        ),
        _run_one(
            variant_name="candidate_atr_stop_k_1_0",
            runtime_cfg=candidate_cfg,
            stabilize_cfg=candidate_cfg,
            overrides=overrides,
            static_audit=static_audit,
            candidate_enabled=True,
        ),
    ]

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "outputs" / "experiments" / f"atr_stop_candidate_{stamp}"
    _write_summary(
        out_dir=out_dir,
        base_cfg=base_cfg,
        baseline_meta=baseline_meta,
        static_audit=static_audit,
        results=results,
    )
    print(f"\nSummary written to {out_dir}")


if __name__ == "__main__":
    main()
