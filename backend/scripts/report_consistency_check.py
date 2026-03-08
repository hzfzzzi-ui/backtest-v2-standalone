from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.scripts._internal_helper import (
    ensure_optional_report,
    open_experiment_handle,
    read_json_artifact,
)
def _check_exp(rd: Path) -> dict[str, Any]:
    resolved_dir, _manifest = open_experiment_handle(results_dir=rd)
    exp_id = resolved_dir.name
    run_config = read_json_artifact(results_dir=resolved_dir, rel_path="run_config.json", fallback_rel_path="run_config.json")
    run_meta = read_json_artifact(results_dir=resolved_dir, artifact_key="run_meta", fallback_rel_path="run_meta.json")
    perf = read_json_artifact(results_dir=resolved_dir, artifact_key="perf", fallback_rel_path="perf.json")

    report_path = ensure_optional_report(results_dir=resolved_dir, generate_if_missing=True)
    report_html = report_path.read_text(encoding="utf-8") if report_path and report_path.exists() else ""

    uni = run_config.get("universe") if isinstance(run_config.get("universe"), dict) else {}
    data = run_meta.get("data") if isinstance(run_meta.get("data"), dict) else {}

    start_ok = str(data.get("start") or "") == str(uni.get("start") or "")
    end_ok = str(data.get("end") or "") == str(uni.get("end") or "")
    benchmark_ok = str(data.get("benchmark") or "") == str(uni.get("benchmark") or "")

    range_text = f"{uni.get('start')} ~ {uni.get('end')}"
    report_range_ok = range_text in report_html
    report_benchmark_ok = str(uni.get("benchmark") or "") in report_html

    perf_ok = True
    cagr = perf.get("cagr")
    if cagr is not None:
        cagr_text = f"{float(cagr) * 100:.2f}%"
        perf_ok = cagr_text in report_html

    funnel_exists = (resolved_dir / "funnel.csv").exists()
    funnel_source_ok = ("数据源: funnel.csv" in report_html) if funnel_exists else True

    report_consistency = run_meta.get("report_consistency") if isinstance(run_meta.get("report_consistency"), dict) else {}
    source_tag_ok = bool(report_consistency.get("sources"))

    all_pass = all([start_ok, end_ok, benchmark_ok, report_range_ok, report_benchmark_ok, perf_ok, funnel_source_ok, source_tag_ok])
    return {
        "exp_id": exp_id,
        "start_ok": start_ok,
        "end_ok": end_ok,
        "benchmark_ok": benchmark_ok,
        "report_range_ok": report_range_ok,
        "report_benchmark_ok": report_benchmark_ok,
        "perf_ok": perf_ok,
        "funnel_source_ok": funnel_source_ok,
        "source_tag_ok": source_tag_ok,
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
