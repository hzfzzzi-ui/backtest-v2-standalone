from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.scripts.run_breakout_multi_alpha_research import (  # noqa: E402
    BASE_CFG_PATH,
    BASE_EXP_ID,
    BASE_META_PATH,
    _assert_base_contract,
    _build_overrides,
    _collect_diffs,
    _load_json,
    _path_text,
    _run_one,
    _static_time_audit,
)


PHASE_CONTRACTS: dict[str, dict[str, set[str]]] = {
    "baseline": {
        "config_paths": set(),
        "override_paths": set(),
    },
    "breakout_window_45": {
        "config_paths": {
            "strategy.params.breakout_window",
        },
        "override_paths": set(),
    },
    "breakout_window_40": {
        "config_paths": {
            "strategy.params.breakout_window",
        },
        "override_paths": set(),
    },
}


def _assert_allowed_diffs(phase_name: str, base_cfg: dict[str, Any], phase_cfg: dict[str, Any]) -> None:
    allowed = set((PHASE_CONTRACTS.get(phase_name) or {}).get("config_paths", set()))
    diffs = _collect_diffs(base_cfg, phase_cfg)
    unexpected = [diff for diff in diffs if _path_text(diff[0]) not in allowed]
    if unexpected:
        lines = []
        for diff_path, base_value, phase_value in unexpected[:20]:
            lines.append(f"{_path_text(diff_path)}: base={base_value!r}, phase={phase_value!r}")
        raise RuntimeError(f"{phase_name} drifted beyond allowed paths:\n" + "\n".join(lines))


def _build_phase_cfg(base_cfg: dict[str, Any], phase_name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    cfg = json.loads(json.dumps(base_cfg))
    params = cfg.setdefault("strategy", {}).setdefault("params", {})
    overrides: dict[str, Any] = {}

    if phase_name == "baseline":
        _assert_allowed_diffs(phase_name, base_cfg, cfg)
        return cfg, overrides
    if phase_name == "breakout_window_45":
        params["breakout_window"] = 45
    elif phase_name == "breakout_window_40":
        params["breakout_window"] = 40
    else:
        raise ValueError(f"unknown phase: {phase_name}")

    _assert_allowed_diffs(phase_name, base_cfg, cfg)
    return cfg, overrides


def _build_phase_audit(base_cfg: dict[str, Any], base_meta: dict[str, Any]) -> list[dict[str, Any]]:
    base_overrides = _build_overrides(base_cfg, base_meta)
    rows: list[dict[str, Any]] = []
    for phase_name in ("baseline", "breakout_window_45", "breakout_window_40"):
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
                "single_path_audit_pass": not unexpected_cfg and not unexpected_override,
                "unexpected_config_paths": unexpected_cfg,
                "unexpected_override_paths": unexpected_override,
            }
        )
    return rows


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
        "main_change_path": "strategy.params.breakout_window",
        "base_breakout_window": int(((base_cfg.get("strategy") or {}).get("params") or {}).get("breakout_window", 0) or 0),
        "unchanged_contract": {
            "benchmark": str((base_cfg.get("universe") or {}).get("benchmark") or ""),
            "start": str((base_cfg.get("universe") or {}).get("start") or ""),
            "end": str((base_cfg.get("universe") or {}).get("end") or ""),
            "costs": base_cfg.get("costs") or {},
            "execution": base_cfg.get("execution") or {},
            "benchmark_regime": base_cfg.get("benchmark_regime") or {},
            "atr_stop_k": float((((base_cfg.get("strategy") or {}).get("params") or {}).get("atr_stop_k", 0.0) or 0.0)),
        },
        "static_audit": audit,
        "phase_audit": phase_audit,
        "results": results,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Breakout Window Research",
        "",
        f"- base_exp_id: `{BASE_EXP_ID}`",
        f"- main_change: `strategy.params.breakout_window`",
        f"- unchanged atr_stop_k: `{(((base_cfg.get('strategy') or {}).get('params') or {}).get('atr_stop_k', 0.0))}`",
        f"- static_audit: `{json.dumps(audit, ensure_ascii=False)}`",
        "",
        "## Phase Audit",
        "",
    ]
    for row in phase_audit:
        lines.append(
            "- `{phase}`: pass=`{single_path_audit_pass}` | config={config_diff_paths} | overrides={override_diff_paths}".format(
                phase=row["phase"],
                single_path_audit_pass=row["single_path_audit_pass"],
                config_diff_paths=json.dumps(row["config_diff_paths"], ensure_ascii=False),
                override_diff_paths=json.dumps(row["override_diff_paths"], ensure_ascii=False),
            )
        )
    lines.extend(
        [
            "",
            "## AB Summary",
            "",
            "| phase | breakout_window | raw_signal | orders | avg_positions | utilization | CAGR | MaxDD | Sharpe | Calmar | trades | win_rate | avg_hold_days | exp_id |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in results:
        win_rate = "-" if row.get("win_rate") is None else f"{float(row['win_rate']):.2%}"
        avg_hold_days = "-" if row.get("avg_hold_days") is None else f"{float(row['avg_hold_days']):.2f}"
        lines.append(
            "| {phase} | {breakout_window} | {raw_signal} | {orders} | {avg_positions:.2f} | {utilization:.2%} | "
            "{cagr:.2%} | {max_drawdown:.2%} | {sharpe:.2f} | {calmar:.2f} | {trades} | "
            f"{win_rate} | {avg_hold_days} | `{row.get('exp_id', '')}` |".format(**row)
        )
    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def _dry_run() -> None:
    base_cfg = _load_json(BASE_CFG_PATH)
    base_meta = _load_json(BASE_META_PATH)
    _assert_base_contract(base_cfg, base_meta)
    _static_time_audit()
    phase_audit = _build_phase_audit(base_cfg, base_meta)
    for row in phase_audit:
        if not bool(row.get("single_path_audit_pass")):
            raise RuntimeError(f"phase audit failed: {row}")
    for phase_name in ("baseline", "breakout_window_45", "breakout_window_40"):
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
    phase_to_window = {
        "baseline": int(((base_cfg.get("strategy") or {}).get("params") or {}).get("breakout_window", 0) or 0),
        "breakout_window_45": 45,
        "breakout_window_40": 40,
    }
    for phase_name in ("baseline", "breakout_window_45", "breakout_window_40"):
        phase_cfg, phase_override = _build_phase_cfg(base_cfg, phase_name)
        overrides = _build_overrides(base_cfg, base_meta)
        overrides.update(phase_override)
        row = _run_one(phase_name=phase_name, runtime_cfg=phase_cfg, overrides=overrides)
        row["breakout_window"] = int(phase_to_window[phase_name])
        results.append(row)

    out_dir = ROOT / "outputs" / "experiments" / f"breakout_window_research_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
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
