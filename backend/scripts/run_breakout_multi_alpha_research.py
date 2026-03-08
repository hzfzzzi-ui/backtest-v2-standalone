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

import pandas as pd

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.tools.experiment_runner import run_experiment  # noqa: E402


BASE_EXP_ID = "exp_20260307_171750033_eb7b"
BASE_CFG_PATH = ROOT / "outputs" / "experiments" / BASE_EXP_ID / "run_config.json"
BASE_META_PATH = ROOT / "outputs" / "experiments" / BASE_EXP_ID / "run_meta.json"

PHASE_CONTRACTS: dict[str, dict[str, set[str]]] = {
    "baseline": {
        "config_paths": set(),
        "override_paths": set(),
    },
    "phase1_pullback": {
        "config_paths": {
            "strategy.params.enable_pullback_candidates",
            "strategy.params.pullback_variant_mode",
        },
        "override_paths": set(),
    },
    "phase2_residual_rank": {
        "config_paths": {
            "strategy.params.enable_pullback_candidates",
            "strategy.params.pullback_variant_mode",
            "strategy.params.enable_residual_ranking",
            "strategy.params.residual_window",
        },
        "override_paths": {
            "enable_multifactor_rank",
            "mf_topk",
            "mf_concentrate_topn",
            "mf_concentrate_scale",
            "mf_rank_gate_mode",
        },
    },
    "phase3_multi_score": {
        "config_paths": {
            "strategy.params.enable_pullback_candidates",
            "strategy.params.pullback_variant_mode",
            "strategy.params.enable_residual_ranking",
            "strategy.params.residual_window",
            "strategy.params.enable_sector_quality_ranking",
            "strategy.params.sector_strength_window_short",
            "strategy.params.sector_strength_window_long",
            "strategy.params.volume_quality_window",
            "strategy.params.residual_weight",
            "strategy.params.sector_weight",
            "strategy.params.quality_weight",
        },
        "override_paths": {
            "enable_multifactor_rank",
            "mf_topk",
            "mf_concentrate_topn",
            "mf_concentrate_scale",
            "mf_rank_gate_mode",
        },
    },
}


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
        diffs: list[tuple[tuple[Any, ...], Any, Any]] = []
        for idx, (base_item, candidate_item) in enumerate(zip(base, candidate)):
            diffs.extend(_collect_diffs(base_item, candidate_item, path + (idx,)))
        return diffs
    if base != candidate:
        return [(path, base, candidate)]
    return []


def _assert_allowed_diffs(phase_name: str, base_cfg: dict[str, Any], phase_cfg: dict[str, Any]) -> None:
    allowed = set((PHASE_CONTRACTS.get(phase_name) or {}).get("config_paths", set()))
    diffs = _collect_diffs(base_cfg, phase_cfg)
    unexpected = [diff for diff in diffs if _path_text(diff[0]) not in allowed]
    if unexpected:
        lines = []
        for diff_path, base_value, phase_value in unexpected[:20]:
            lines.append(f"{_path_text(diff_path)}: base={base_value!r}, phase={phase_value!r}")
        raise RuntimeError(f"{phase_name} drifted beyond allowed paths:\n" + "\n".join(lines))


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


def _assert_base_contract(base_cfg: dict[str, Any], base_meta: dict[str, Any]) -> None:
    strategy_name = str((base_cfg.get("strategy") or {}).get("name") or "").strip().lower()
    if strategy_name != "breakout_trend":
        raise RuntimeError(f"expected breakout_trend base, got {strategy_name!r}")
    if str((base_meta.get("data") or {}).get("universe_mode") or "") != "HS300_ZZ500":
        raise RuntimeError("expected HS300_ZZ500 universe")
    if str((base_cfg.get("universe") or {}).get("benchmark") or "") != "000300.SH":
        raise RuntimeError("expected benchmark 000300.SH")
    if not bool(((base_cfg.get("benchmark_regime") or {}).get("enabled"))):
        raise RuntimeError("expected benchmark_regime.enabled=true")
    atr_stop_k = float((((base_cfg.get("strategy") or {}).get("params") or {}).get("atr_stop_k", 0.0) or 0.0))
    if abs(atr_stop_k - 1.0) > 1e-9:
        raise RuntimeError(f"expected current candidate atr_stop_k=1.0, got {atr_stop_k!r}")


