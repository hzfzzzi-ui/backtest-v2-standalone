from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

import pandas as pd

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.services.experiment_runtime_service import run_experiment_request  # noqa: E402


BASE_CFG_PATH = ROOT / "outputs" / "baselines" / "baseline_V10" / "config.json"
OUTPUT_ROOT = ROOT / "outputs" / "ops" / "v10_rotation_replace_minimal_20260313"
ENV_PATH = ROOT / ".env"
REFERENCE_EXP_IDS = {
    "0717": "exp_20260313_035110024_32ed",
    "1626": "exp_20260312_034933994_f811",
}
REFERENCE_PERF_KEYS = (
    "total_return",
    "max_drawdown",
    "cagr",
    "sharpe",
    "calmar",
    "turnover",
    "trades",
    "effective_execution_start_date",
)
WINDOWS: dict[str, dict[str, Any]] = {
    "0717": {
        "start": "2007-01-15",
        "end": "2017-01-15",
        "periods": {
            "phase_2009_bull": ("2009-01-05", "2009-12-31"),
            "phase_2014_2015_bull": ("2014-01-02", "2015-06-12"),
            "phase_2015_2017_post_crash": ("2015-06-15", "2017-01-13"),
        },
    },
    "1626": {
        "start": "2016-03-01",
        "end": "2026-03-01",
        "periods": {
            "phase_2018_bear": ("2018-01-02", "2018-12-28"),
            "phase_2021_2022_drawdown": ("2021-02-19", "2022-10-31"),
            "phase_2024_2026_recovery": ("2024-02-06", "2026-02-27"),
        },
    },
}
VARIANTS: list[tuple[str, dict[str, Any]]] = [
    ("B0", {}),
    (
        "R1",
        {
            "rotation_replace_enabled": True,
            "rotation_replace_only_strong_risk_on": True,
            "rotation_replace_max_swaps_per_day": 1,
            "rotation_replace_candidate_top_n": 3,
            "rotation_replace_min_score_gap": 0.15,
        },
    ),
    (
        "R1b",
        {
            "rotation_replace_enabled": True,
            "rotation_replace_only_strong_risk_on": True,
            "rotation_replace_max_swaps_per_day": 1,
            "rotation_replace_candidate_top_n": 3,
            "rotation_replace_min_score_gap": 0.10,
        },
    ),
]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_local_env() -> None:
    if not ENV_PATH.exists():
        return
    for raw_line in ENV_PATH.read_text(encoding="utf-8-sig").splitlines():
        line = str(raw_line or "").strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = str(key or "").strip()
        if not key:
            continue
        os.environ.setdefault(key, value)
    # Desktop shell cannot resolve docker-internal hostnames; local forwarded port is available.
    os.environ.setdefault("PAMS_PG_HOST", "127.0.0.1")
    os.environ.setdefault("PAMS_PG_PORT", "5432")
    os.environ.setdefault("PAMS_PG_DBNAME", "pams")
    os.environ.setdefault("PAMS_PG_USER", "pams")
    if os.getenv("POSTGRES_PASSWORD") and not os.getenv("PAMS_PG_PASSWORD"):
        os.environ["PAMS_PG_PASSWORD"] = str(os.getenv("POSTGRES_PASSWORD"))


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


def _allowed_paths(window_key: str, variant_name: str) -> set[tuple[Any, ...]]:
    allowed: set[tuple[Any, ...]] = set()
    window = WINDOWS[window_key]
    if str(window["start"]) != str(_BASE_CFG["universe"]["start"]):
        allowed.add(("universe", "start"))
    if str(window["end"]) != str(_BASE_CFG["universe"]["end"]):
        allowed.add(("universe", "end"))
    if variant_name != "B0":
        allowed.update(
            {
                ("sizing", "rotation_replace_enabled"),
                ("sizing", "rotation_replace_only_strong_risk_on"),
                ("sizing", "rotation_replace_max_swaps_per_day"),
                ("sizing", "rotation_replace_candidate_top_n"),
                ("sizing", "rotation_replace_min_score_gap"),
                ("sizing",),
            }
        )
    return allowed


def _assert_variant_contract(base_cfg: dict[str, Any], candidate_cfg: dict[str, Any], *, window_key: str, variant_name: str) -> None:
    allowed = _allowed_paths(window_key, variant_name)
    diffs = _collect_diffs(base_cfg, candidate_cfg)
    unexpected = [diff for diff in diffs if diff[0] not in allowed]
    if unexpected:
        lines = [
            f"{_path_text(path)}: baseline={base_value!r}, candidate={candidate_value!r}"
            for path, base_value, candidate_value in unexpected[:20]
        ]
        raise RuntimeError(
            f"{window_key}/{variant_name} drifted beyond allowed paths:\n" + "\n".join(lines)
        )


