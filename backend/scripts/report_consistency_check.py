from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.scripts._internal_helper import open_experiment_handle, read_json_artifact


def _check_exp(rd: Path) -> dict[str, Any]:
    resolved_dir, manifest = open_experiment_handle(results_dir=rd)
    exp_id = resolved_dir.name
    run_config = read_json_artifact(results_dir=resolved_dir, rel_path="run_config.json", fallback_rel_path="run_config.json")
    run_meta = read_json_artifact(results_dir=resolved_dir, artifact_key="run_meta", fallback_rel_path="run_meta.json")
    perf = read_json_artifact(results_dir=resolved_dir, artifact_key="perf", fallback_rel_path="perf.json")

    uni = run_config.get("universe") if isinstance(run_config.get("universe"), dict) else {}
    data = run_meta.get("data") if isinstance(run_meta.get("data"), dict) else {}
    report_consistency = run_meta.get("report_consistency") if isinstance(run_meta.get("report_consistency"), dict) else {}
    metrics = manifest.get("metrics") if isinstance(manifest.get("metrics"), dict) else {}

    start_ok = str(data.get("start") or "") == str(uni.get("start") or "")
    end_ok = str(data.get("end") or "") == str(uni.get("end") or "")
    benchmark_ok = str(data.get("benchmark") or "") == str(uni.get("benchmark") or "")
    source_tag_ok = bool(report_consistency.get("sources"))

    manifest_perf_ok = (
        metrics.get("cagr") == perf.get("cagr")
        and metrics.get("max_drawdown") == perf.get("max_drawdown")
        and metrics.get("trades") == perf.get("trades")
    )
    manifest_core_ok = isinstance(manifest.get("core_artifacts"), dict) and "perf" in manifest.get("core_artifacts", {})

    all_pass = all([start_ok, end_ok, benchmark_ok, source_tag_ok, manifest_perf_ok, manifest_core_ok])
    return {
        "exp_id": exp_id,
        "start_ok": start_ok,
        "end_ok": end_ok,
        "benchmark_ok": benchmark_ok,
        "source_tag_ok": source_tag_ok,
        "manifest_perf_ok": manifest_perf_ok,
        "manifest_core_ok": manifest_core_ok,
        "all_pass": all_pass,
    }


def main() -> None:
    root = Path("outputs/experiments")
    targets = [
        "exp_20260306_203305",
        "exp_20260306_211811",
        "exp_20260307_014641",
    ]
    rows = []
    for exp_id in targets:
        rd = root / exp_id
        if not rd.exists():
            rows.append({"exp_id": exp_id, "all_pass": False, "error": "missing_experiment_dir"})
            continue
        try:
            rows.append(_check_exp(rd))
        except Exception as exc:
            rows.append({"exp_id": exp_id, "all_pass": False, "error": str(exc)})

    out = Path("docs") / "report_consistency_check_2026-03-07.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({k for r in rows for k in r.keys()})
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"wrote {out}")
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
