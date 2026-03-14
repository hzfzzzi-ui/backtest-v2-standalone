import argparse
import io
import json
import os
import sys
import time
from collections import defaultdict, deque
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


BASE_CFG_PATH = ROOT / "outputs" / "baselines" / "baseline_V10_1" / "config.json"
OUTPUT_ROOT = ROOT / "outputs" / "ops" / "v10_industry_second_stage_s7_20260314"
ENV_PATH = ROOT / ".env"
HARD_GATE_CAGR = 0.10
REFERENCE_EXP_IDS = {
    "0717": "exp_20260314_144431437_56c4",
    "1626": "exp_20260314_144548534_7db9",
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
    "1626": {
        "role": "main",
        "start": "2016-03-01",
        "end": "2026-03-01",
        "periods": {
            "phase_2019_2021_bull": ("2019-01-02", "2021-02-18"),
            "phase_2021_2022_drawdown": ("2021-02-19", "2022-10-31"),
            "phase_2024_2026_recovery": ("2024-02-06", "2026-02-27"),
        },
    },
    "0717": {
        "role": "hard_gate",
        "start": "2007-01-15",
        "end": "2017-01-15",
        "periods": {
            "phase_2009_bull": ("2009-01-05", "2009-12-31"),
            "phase_2010_2013_range": ("2010-01-04", "2013-12-31"),
            "phase_2014_2015_bull": ("2014-01-02", "2015-06-12"),
            "phase_2015_2017_post_crash": ("2015-06-15", "2017-01-13"),
        },
    },
    "0726": {
        "role": "audit",
        "start": "2007-01-15",
        "end": "2026-03-01",
        "periods": {
            "phase_2009_bull": ("2009-01-05", "2009-12-31"),
            "phase_2014_2015_bull": ("2014-01-02", "2015-06-12"),
            "phase_2019_2021_bull": ("2019-01-02", "2021-02-18"),
            "phase_2024_2026_recovery": ("2024-02-06", "2026-02-27"),
        },
    },
}
VARIANTS: list[tuple[str, dict[tuple[Any, ...], Any]]] = [
    ("B0", {}),
    (
        "S7_A_SOFT15",
        {
            ("signal_generation", "ranking", "residual_refine_mode"): "industry_second_stage",
            ("signal_generation", "ranking", "residual_refine_weight"): 0.15,
            ("signal_generation", "ranking", "industry_second_stage_min_industry_score"): 0.85,
        },
    ),
    (
        "S7_B_SOFT25",
        {
            ("signal_generation", "ranking", "residual_refine_mode"): "industry_second_stage",
            ("signal_generation", "ranking", "residual_refine_weight"): 0.25,
            ("signal_generation", "ranking", "industry_second_stage_min_industry_score"): 0.85,
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
    os.environ.setdefault("PAMS_PG_HOST", "127.0.0.1")
    os.environ.setdefault("PAMS_PG_PORT", "5432")
    os.environ.setdefault("PAMS_PG_DBNAME", "pams")
    os.environ.setdefault("PAMS_PG_USER", "pams")
    if os.getenv("POSTGRES_PASSWORD") and not os.getenv("PAMS_PG_PASSWORD"):
        os.environ["PAMS_PG_PASSWORD"] = str(os.getenv("POSTGRES_PASSWORD"))


def _path_text(path: tuple[Any, ...]) -> str:
    return ".".join(str(part) for part in path)


def _set_path(cfg: dict[str, Any], path: tuple[Any, ...], value: Any) -> None:
    cursor: Any = cfg
    for key in path[:-1]:
        if not isinstance(cursor.get(key), dict):
            cursor[key] = {}
        cursor = cursor[key]
    cursor[path[-1]] = value


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
                ("signal_generation", "ranking", "residual_refine_mode"),
                ("signal_generation", "ranking", "residual_refine_weight"),
                ("signal_generation", "ranking", "industry_second_stage_min_industry_score"),
            }
        )
    return allowed


def _assert_variant_contract(base_cfg: dict[str, Any], candidate_cfg: dict[str, Any], *, window_key: str, variant_name: str) -> list[dict[str, Any]]:
    allowed = _allowed_paths(window_key, variant_name)
    diffs = _collect_diffs(base_cfg, candidate_cfg)
    unexpected = [diff for diff in diffs if diff[0] not in allowed]
    if unexpected:
        lines = [
            f"{_path_text(path)}: baseline={base_value!r}, candidate={candidate_value!r}"
            for path, base_value, candidate_value in unexpected[:20]
        ]
        raise RuntimeError(f"{window_key}/{variant_name} drifted beyond allowed paths:\n" + "\n".join(lines))
    return [
        {"path": _path_text(path), "baseline": base_value, "candidate": candidate_value}
        for path, base_value, candidate_value in diffs
    ]


def _build_variant_cfg(window_key: str, variant_name: str, patch: dict[tuple[Any, ...], Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cfg = deepcopy(_BASE_CFG)
    cfg.setdefault("universe", {})["start"] = str(WINDOWS[window_key]["start"])
    cfg.setdefault("universe", {})["end"] = str(WINDOWS[window_key]["end"])
    ranking = cfg.setdefault("signal_generation", {}).setdefault("ranking", {})
    ranking["score_source_mode"] = str(ranking.get("score_source_mode", "residual_only") or "residual_only")
    ranking["residual_window"] = int(ranking.get("residual_window", 40) or 40)
    for path, value in patch.items():
        _set_path(cfg, path, deepcopy(value))
    diff_rows = _assert_variant_contract(_BASE_CFG, cfg, window_key=window_key, variant_name=variant_name)
    return cfg, diff_rows


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _safe_json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _compute_roundtrip_stats(trades_df: pd.DataFrame) -> dict[str, float]:
    stats = {
        "win_rate": 0.0,
        "profit_factor": 0.0,
        "avg_win": 0.0,
        "avg_loss": 0.0,
    }
    if trades_df.empty or "side" not in trades_df.columns:
        return stats
    trades = trades_df.copy()
    trades["date"] = pd.to_datetime(trades["date"], errors="coerce")
    trades = trades.dropna(subset=["date"]).sort_values(["date", "symbol"]).reset_index(drop=True)
    buys = trades[trades["side"].astype(str).str.upper() == "BUY"]
    sells = trades[trades["side"].astype(str).str.upper() == "SELL"]
    fifo: dict[str, deque] = defaultdict(deque)
    for row in buys.itertuples(index=False):
        fifo[str(row.symbol)].append((_safe_float(getattr(row, "fill_price", 0.0), 0.0), int(getattr(row, "qty", 0) or 0)))
    returns: list[float] = []
    for row in sells.itertuples(index=False):
        sym = str(row.symbol)
        if not fifo.get(sym):
            continue
        buy_fill, _ = fifo[sym].popleft()
        sell_fill = _safe_float(getattr(row, "fill_price", 0.0), 0.0)
        if buy_fill <= 1e-8 or sell_fill <= 0:
            continue
        returns.append(sell_fill / buy_fill - 1.0)
    if not returns:
        return stats
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    stats["win_rate"] = float(len(wins) / len(returns))
    stats["profit_factor"] = float(gross_win / gross_loss) if gross_loss > 1e-12 else float("inf")
    stats["avg_win"] = float(sum(wins) / len(wins)) if wins else 0.0
    stats["avg_loss"] = float(sum(losses) / len(losses)) if losses else 0.0
    return stats


def _collect_buy_meta_stats(results_dir: Path) -> dict[str, Any]:
    trades_path = results_dir / "portfolio_trades.csv"
    defaults = {
        "buy_count": 0,
        "observed_refine_modes": "",
        "avg_industry_second_stage_score": 0.0,
        "avg_industry_second_stage_not_hot_score": 0.0,
        "avg_industry_second_stage_uncrowded_score": 0.0,
        "avg_industry_second_stage_breadth_timing_score": 0.0,
        "avg_industry_second_stage_persistence_10d": 0.0,
        "industry_second_stage_active_ratio": 0.0,
    }
    if not trades_path.exists():
        return defaults
    trades = pd.read_csv(trades_path)
    if trades.empty or "side" not in trades.columns:
        return defaults
    buys = trades[trades["side"].astype(str).str.upper() == "BUY"].copy()
    if buys.empty:
        return defaults
    meta_df = pd.DataFrame([_safe_json_dict(value) for value in buys.get("meta_json", [])])
    joined = pd.concat([buys.reset_index(drop=True), meta_df.reset_index(drop=True)], axis=1)
    refine_modes = sorted(
        {str(v).strip().lower() for v in joined.get("residual_refine_mode", pd.Series(dtype=object)).dropna().tolist()}
    )
    return {
        "buy_count": int(len(buys)),
        "observed_refine_modes": ",".join(refine_modes),
        "avg_industry_second_stage_score": float(pd.to_numeric(joined.get("industry_second_stage_score"), errors="coerce").mean() or 0.0),
        "avg_industry_second_stage_not_hot_score": float(pd.to_numeric(joined.get("industry_second_stage_not_hot_score"), errors="coerce").mean() or 0.0),
        "avg_industry_second_stage_uncrowded_score": float(pd.to_numeric(joined.get("industry_second_stage_uncrowded_score"), errors="coerce").mean() or 0.0),
        "avg_industry_second_stage_breadth_timing_score": float(pd.to_numeric(joined.get("industry_second_stage_breadth_timing_score"), errors="coerce").mean() or 0.0),
        "avg_industry_second_stage_persistence_10d": float(pd.to_numeric(joined.get("industry_second_stage_persistence_10d"), errors="coerce").mean() or 0.0),
        "industry_second_stage_active_ratio": float(pd.to_numeric(joined.get("industry_second_stage_active"), errors="coerce").fillna(0.0).mean() or 0.0),
    }


def _load_reference_perf(window_key: str) -> dict[str, Any]:
    exp_id = REFERENCE_EXP_IDS.get(window_key, "")
    if not exp_id:
        return {}
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
        else:
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
        return {"return": 0.0, "max_drawdown": 0.0, "start": start, "end": end, "days": 0}
    sub = sub.sort_values("date").reset_index(drop=True)
    start_nav = _safe_float(sub["nav"].iloc[0], 1.0)
    end_nav = _safe_float(sub["nav"].iloc[-1], 1.0)
    running_peak = sub["nav"].cummax()
    drawdown = sub["nav"] / running_peak - 1.0
    return {
        "return": float(end_nav / start_nav - 1.0) if start_nav > 1e-12 else 0.0,
        "max_drawdown": float(drawdown.min()) if not drawdown.empty else 0.0,
        "start": start,
        "end": end,
        "days": int(len(sub)),
    }


def _variant_meta(variant_name: str) -> tuple[str, float, float]:
    patch = dict(dict(VARIANTS).get(variant_name, {}))
    return (
        str(patch.get(("signal_generation", "ranking", "residual_refine_mode"), "off")),
        float(patch.get(("signal_generation", "ranking", "residual_refine_weight"), 0.0)),
        float(patch.get(("signal_generation", "ranking", "industry_second_stage_min_industry_score"), 0.85)),
    )


def _summarize_results(window_key: str, variant_name: str, result: dict[str, Any]) -> dict[str, Any]:
    exp_id = str(result.get("exp_id") or "")
    results_dir = ROOT / "outputs" / "experiments" / exp_id
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
    trade_stats = _compute_roundtrip_stats(trades_df)
    buy_meta_stats = _collect_buy_meta_stats(results_dir)
    period_metrics = {
        period_name: _period_metrics(nav_df, start=period_start, end=period_end)
        for period_name, (period_start, period_end) in WINDOWS[window_key]["periods"].items()
    }
    refine_mode, refine_weight, min_industry_score = _variant_meta(variant_name)
    summary = {
        "window": window_key,
        "window_role": WINDOWS[window_key]["role"],
        "variant": variant_name,
        "exp_id": exp_id,
        "results_dir": str(results_dir),
        "residual_refine_mode": str(refine_mode),
        "residual_refine_weight": float(refine_weight),
        "industry_second_stage_min_industry_score": float(min_industry_score),
        "total_return": float(perf.get("total_return", result.get("total_return", 0.0)) or 0.0),
        "cagr": float(perf.get("cagr", result.get("cagr", 0.0)) or 0.0),
        "max_drawdown": float(perf.get("max_drawdown", result.get("max_drawdown", 0.0)) or 0.0),
        "sharpe": float(perf.get("sharpe", result.get("sharpe", 0.0)) or 0.0),
        "calmar": float(perf.get("calmar", result.get("calmar", 0.0)) or 0.0),
        "turnover": float(perf.get("turnover", result.get("turnover", 0.0)) or 0.0),
        "trades": int(perf.get("trades", result.get("trades", 0)) or 0),
        "effective_execution_start_date": str(perf.get("effective_execution_start_date") or ""),
        "win_rate": float(trade_stats["win_rate"]),
        "profit_factor": float(trade_stats["profit_factor"]),
        "avg_win": float(trade_stats["avg_win"]),
        "avg_loss": float(trade_stats["avg_loss"]),
        "buy_count": int(buy_meta_stats["buy_count"]),
        "observed_refine_modes": str(buy_meta_stats["observed_refine_modes"]),
        "avg_industry_second_stage_score": float(buy_meta_stats["avg_industry_second_stage_score"]),
        "avg_industry_second_stage_not_hot_score": float(buy_meta_stats["avg_industry_second_stage_not_hot_score"]),
        "avg_industry_second_stage_uncrowded_score": float(buy_meta_stats["avg_industry_second_stage_uncrowded_score"]),
        "avg_industry_second_stage_breadth_timing_score": float(buy_meta_stats["avg_industry_second_stage_breadth_timing_score"]),
        "avg_industry_second_stage_persistence_10d": float(buy_meta_stats["avg_industry_second_stage_persistence_10d"]),
        "industry_second_stage_active_ratio": float(buy_meta_stats["industry_second_stage_active_ratio"]),
        "baseline_match": _baseline_match(window_key, perf) if variant_name == "B0" and window_key in REFERENCE_EXP_IDS else {},
        "period_metrics": period_metrics,
    }
    return summary


def _run_variant(window_key: str, variant_name: str, patch: dict[tuple[Any, ...], Any]) -> dict[str, Any]:
    cfg, diff_rows = _build_variant_cfg(window_key, variant_name, patch)
    request_payload = {
        "config_json": cfg,
        "output_label": f"s7_{window_key.lower()}_{variant_name.lower()}",
    }
    print(f"[{window_key}/{variant_name}] running ...")
    t0 = time.perf_counter()

    def progress(stage: str, payload: dict[str, Any]) -> None:
        pct = payload.get("progress_pct")
        if pct is None:
            return
        print(f"  {stage}: {float(pct):.1f}%")

    result = run_experiment_request(request_payload, progress_hook=progress)
    summary = _summarize_results(window_key, variant_name, result)
    elapsed = time.perf_counter() - t0
    print(
        "  done: "
        f"exp_id={summary['exp_id']} "
        f"cagr={summary['cagr']:.4f} "
        f"sharpe={summary['sharpe']:.4f} "
        f"max_dd={summary['max_drawdown']:.4f} "
        f"active_ratio={summary['industry_second_stage_active_ratio']:.4f} "
        f"elapsed={elapsed:.1f}s"
    )
    return {
        "window": window_key,
        "variant": variant_name,
        "request_payload": request_payload,
        "diff_rows": diff_rows,
        "summary": summary,
    }


def _window_output_dir(window_key: str) -> Path:
    return OUTPUT_ROOT / window_key


def run_window(window_key: str, variant_names: list[str] | None = None) -> list[dict[str, Any]]:
    names = [name for name, _ in VARIANTS] if variant_names is None else list(variant_names)
    variant_map = dict(VARIANTS)
    records: list[dict[str, Any]] = []
    for variant_name in names:
        patch = variant_map[variant_name]
        record = _run_variant(window_key, variant_name, patch)
        records.append(record)
        out_dir = _window_output_dir(window_key) / variant_name
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_json(out_dir / "request_payload.json", record["request_payload"])
        _write_json(out_dir / "diff_rows.json", record["diff_rows"])
        _write_json(out_dir / "summary.json", record["summary"])
    return records


def _gate_rows(summary_map: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant_name, _ in VARIANTS:
        if variant_name == "B0":
            continue
        main = summary_map.get(("1626", variant_name))
        gate = summary_map.get(("0717", variant_name))
        base_main = summary_map.get(("1626", "B0"))
        if not main or not gate or not base_main:
            continue
        main_ok = float(main["cagr"]) >= float(base_main["cagr"]) - 1e-9 and float(main["sharpe"]) >= float(base_main["sharpe"]) - 1e-9
        gate_ok = float(gate["cagr"]) >= HARD_GATE_CAGR
        rows.append(
            {
                "variant": variant_name,
                "main_cagr": float(main["cagr"]),
                "main_sharpe": float(main["sharpe"]),
                "main_max_drawdown": float(main["max_drawdown"]),
                "hard_gate_cagr": float(gate["cagr"]),
                "hard_gate_max_drawdown": float(gate["max_drawdown"]),
                "passes_main_window": bool(main_ok),
                "passes_0717_hard_gate": bool(gate_ok),
                "eligible_for_0726_audit": bool(main_ok and gate_ok),
            }
        )
    return rows


def _write_outputs(records: list[dict[str, Any]], gate_rows: list[dict[str, Any]]) -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    summaries = [record["summary"] for record in records]
    _write_json(OUTPUT_ROOT / "summary_all.json", summaries)
    pd.DataFrame([{key: value for key, value in row.items() if key != "period_metrics"} for row in summaries]).to_csv(
        OUTPUT_ROOT / "summary_all.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(gate_rows).to_csv(OUTPUT_ROOT / "gate_results.csv", index=False, encoding="utf-8-sig")

    comparison_rows: list[dict[str, Any]] = []
    summary_map = {(row["window"], row["variant"]): row for row in summaries}
    for window_key in ("0717", "1626"):
        base = summary_map.get((window_key, "B0"))
        if not base:
            continue
        for variant_name, _ in VARIANTS:
            if variant_name == "B0":
                continue
            row = summary_map.get((window_key, variant_name))
            if not row:
                continue
            comparison_rows.append(
                {
                    "window": window_key,
                    "variant": variant_name,
                    "delta_cagr": float(row["cagr"] - base["cagr"]),
                    "delta_max_drawdown": float(row["max_drawdown"] - base["max_drawdown"]),
                    "delta_sharpe": float(row["sharpe"] - base["sharpe"]),
                    "delta_turnover": float(row["turnover"] - base["turnover"]),
                    "delta_trades": int(row["trades"] - base["trades"]),
                    "delta_active_ratio": float(
                        row["industry_second_stage_active_ratio"] - base.get("industry_second_stage_active_ratio", 0.0)
                    ),
                    "delta_avg_second_stage_score": float(
                        row["avg_industry_second_stage_score"] - base.get("avg_industry_second_stage_score", 0.0)
                    ),
                }
            )
    pd.DataFrame(comparison_rows).to_csv(OUTPUT_ROOT / "comparison.csv", index=False, encoding="utf-8-sig")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", choices=["1626", "0717", "0726", "full"], default="full")
    args = parser.parse_args()

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    if args.window == "1626":
        _write_outputs(run_window("1626"), [])
        return
    if args.window == "0717":
        _write_outputs(run_window("0717"), [])
        return
    if args.window == "0726":
        _write_outputs(run_window("0726"), [])
        return

    all_records: list[dict[str, Any]] = []
    all_records.extend(run_window("1626"))
    all_records.extend(run_window("0717"))
    summary_map = {(record["summary"]["window"], record["summary"]["variant"]): record["summary"] for record in all_records}
    gate_rows = _gate_rows(summary_map)
    survivors = [row["variant"] for row in gate_rows if row["eligible_for_0726_audit"]]
    if survivors:
        audit_variants = ["B0", *[item for item in survivors if item != "B0"]]
        all_records.extend(run_window("0726", variant_names=audit_variants))
    _write_outputs(all_records, gate_rows)


_BASE_CFG = _load_json(BASE_CFG_PATH)
_load_local_env()


if __name__ == "__main__":
    main()