def _build_variant_cfg(window_key: str, variant_name: str, rotation_cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = deepcopy(_BASE_CFG)
    cfg.setdefault("universe", {})["start"] = str(WINDOWS[window_key]["start"])
    cfg.setdefault("universe", {})["end"] = str(WINDOWS[window_key]["end"])
    if rotation_cfg:
        sizing = cfg.setdefault("sizing", {})
        for key, value in rotation_cfg.items():
            sizing[key] = value
    _assert_variant_contract(_BASE_CFG, cfg, window_key=window_key, variant_name=variant_name)
    return cfg


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _safe_json_loads(value: Any) -> dict[str, Any]:
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_reference_perf(window_key: str) -> dict[str, Any]:
    exp_id = REFERENCE_EXP_IDS[window_key]
    path = ROOT / "outputs" / "experiments" / exp_id / "perf.json"
    return _load_json(path) if path.exists() else {}


def _baseline_match(window_key: str, perf: dict[str, Any]) -> dict[str, Any]:
    reference_perf = _load_reference_perf(window_key)
    checks: dict[str, Any] = {"reference_exp_id": REFERENCE_EXP_IDS[window_key], "matches": True, "diffs": {}}
    for key in REFERENCE_PERF_KEYS:
        lhs = perf.get(key)
        rhs = reference_perf.get(key)
        if isinstance(lhs, str) or isinstance(rhs, str):
            same = str(lhs or "") == str(rhs or "")
            if not same:
                checks["matches"] = False
                checks["diffs"][key] = {"candidate": lhs, "reference": rhs}
            continue
        same = abs(_safe_float(lhs) - _safe_float(rhs)) <= 1e-9
        if not same:
            checks["matches"] = False
            checks["diffs"][key] = {"candidate": lhs, "reference": rhs}
    return checks


def _period_metrics(nav_df: pd.DataFrame, *, start: str, end: str) -> dict[str, Any]:
    if nav_df.empty:
        return {"return": 0.0, "max_drawdown": 0.0, "start": "", "end": "", "days": 0}
    mask = (nav_df["date"] >= pd.Timestamp(start)) & (nav_df["date"] <= pd.Timestamp(end))
    sub = nav_df.loc[mask].copy()
    if sub.empty:
        return {"return": 0.0, "max_drawdown": 0.0, "start": "", "end": "", "days": 0}
    sub = sub.sort_values("date").reset_index(drop=True)
    nav = sub["nav"].astype(float)
    period_return = float(nav.iloc[-1] / nav.iloc[0] - 1.0) if float(nav.iloc[0]) > 0 else 0.0
    drawdown = nav / nav.cummax() - 1.0
    return {
        "return": float(period_return),
        "max_drawdown": float(drawdown.min()),
        "start": str(sub.iloc[0]["date"].date()),
        "end": str(sub.iloc[-1]["date"].date()),
        "days": int(len(sub)),
    }


def _summarize_results(window_key: str, variant_name: str, result: dict[str, Any]) -> dict[str, Any]:
    results_dir = Path(str(result.get("results_dir") or "")).resolve()
    perf_path = results_dir / "perf.json"
    perf = _load_json(perf_path) if perf_path.exists() else {}
    nav_path = results_dir / "nav.csv"
    nav_df = pd.read_csv(nav_path) if nav_path.exists() else pd.DataFrame(columns=["date", "nav"])
    if not nav_df.empty:
        nav_df["date"] = pd.to_datetime(nav_df["date"], errors="coerce")
        nav_df["nav"] = pd.to_numeric(nav_df["nav"], errors="coerce")
        nav_df = nav_df.dropna(subset=["date", "nav"]).sort_values("date").reset_index(drop=True)
    trades_path = results_dir / "portfolio_trades.csv"
    trades_df = pd.read_csv(trades_path) if trades_path.exists() else pd.DataFrame()
    if not trades_df.empty:
        trades_df["date"] = pd.to_datetime(trades_df["date"], errors="coerce")
        trades_df["side"] = trades_df["side"].astype(str).str.upper()
        trades_df["reason_code"] = trades_df["reason_code"].astype(str).str.upper()
        trades_df["meta_json"] = trades_df["meta_json"].astype(str)
    rotation_sells = trades_df[
        (trades_df.get("side") == "SELL") & (trades_df.get("reason_code") == "ROTATION_REPLACE")
    ].copy() if not trades_df.empty else pd.DataFrame()
    rotation_meta = [_safe_json_loads(value) for value in list(rotation_sells.get("meta_json", []))]
    rotation_gaps = [_safe_float(meta.get("rotation_score_gap")) for meta in rotation_meta if meta]
    window_periods = WINDOWS[window_key]["periods"]
    period_metrics = {
        period_name: _period_metrics(nav_df, start=period_start, end=period_end)
        for period_name, (period_start, period_end) in window_periods.items()
    }
    period_rotation_counts = {
        period_name: int(
            len(
                rotation_sells[
                    (rotation_sells["date"] >= pd.Timestamp(period_start))
                    & (rotation_sells["date"] <= pd.Timestamp(period_end))
                ]
            )
        )
        for period_name, (period_start, period_end) in window_periods.items()
    } if not rotation_sells.empty else {period_name: 0 for period_name in window_periods}

    summary = {
        "window": window_key,
        "variant": variant_name,
        "exp_id": str(result.get("exp_id") or ""),
        "results_dir": str(results_dir),
        "total_return": float(perf.get("total_return", result.get("total_return", 0.0)) or 0.0),
        "cagr": float(perf.get("cagr", result.get("cagr", 0.0)) or 0.0),
        "max_drawdown": float(perf.get("max_drawdown", result.get("max_drawdown", 0.0)) or 0.0),
        "sharpe": float(perf.get("sharpe", result.get("sharpe", 0.0)) or 0.0),
        "calmar": float(perf.get("calmar", result.get("calmar", 0.0)) or 0.0),
        "turnover": float(perf.get("turnover", result.get("turnover", 0.0)) or 0.0),
        "trades": int(perf.get("trades", result.get("trades", 0)) or 0),
        "effective_execution_start_date": str(perf.get("effective_execution_start_date") or ""),
        "rotation_replace_sell_count": int(len(rotation_sells)),
        "rotation_replace_day_count": int(rotation_sells["date"].dt.normalize().nunique()) if not rotation_sells.empty else 0,
        "rotation_replace_avg_score_gap": float(sum(rotation_gaps) / len(rotation_gaps)) if rotation_gaps else 0.0,
        "rotation_replace_max_score_gap": float(max(rotation_gaps)) if rotation_gaps else 0.0,
        "period_metrics": period_metrics,
        "period_rotation_counts": period_rotation_counts,
    }
    if variant_name == "B0":
        summary["baseline_match"] = _baseline_match(window_key, perf)
    return summary


def _run_one(window_key: str, variant_name: str, rotation_cfg: dict[str, Any]) -> dict[str, Any]:
    semantic_cfg = _build_variant_cfg(window_key, variant_name, rotation_cfg)
    request_payload = {
        "preset": "single",
        "config_json": semantic_cfg,
        "fast_mode": True,
    }
    t0 = time.perf_counter()
    print(f"\n{'=' * 84}")
    print(f"{window_key} / {variant_name}")
    print(f"{'=' * 84}")

    def progress(pct: int, message: str) -> None:
        elapsed = time.perf_counter() - t0
        print(f"  [{pct:3d}%] {message} ({elapsed:.1f}s)")

    result = run_experiment_request(request_payload, progress_hook=progress)
    summary = _summarize_results(window_key, variant_name, result)
    elapsed = time.perf_counter() - t0
    print(
        "  done: "
        f"exp_id={summary['exp_id']} "
        f"cagr={summary['cagr']:.4f} "
        f"max_dd={summary['max_drawdown']:.4f} "
        f"rotation_sells={summary['rotation_replace_sell_count']} "
        f"elapsed={elapsed:.1f}s"
    )
    return {
        "window": window_key,
        "variant": variant_name,
        "request_payload": request_payload,
        "summary": summary,
    }


def _window_output_dir(window_key: str) -> Path:
    return OUTPUT_ROOT / window_key


def run_window(window_key: str) -> list[dict[str, Any]]:
    if window_key not in WINDOWS:
        raise RuntimeError(f"unsupported window: {window_key}")
    output_dir = _window_output_dir(window_key)
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for variant_name, rotation_cfg in VARIANTS:
        record = _run_one(window_key, variant_name, rotation_cfg)
        records.append(record)
        _write_json(output_dir / f"request_payload_{variant_name}.json", record["request_payload"])
    summaries = [record["summary"] for record in records]
    _write_json(output_dir / f"summary_{window_key}.json", summaries)
    rows: list[dict[str, Any]] = []
    for summary in summaries:
        row = {
            key: value
            for key, value in summary.items()
            if key not in {"period_metrics", "period_rotation_counts", "baseline_match"}
        }
        for period_name, metrics in dict(summary.get("period_metrics") or {}).items():
            row[f"{period_name}_return"] = float(metrics.get("return", 0.0) or 0.0)
            row[f"{period_name}_max_drawdown"] = float(metrics.get("max_drawdown", 0.0) or 0.0)
            row[f"{period_name}_days"] = int(metrics.get("days", 0) or 0)
        for period_name, count in dict(summary.get("period_rotation_counts") or {}).items():
            row[f"{period_name}_rotation_count"] = int(count or 0)
        if isinstance(summary.get("baseline_match"), dict):
            row["baseline_match"] = bool(summary["baseline_match"].get("matches"))
        rows.append(row)
    pd.DataFrame(rows).to_csv(output_dir / f"summary_{window_key}.csv", index=False, encoding="utf-8-sig")
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", choices=["0717", "1626", "all"], default="all")
    args = parser.parse_args()

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    if args.window == "all":
        all_records: list[dict[str, Any]] = []
        for window_key in ("0717", "1626"):
            all_records.extend(run_window(window_key))
        _write_json(OUTPUT_ROOT / "summary_all.json", [record["summary"] for record in all_records])
        pd.DataFrame([record["summary"] for record in all_records]).to_csv(
            OUTPUT_ROOT / "summary_all.csv",
            index=False,
            encoding="utf-8-sig",
        )
        return
    run_window(args.window)


_load_local_env()
_BASE_CFG = _load_json(BASE_CFG_PATH)


if __name__ == "__main__":
    main()
