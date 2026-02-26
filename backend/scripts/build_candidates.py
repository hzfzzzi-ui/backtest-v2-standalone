from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

MDD_LIMIT = -0.20
TOP_N = 10
MIN_TIER = "T2"
OUTPUT_DIR = "outputs"

TIER_RANK = {"T0": 0, "T1": 1, "T2": 2, "T3": 3}
SCORECARD_RANK = {"D": 0, "C": 1, "B": 2, "A": 3, "A+": 4}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _to_float(v: Any) -> float | None:
    if v in (None, ""):
        return None
    try:
        return float(v)
    except Exception:
        return None


def _to_int(v: Any) -> int | None:
    if v in (None, ""):
        return None
    try:
        return int(float(v))
    except Exception:
        return None


def _resolve_results_dir(*, repo_root: Path, exp_id: str | None, results_dir: str | None) -> Path:
    if results_dir:
        p = Path(results_dir)
        return p.resolve() if p.is_absolute() else (repo_root / p).resolve()
    if not exp_id:
        raise ValueError("either --exp_id or --results_dir is required")
    candidates = [
        (repo_root / OUTPUT_DIR / "experiments" / exp_id).resolve(),
        (repo_root / OUTPUT_DIR / exp_id).resolve(),
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(f"unable to resolve results_dir for exp_id={exp_id}")


def _scorecard_value(perf: dict[str, Any], run_meta: dict[str, Any]) -> tuple[str | None, str]:
    explicit = str(run_meta.get("scorecard") or perf.get("scorecard") or "").strip().upper()
    if explicit in SCORECARD_RANK:
        return explicit, "explicit"

    cagr = _to_float(perf.get("cagr"))
    mdd = _to_float(perf.get("max_drawdown"))
    sharpe = _to_float(perf.get("sharpe"))
    if cagr is None or mdd is None or sharpe is None:
        return None, "missing_metrics"

    if sharpe >= 1.5 and cagr >= 0.15 and mdd >= -0.12:
        return "A", "approx"
    if sharpe >= 1.0 and cagr >= 0.08 and mdd >= -0.18:
        return "B", "approx"
    if sharpe >= 0.5 and cagr >= 0.02 and mdd >= -0.25:
        return "C", "approx"
    return "D", "approx"


def _load_reason_summary(path: Path, topk: int = 10) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except Exception:
        return []
    if not lines:
        return []
    cols = [x.strip() for x in lines[0].split(",")]
    if not {"code", "count"}.issubset(set(cols)):
        return []
    i_code = cols.index("code")
    i_count = cols.index("count")
    i_ratio = cols.index("ratio") if "ratio" in cols else -1
    for line in lines[1:]:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) <= max(i_code, i_count):
            continue
        code = parts[i_code]
        count = _to_int(parts[i_count]) or 0
        ratio = _to_float(parts[i_ratio]) if i_ratio >= 0 and len(parts) > i_ratio else None
        if code or count > 0:
            rows.append({"code": code, "count": count, "ratio": ratio})
    rows.sort(key=lambda x: (-int(x.get("count") or 0), str(x.get("code") or "")))
    return rows[:topk]


