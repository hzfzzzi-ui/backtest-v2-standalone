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

from backend.core.tools.experiment_runner import run_experiment  # noqa: E402


BASELINE_EXP_ID = "exp_20260307_051743747_77d8"
BASELINE_CFG_PATH = ROOT / "outputs" / "experiments" / BASELINE_EXP_ID / "run_config.json"
BASELINE_META_PATH = ROOT / "outputs" / "experiments" / BASELINE_EXP_ID / "run_meta.json"
ALLOWED_DIFF_PATH = ("strategy", "params", "regime_ma")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


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
            "variant drifted beyond the allowed main change:\n" + "\n".join(lines)
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


def _build_variant_cfg(base_cfg: dict[str, Any], *, regime_ma: int) -> dict[str, Any]:
    candidate_cfg = deepcopy(base_cfg)
    candidate_cfg.setdefault("strategy", {}).setdefault("params", {})["regime_ma"] = int(regime_ma)
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
    if bool(((base_cfg.get("benchmark_regime") or {}).get("enabled"))):
        return
    raise RuntimeError("expected baseline benchmark_regime.enabled=true")


def _run_one(
    *,
    variant_name: str,
    regime_ma: int,
    base_cfg: dict[str, Any],
    baseline_meta: dict[str, Any],
) -> dict[str, Any]:
    runtime_cfg = _build_variant_cfg(base_cfg, regime_ma=regime_ma)
    execution_cfg = deepcopy(runtime_cfg)
    _normalize_db_runtime(execution_cfg)
    overrides = _build_overrides(base_cfg, baseline_meta)

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(execution_cfg, tmp, ensure_ascii=False, indent=2)
    tmp.close()
    tmp_path = tmp.name

    t0 = time.perf_counter()
    print(f"\n{'=' * 72}")
    print(f"{variant_name}: strategy.params.regime_ma={regime_ma}")
    print(f"{'=' * 72}")

    def progress(pct: int, message: str) -> None:
        elapsed = time.perf_counter() - t0
        print(f"  [{pct:3d}%] {message} ({elapsed:.1f}s)")

    try:
        result = run_experiment(tmp_path, preset="single", overrides=overrides, progress_hook=progress)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    metrics = {
        "variant": variant_name,
        "regime_ma": int(regime_ma),
        "exp_id": str(result.get("exp_id") or ""),
        "results_dir": str(result.get("results_dir") or ""),
        "cagr": float(result.get("cagr", 0.0) or 0.0),
        "max_drawdown": float(result.get("max_drawdown", 0.0) or 0.0),
        "sharpe": float(result.get("sharpe", 0.0) or 0.0),
        "calmar": float(result.get("calmar", 0.0) or 0.0),
        "total_return": float(result.get("total_return", 0.0) or 0.0),
        "trades": int(result.get("trades", 0) or 0),
        "turnover": float(result.get("turnover", 0.0) or 0.0),
        "avg_positions": float(result.get("avg_positions", 0.0) or 0.0),
        "audit_only_changed": _path_text(ALLOWED_DIFF_PATH),
    }
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
    results: list[dict[str, Any]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    baseline_regime_ma = int(((base_cfg.get("strategy") or {}).get("params") or {}).get("regime_ma", 0) or 0)
    summary = {
        "generated_at": datetime.now().isoformat(),
        "baseline_exp_id": BASELINE_EXP_ID,
        "baseline_config_path": str(BASELINE_CFG_PATH),
        "baseline_meta_path": str(BASELINE_META_PATH),
        "baseline_regime_ma": baseline_regime_ma,
        "main_change_path": _path_text(ALLOWED_DIFF_PATH),
        "unchanged_contract": {
            "benchmark": str((base_cfg.get("universe") or {}).get("benchmark") or ""),
            "start": str((base_cfg.get("universe") or {}).get("start") or ""),
            "end": str((base_cfg.get("universe") or {}).get("end") or ""),
            "costs": base_cfg.get("costs") or {},
            "execution": base_cfg.get("execution") or {},
            "benchmark_regime": base_cfg.get("benchmark_regime") or {},
        },
        "results": results,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Breakout Regime MA Research",
        "",
        f"- baseline_exp_id: `{BASELINE_EXP_ID}`",
        f"- main_change: `{_path_text(ALLOWED_DIFF_PATH)}`",
        f"- unchanged benchmark_regime: `{json.dumps(base_cfg.get('benchmark_regime') or {}, ensure_ascii=False)}`",
        "",
        "| variant | regime_ma | CAGR | MaxDD | Sharpe | Calmar | Trades | exp_id |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in results:
        lines.append(
            "| {variant} | {regime_ma} | {cagr:.2%} | {max_drawdown:.2%} | {sharpe:.2f} | "
            "{calmar:.2f} | {trades} | `{exp_id}` |".format(**row)
        )
    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if not BASELINE_CFG_PATH.exists():
        raise FileNotFoundError(f"missing baseline config: {BASELINE_CFG_PATH}")
    if not BASELINE_META_PATH.exists():
        raise FileNotFoundError(f"missing baseline meta: {BASELINE_META_PATH}")

    base_cfg = _load_json(BASELINE_CFG_PATH)
    baseline_meta = _load_json(BASELINE_META_PATH)
    _assert_baseline_contract(base_cfg, baseline_meta)

    baseline_regime_ma = int(((base_cfg.get("strategy") or {}).get("params") or {}).get("regime_ma", 60) or 60)
    variants = [
        ("baseline", baseline_regime_ma),
        ("regime_ma_90", 90),
        ("regime_ma_120", 120),
    ]

    print("Audit: only provider-side strategy.params.regime_ma will change.")
    print("Audit: benchmark_regime, costs, universe, execution, and report semantics stay untouched.")
    print("Audit: existing engine still generates signals on day t and queues orders for next-day open.")

    results: list[dict[str, Any]] = []
    for variant_name, regime_ma in variants:
        results.append(
            _run_one(
                variant_name=variant_name,
                regime_ma=regime_ma,
                base_cfg=base_cfg,
                baseline_meta=baseline_meta,
            )
        )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "outputs" / "experiments" / f"regime_ma_research_{stamp}"
    _write_summary(out_dir=out_dir, base_cfg=base_cfg, baseline_meta=baseline_meta, results=results)
    print(f"\nSummary written to {out_dir}")


if __name__ == "__main__":
    main()