def _build_overrides(base_cfg: dict[str, Any], base_meta: dict[str, Any]) -> dict[str, Any]:
    universe = base_cfg.get("universe") or {}
    counters = base_meta.get("counters") if isinstance(base_meta.get("counters"), dict) else {}
    data = base_meta.get("data") if isinstance(base_meta.get("data"), dict) else {}
    return {
        "universe_mode": str(data.get("universe_mode") or "HS300_ZZ500"),
        "start_date": str(universe.get("start") or ""),
        "end_date": str(universe.get("end") or ""),
        "benchmark": str(universe.get("benchmark") or ""),
        "initial_capital": float(base_cfg.get("initial_capital") or 1_000_000),
        "max_positions": int(counters.get("max_positions") or 10),
        "base_order_value": float((base_cfg.get("sizing") or {}).get("order_value", 0.0) or 0.0),
        "fast_mode": False,
        "price_adj": "hfq",
        "enable_multifactor_rank": False,
        "mf_topk": 0,
        "mf_concentrate_topn": 0,
        "mf_concentrate_scale": 1.0,
        "mf_rank_gate_mode": "ALWAYS_ON",
    }


def _build_phase_cfg(base_cfg: dict[str, Any], phase_name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    cfg = deepcopy(base_cfg)
    params = cfg.setdefault("strategy", {}).setdefault("params", {})
    overrides: dict[str, Any] = {}

    if phase_name == "baseline":
        _assert_allowed_diffs(phase_name, base_cfg, cfg)
        return cfg, overrides
    if phase_name == "phase1_pullback":
        params["enable_pullback_candidates"] = True
        params["pullback_variant_mode"] = "pb_reclaim_ma20"
    elif phase_name == "phase2_residual_rank":
        params["enable_pullback_candidates"] = True
        params["pullback_variant_mode"] = "pb_reclaim_ma20"
        params["enable_residual_ranking"] = True
        params["residual_window"] = 60
        overrides.update(
            {
                "enable_multifactor_rank": True,
                "mf_topk": 0,
                "mf_concentrate_topn": 0,
                "mf_concentrate_scale": 1.0,
                "mf_rank_gate_mode": "ALWAYS_ON",
            }
        )
    elif phase_name == "phase3_multi_score":
        params["enable_pullback_candidates"] = True
        params["pullback_variant_mode"] = "pb_reclaim_ma20"
        params["enable_residual_ranking"] = True
        params["residual_window"] = 60
        params["enable_sector_quality_ranking"] = True
        params["sector_strength_window_short"] = 20
        params["sector_strength_window_long"] = 60
        params["volume_quality_window"] = 20
        params["residual_weight"] = 0.5
        params["sector_weight"] = 0.3
        params["quality_weight"] = 0.2
        overrides.update(
            {
                "enable_multifactor_rank": True,
                "mf_topk": 0,
                "mf_concentrate_topn": 0,
                "mf_concentrate_scale": 1.0,
                "mf_rank_gate_mode": "ALWAYS_ON",
            }
        )
    else:
        raise ValueError(f"unknown phase: {phase_name}")

    _assert_allowed_diffs(phase_name, base_cfg, cfg)
    return cfg, overrides


def _static_time_audit() -> dict[str, Any]:
    sim_path = ROOT / "backend" / "core" / "engine_vector" / "portfolio_simulator_strict.py"
    provider_path = ROOT / "backend" / "core" / "engine_vector" / "breakout_signal_provider.py"
    sim_text = sim_path.read_text(encoding="utf-8")
    provider_text = provider_path.read_text(encoding="utf-8")
    checks = {
        "provider_day_signals_call": "provider.day_signals(day, i, ctx)" in sim_text,
        "next_day_queue": "pending[next_day] = [" in sim_text,
        "provider_regime_ma_rolling": "rolling(regime_ma, min_periods=regime_ma)" in provider_text,
        "provider_risk_on_assignment": "self._risk_on[valid_bench] = self._bench_close[valid_bench] > bench_ma[valid_bench]" in provider_text,
    }
    if not all(checks.values()):
        raise RuntimeError(f"time alignment static audit failed: {checks!r}")
    return {"audit_mode": "static_code_contract", "checks": checks, "t1_execution_confirmed": True}


def _compute_trade_stats(results_dir: Path) -> dict[str, Any]:
    trades_path = results_dir / "portfolio_trades.csv"
    if not trades_path.exists():
        return {"win_rate": None, "avg_hold_days": None}
    try:
        tdf = pd.read_csv(trades_path)
    except Exception:
        return {"win_rate": None, "avg_hold_days": None}
    if tdf.empty or "symbol" not in tdf.columns or "side" not in tdf.columns:
        return {"win_rate": None, "avg_hold_days": None}

    tdf["date"] = pd.to_datetime(tdf["date"], errors="coerce")
    tdf["symbol"] = tdf["symbol"].astype(str).str.lower()
    tdf = tdf.dropna(subset=["date", "symbol"])
    if tdf.empty:
        return {"win_rate": None, "avg_hold_days": None}

    open_lots: dict[str, list[dict[str, Any]]] = {}
    realized_rows: list[dict[str, Any]] = []
    for row in tdf.sort_values(["date"]).itertuples(index=False):
        sym = str(getattr(row, "symbol", "")).lower()
        side = str(getattr(row, "side", "")).upper()
        qty = int(float(getattr(row, "qty", 0) or 0))
        price = float(getattr(row, "fill_price", getattr(row, "price", 0.0)) or 0.0)
        day = pd.Timestamp(getattr(row, "date"))
        if qty <= 0 or price <= 0:
            continue
        if side == "BUY":
            open_lots.setdefault(sym, []).append({"qty": qty, "price": price, "date": day})
            continue
        if side != "SELL":
            continue
        remain = qty
        lots = open_lots.get(sym, [])
        while remain > 0 and lots:
            head = lots[0]
            matched = min(remain, int(head["qty"]))
            pnl = (price - float(head["price"])) * matched
            hold_days = int((day - pd.Timestamp(head["date"])).days)
            realized_rows.append({"pnl": pnl, "hold_days": hold_days})
            head["qty"] = int(head["qty"]) - matched
            remain -= matched
            if int(head["qty"]) <= 0:
                lots.pop(0)
        if lots:
            open_lots[sym] = lots

    if not realized_rows:
        return {"win_rate": None, "avg_hold_days": None}
    rdf = pd.DataFrame(realized_rows)
    return {
        "win_rate": float((rdf["pnl"] > 0).mean()),
        "avg_hold_days": float(rdf["hold_days"].mean()),
    }


def _collect_phase_metrics(phase_name: str, result: dict[str, Any]) -> dict[str, Any]:
    results_dir = Path(str(result.get("results_dir") or ""))
    perf = _load_json(results_dir / "perf.json") if results_dir.exists() else {}
    run_meta = _load_json(results_dir / "run_meta.json") if results_dir.exists() else {}
    counters = run_meta.get("counters") if isinstance(run_meta.get("counters"), dict) else {}
    trade_stats = _compute_trade_stats(results_dir) if results_dir.exists() else {"win_rate": None, "avg_hold_days": None}
    return {
        "phase": phase_name,
        "exp_id": str(result.get("exp_id") or ""),
        "results_dir": str(results_dir),
        "raw_signal": int(counters.get("raw_signal", result.get("raw_signal", 0)) or 0),
        "orders": int(counters.get("orders", result.get("orders", 0)) or 0),
        "avg_positions": float(counters.get("avg_positions", result.get("avg_positions", 0.0)) or 0.0),
        "utilization": float(float(counters.get("avg_positions", 0.0) or 0.0) / max(int(counters.get("max_positions", 10) or 10), 1)),
        "cagr": float(perf.get("cagr", result.get("cagr", 0.0)) or 0.0),
        "max_drawdown": float(perf.get("max_drawdown", result.get("max_drawdown", 0.0)) or 0.0),
        "sharpe": float(perf.get("sharpe", result.get("sharpe", 0.0)) or 0.0),
        "calmar": float(perf.get("calmar", result.get("calmar", 0.0)) or 0.0),
        "total_return": float(perf.get("total_return", result.get("total_return", 0.0)) or 0.0),
        "trades": int(perf.get("trades", result.get("trades", 0)) or 0),
        "win_rate": trade_stats["win_rate"],
        "avg_hold_days": trade_stats["avg_hold_days"],
    }


def _build_phase_audit(base_cfg: dict[str, Any], base_meta: dict[str, Any]) -> list[dict[str, Any]]:
    base_overrides = _build_overrides(base_cfg, base_meta)
    rows: list[dict[str, Any]] = []
    for phase_name in ("baseline", "phase1_pullback", "phase2_residual_rank", "phase3_multi_score"):
        phase_cfg, phase_override = _build_phase_cfg(base_cfg, phase_name)
        cfg_diff_paths = sorted(_path_text(path) for path, _, _ in _collect_diffs(base_cfg, phase_cfg))
        combined_overrides = dict(base_overrides)
        combined_overrides.update(phase_override)
        override_diff_paths = sorted(
            key
            for key in sorted(set(base_overrides.keys()) | set(combined_overrides.keys()))
            if base_overrides.get(key) != combined_overrides.get(key)
        )
        allowed = PHASE_CONTRACTS.get(phase_name) or {"config_paths": set(), "override_paths": set()}
        unexpected_cfg = [path for path in cfg_diff_paths if path not in allowed.get("config_paths", set())]
        unexpected_override = [path for path in override_diff_paths if path not in allowed.get("override_paths", set())]
        rows.append(
            {
                "phase": phase_name,
                "config_diff_paths": cfg_diff_paths,
                "override_diff_paths": override_diff_paths,
                "allowed_config_paths": sorted(allowed.get("config_paths", set())),
                "allowed_override_paths": sorted(allowed.get("override_paths", set())),
                "single_path_audit_pass": not unexpected_cfg and not unexpected_override,
                "unexpected_config_paths": unexpected_cfg,
                "unexpected_override_paths": unexpected_override,
            }
        )
    return rows


def _run_one(
    *,
    phase_name: str,
    runtime_cfg: dict[str, Any],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    from backend.api.endpoints.backtest_v2_artifacts import ensure_standard_artifacts

    execution_cfg = deepcopy(runtime_cfg)
    _normalize_db_runtime(execution_cfg)

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(execution_cfg, tmp, ensure_ascii=False, indent=2)
    tmp.close()
    tmp_path = tmp.name

    t0 = time.perf_counter()
    print(f"\n{'=' * 72}")
    print(f"{phase_name}")
    print(f"{'=' * 72}")

    def progress(pct: int, message: str) -> None:
        elapsed = time.perf_counter() - t0
        print(f"  [{pct:3d}%] {message} ({elapsed:.1f}s)")

    try:
        result = run_experiment(tmp_path, preset="single", overrides=overrides, progress_hook=progress)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    results_dir = Path(str(result.get("results_dir") or ""))
    if results_dir.exists():
        result = ensure_standard_artifacts(
            results_dir=results_dir,
            result=result,
            base_cfg=execution_cfg,
            overrides=overrides,
        )
        try:
            from backend.core.report.report_generator import generate_report

            generate_report(str(results_dir))
        except Exception:
            pass
    return _collect_phase_metrics(phase_name, result)


def _write_summary(
    *,
    out_dir: Path,
    base_cfg: dict[str, Any],
    base_meta: dict[str, Any],
    audit: dict[str, Any],
    phase_audit: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    ab_df = pd.DataFrame(results)
    ab_df.to_csv(out_dir / "ab_summary.csv", index=False)

    summary = {
        "generated_at": datetime.now().isoformat(),
        "base_exp_id": BASE_EXP_ID,
        "base_config_path": str(BASE_CFG_PATH),
        "base_meta_path": str(BASE_META_PATH),
        "unchanged_contract": {
            "benchmark": str((base_cfg.get("universe") or {}).get("benchmark") or ""),
            "start": str((base_cfg.get("universe") or {}).get("start") or ""),
            "end": str((base_cfg.get("universe") or {}).get("end") or ""),
            "costs": base_cfg.get("costs") or {},
            "execution": base_cfg.get("execution") or {},
            "benchmark_regime": base_cfg.get("benchmark_regime") or {},
            "universe_mode": str((base_meta.get("data") or {}).get("universe_mode") or ""),
        },
        "static_audit": audit,
        "phase_audit": phase_audit,
        "results": results,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# Breakout Multi Alpha Research",
        "",
        f"- base_exp_id: `{BASE_EXP_ID}`",
        f"- universe_mode: `{(base_meta.get('data') or {}).get('universe_mode', '')}`",
        f"- benchmark: `{(base_cfg.get('universe') or {}).get('benchmark', '')}`",
        f"- static_audit: `{json.dumps(audit, ensure_ascii=False)}`",
        "",
        "## Phase Audit",
        "",
    ]
    for row in phase_audit:
        md_lines.append(
            "- `{phase}`: pass=`{single_path_audit_pass}` | config={config_diff_paths} | overrides={override_diff_paths}".format(
                phase=row["phase"],
                single_path_audit_pass=row["single_path_audit_pass"],
                config_diff_paths=json.dumps(row["config_diff_paths"], ensure_ascii=False),
                override_diff_paths=json.dumps(row["override_diff_paths"], ensure_ascii=False),
            )
        )
    md_lines.extend(
        [
            "",
            "## AB Summary",
            "",
            "| phase | raw_signal | orders | avg_positions | utilization | CAGR | MaxDD | Sharpe | Calmar | trades | win_rate | avg_hold_days | exp_id |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in results:
        win_rate = "-" if row.get("win_rate") is None else f"{float(row['win_rate']):.2%}"
        avg_hold_days = "-" if row.get("avg_hold_days") is None else f"{float(row['avg_hold_days']):.2f}"
        md_lines.append(
            "| {phase} | {raw_signal} | {orders} | {avg_positions:.2f} | {utilization:.2%} | "
            "{cagr:.2%} | {max_drawdown:.2%} | {sharpe:.2f} | {calmar:.2f} | {trades} | "
            f"{win_rate} | {avg_hold_days} | `{row.get('exp_id', '')}` |".format(**row)
        )
    (out_dir / "summary.md").write_text("\n".join(md_lines), encoding="utf-8")


def _dry_run() -> None:
    base_cfg = _load_json(BASE_CFG_PATH)
    base_meta = _load_json(BASE_META_PATH)
    _assert_base_contract(base_cfg, base_meta)
    _static_time_audit()
    phase_audit = _build_phase_audit(base_cfg, base_meta)
    for row in phase_audit:
        if not bool(row.get("single_path_audit_pass")):
            raise RuntimeError(f"phase audit failed: {row}")
    for phase_name in ("baseline", "phase1_pullback", "phase2_residual_rank", "phase3_multi_score"):
        phase_cfg, phase_override = _build_phase_cfg(base_cfg, phase_name)
        combined_overrides = _build_overrides(base_cfg, base_meta)
        combined_overrides.update(phase_override)
        print(json.dumps({"phase": phase_name, "override_keys": sorted(combined_overrides.keys())}, ensure_ascii=False))
        if not isinstance(phase_cfg, dict):
            raise RuntimeError(f"{phase_name} config build failed")
    print("dry-run-ok")


def main(argv: list[str] | None = None) -> None:
    argv = list(argv or sys.argv[1:])
    if not BASE_CFG_PATH.exists():
        raise FileNotFoundError(f"missing base config: {BASE_CFG_PATH}")
    if not BASE_META_PATH.exists():
        raise FileNotFoundError(f"missing base meta: {BASE_META_PATH}")

    if "--dry-run" in argv:
        _dry_run()
        return

    base_cfg = _load_json(BASE_CFG_PATH)
    base_meta = _load_json(BASE_META_PATH)
    _assert_base_contract(base_cfg, base_meta)
    audit = _static_time_audit()
    phase_audit = _build_phase_audit(base_cfg, base_meta)
    failed_phase_audit = [row for row in phase_audit if not bool(row.get("single_path_audit_pass"))]
    if failed_phase_audit:
        raise RuntimeError(f"phase audit failed: {failed_phase_audit}")

    results: list[dict[str, Any]] = []
    for phase_name in ("baseline", "phase1_pullback", "phase2_residual_rank", "phase3_multi_score"):
        phase_cfg, phase_override = _build_phase_cfg(base_cfg, phase_name)
        overrides = _build_overrides(base_cfg, base_meta)
        overrides.update(phase_override)
        results.append(_run_one(phase_name=phase_name, runtime_cfg=phase_cfg, overrides=overrides))

    out_dir = ROOT / "outputs" / "experiments" / f"multi_alpha_research_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    _write_summary(
        out_dir=out_dir,
        base_cfg=base_cfg,
        base_meta=base_meta,
        audit=audit,
        phase_audit=phase_audit,
        results=results,
    )
    print(f"summary_dir={out_dir}")


if __name__ == "__main__":
    main()