def _select_groups(results_dir: Path, manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    groups = list(manifest.get("groups") or [])
    if not groups:
        warnings.append("manifest.groups is empty")
        return [], warnings

    selected: list[dict[str, Any]] = []
    for g in sorted(groups, key=lambda x: str((x or {}).get("group_id") or "")):
        if not isinstance(g, dict):
            continue
        gid = str(g.get("group_id") or "").strip()
        if not gid:
            continue
        gfiles = dict(g.get("group_files") or {})
        gdir = str(g.get("group_dir") or "").strip()
        group_dir = (results_dir / gdir).resolve() if gdir else (results_dir / "groups" / gid).resolve()
        perf_path = (results_dir / str(gfiles.get("perf") or "")).resolve() if gfiles.get("perf") else (group_dir / "perf.json")
        run_meta_path = (results_dir / str(gfiles.get("run_meta") or "")).resolve() if gfiles.get("run_meta") else (group_dir / "run_meta.json")
        reason_path = (results_dir / str(gfiles.get("reason_codes") or "")).resolve() if gfiles.get("reason_codes") else (group_dir / "reason_code_counts.csv")

        perf = _load_json(perf_path)
        run_meta = _load_json(run_meta_path)
        tier = str(g.get("tier") or run_meta.get("tier") or "").upper()
        if tier not in TIER_RANK:
            tier = "T0"
        if TIER_RANK[tier] < TIER_RANK[MIN_TIER]:
            continue

        mdd = _to_float(perf.get("max_drawdown"))
        if mdd is None or mdd < MDD_LIMIT:
            continue

        scorecard, score_src = _scorecard_value(perf, run_meta)
        if scorecard is None:
            warnings.append(f"{gid}: scorecard missing and approximation unavailable; skipped scorecard filter")
        elif SCORECARD_RANK.get(scorecard, -1) < SCORECARD_RANK["B"]:
            continue

        red_flags = run_meta.get("red_flags")
        if isinstance(red_flags, list):
            if len(red_flags) > 0:
                continue
        else:
            warnings.append(f"{gid}: red_flags unavailable; red-flag filter skipped")

        counters = dict(run_meta.get("counters") or {})
        reasons = _load_reason_summary(reason_path, topk=10)
        cagr = _to_float(perf.get("cagr"))
        sharpe = _to_float(perf.get("sharpe"))
        rank_score = (cagr or 0.0) + (sharpe or 0.0) * 0.05 + (mdd or 0.0) * 0.5
        selected.append(
            {
                "group_id": gid,
                "tier": tier,
                "scorecard": scorecard,
                "scorecard_source": score_src,
                "rank_score": rank_score,
                "metrics": {
                    "cagr": cagr,
                    "max_drawdown": mdd,
                    "sharpe": sharpe,
                    "total_return": _to_float(perf.get("total_return")),
                    "trades": _to_int(perf.get("trades")),
                },
                "triggers": {
                    "gate_on_rate": _to_float(counters.get("gate_on_rate")),
                    "mf_rank_applied_rate": _to_float(counters.get("mf_rank_applied_rate")),
                    "trend_slope_block_count": _to_int(counters.get("trend_slope_block_count")),
                    "atr_stop_exit_count": _to_int(counters.get("atr_stop_exit_count")),
                    "atr_trail_exit_count": _to_int(counters.get("atr_trail_exit_count")),
                    "atr_trail_update_count": _to_int(counters.get("atr_trail_update_count")),
                },
                "reason_codes_top10": reasons,
                "why": {
                    "tier_ok": True,
                    "mdd_ok": True,
                    "scorecard_ok": (scorecard is None) or (SCORECARD_RANK.get(scorecard, -1) >= SCORECARD_RANK["B"]),
                    "reason_summary": [r.get("code") for r in reasons[:3]],
                },
            }
        )

    selected.sort(key=lambda x: (-float(x.get("rank_score") or 0.0), str(x.get("group_id") or "")))
    return selected[:TOP_N], sorted(set(warnings))


def build_outputs(results_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = results_dir / "manifest.json"
    manifest = _load_json(manifest_path)
    if not manifest:
        raise FileNotFoundError(f"manifest not found or invalid: {manifest_path}")

    candidates, warnings = _select_groups(results_dir, manifest)
    exp_id = str(manifest.get("exp_id") or results_dir.name)
    preset = str(manifest.get("preset") or "")
    dims = dict(manifest.get("dims") or {})

    candidates_obj = {
        "exp_id": exp_id,
        "preset": preset,
        "source_results_dir": str(results_dir),
        "filters": {
            "min_tier": MIN_TIER,
            "min_scorecard": "B",
            "max_drawdown_limit": MDD_LIMIT,
            "top_n": TOP_N,
        },
        "warnings": warnings,
        "dims": dims,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
    execution_obj = {
        "exp_id": exp_id,
        "source_results_dir": str(results_dir),
        "strategy_version": "v1",
        "candidates_count": len(candidates),
        "items": [
            {
                "date": "",
                "strategy_group": str(c.get("group_id") or ""),
                "status": "PENDING",
                "target_positions": [],
                "notes": "",
            }
            for c in candidates
        ],
    }
    return candidates_obj, execution_obj


def main() -> int:
    parser = argparse.ArgumentParser(description="Build candidate list and execution skeleton from experiment outputs.")
    parser.add_argument("--exp_id", type=str, default="", help="Experiment ID (resolved under outputs/experiments/<exp_id>).")
    parser.add_argument("--results_dir", type=str, default="", help="Explicit results_dir path.")
    parser.add_argument("--out_dir", type=str, default=OUTPUT_DIR, help="Output directory for candidates.json and execution_list.json.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    results_dir = _resolve_results_dir(
        repo_root=repo_root,
        exp_id=(args.exp_id.strip() or None),
        results_dir=(args.results_dir.strip() or None),
    )
    candidates_obj, execution_obj = build_outputs(results_dir)

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = (repo_root / out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    c_path = out_dir / "candidates.json"
    e_path = out_dir / "execution_list.json"
    c_path.write_text(json.dumps(candidates_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    e_path.write_text(json.dumps(execution_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote: {c_path}")
    print(f"wrote: {e_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
