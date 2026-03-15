from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.core.universe.lineage import list_universe_lineage


BASELINE_EXP_ID = "exp_20260307_051743747_77d8"
SCRIPT_GLOB = "backend/scripts/**/*.py"
UNIVERSE_PATTERN = re.compile(r'"universe_mode"\s*:\s*"([A-Z0-9_]+)"')
WB_FALLBACK_PATTERN = re.compile(r'wb_(?:cfg|variant)\.get\("universe_mode",\s*"([A-Z0-9_]+)"\)')


def _repo_root() -> Path:
    return _ROOT


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _baseline_bundle() -> dict[str, Any]:
    exp_dir = _repo_root() / "outputs" / "experiments" / BASELINE_EXP_ID
    run_meta = _load_json(exp_dir / "run_meta.json")
    perf = _load_json(exp_dir / "perf.json")
    universe = run_meta.get("universe") if isinstance(run_meta.get("universe"), dict) else {}
    return {
        "exp_id": BASELINE_EXP_ID,
        "universe": {
            "universe_mode": universe.get("universe_mode"),
            "symbols_source": universe.get("symbols_source"),
            "raw_count": universe.get("raw_count"),
            "tradable_symbols": universe.get("tradable_symbols"),
            "after_filters_symbols": universe.get("after_filters_symbols"),
            "resolve_asof": universe.get("resolve_asof"),
            "dynamic_all_a_entry": universe.get("dynamic_all_a_entry"),
            "index_code": universe.get("index_code"),
            "load_table": universe.get("load_table"),
        },
        "perf": {
            "cagr": perf.get("cagr"),
            "max_drawdown": perf.get("max_drawdown"),
            "sharpe": perf.get("sharpe"),
            "trades": perf.get("trades"),
        },
    }


def _script_universe_inventory() -> dict[str, list[str]]:
    repo = _repo_root()
    out: dict[str, list[str]] = {}
    for path in sorted(repo.glob(SCRIPT_GLOB)):
        if path.name == "universe_data_audit.py":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        modes = set(UNIVERSE_PATTERN.findall(text)) | set(WB_FALLBACK_PATTERN.findall(text))
        if modes:
            out[str(path.relative_to(repo)).replace("\\", "/")] = sorted(modes)
    return out


def _data_cache_inventory() -> list[dict[str, Any]]:
    cache_dir = _repo_root() / "data_cache"
    if not cache_dir.exists():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(cache_dir.iterdir()):
        if not path.is_file():
            continue
        stat = path.stat()
        items.append(
            {
                "name": path.name,
                "bytes": int(stat.st_size),
                "modified_at": stat.st_mtime,
            }
        )
    return items


def _redundancy_findings() -> list[dict[str, Any]]:
    return [
        {
            "surface": "ALL_A runtime lineage",
            "finding": "ALL_A resolves from pit_security_master+pams_ohlcv_daily and does not consume pit_index_constituents.",
            "impact": "CSI constituent imports are not runtime dependencies for ALL_A workflows.",
        },
        {
            "surface": "CSI800 import path",
            "finding": "Historical CSI800 import paths previously replaced the whole pit_index_constituents table.",
            "impact": "CSI1000 rows could be deleted even though runtime consumes them by index_code.",
        },
        {
            "surface": "data_cache/index_stock_cons_000906.csv",
            "finding": "Historical static CSI800 snapshot still exists alongside reconstructed PIT change files.",
            "impact": "Historical cleanup should prefer csi800_pit_changes.csv over static one-shot snapshots when PIT behavior matters.",
        },
        {
            "surface": "CSI1000 imports",
            "finding": "Both static and monthly-reconstructed CSI1000 CSV pipelines exist.",
            "impact": "The static fallback is lower fidelity and should be treated as emergency-only data, not baseline-grade PIT history.",
        },
    ]


def build_audit_report() -> dict[str, Any]:
    lineages = []
    script_inventory = _script_universe_inventory()
    script_mode_index: dict[str, list[str]] = {}
    for path, modes in script_inventory.items():
        for mode in modes:
            script_mode_index.setdefault(mode, []).append(path)
    for lineage in list_universe_lineage():
        record = {
            "mode": lineage.mode,
            "symbols_source": lineage.symbols_source,
            "load_table": lineage.load_table,
            "resolver_entrypoint": lineage.resolver_entrypoint,
            "resolve_asof_policy": lineage.resolve_asof_policy,
            "dynamic_all_a_entry": lineage.dynamic_all_a_entry,
            "import_assets": list(lineage.import_assets),
            "search_workflows": sorted(script_mode_index.get(lineage.mode, [])),
            "notes": lineage.notes,
        }
        lineages.append(record)
    return {
        "baseline_bundle": _baseline_bundle(),
        "universe_lineage": lineages,
        "script_workflow_inventory": script_inventory,
        "data_cache_inventory": _data_cache_inventory(),
        "redundancy_findings": _redundancy_findings(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit universe data lineage and related import assets.")
    parser.add_argument("--output-json", default="", help="optional path to write the audit report as JSON")
    args = parser.parse_args()

    report = build_audit_report()
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output_json:
        out_path = Path(args.output_json)
        if not out_path.is_absolute():
            out_path = (_repo_root() / out_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")
        print(f"written={out_path}")
    print(rendered)


if __name__ == "__main__":
    main()
