from __future__ import annotations

import io
import json
import math
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
OUTPUT_ROOT = ROOT / "outputs" / "ops" / "v10_regime_source_minimal_20260313"
ENV_PATH = ROOT / ".env"
REFERENCE_EXP_ID = "exp_20260312_034933994_f811"
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
PHASES: dict[str, tuple[str, str]] = {
    "phase_2018_bear": ("2018-01-02", "2018-12-28"),
    "phase_2019_2021_bull": ("2019-01-02", "2021-02-18"),
    "phase_2021_2022_drawdown": ("2021-02-19", "2022-10-31"),
    "phase_2022_2024_weak": ("2022-11-01", "2024-02-05"),
    "phase_2024_2026_recovery": ("2024-02-06", "2026-02-27"),
}
PHASE_LABELS = {
    "phase_2018_bear": "2018 单边熊",
    "phase_2019_2021_bull": "2019-2021 核心资产牛",
    "phase_2021_2022_drawdown": "2021-2022 杀估值回撤",
    "phase_2022_2024_weak": "2022-2024 弱市探底",
    "phase_2024_2026_recovery": "2024-2026 政策修复",
}
VARIANTS: list[dict[str, Any]] = [
    {
        "name": "B0_HS300",
        "label": "HS300 benchmark regime 基线",
        "description": "保持 V10 baseline 不变。",
        "mutations": {},
    },
    {
        "name": "R_CSI800_BENCH",
        "label": "CSI800 benchmark regime",
        "description": "只把 universe.benchmark 从 000300.SH 切到 000906.SH。由于当前引擎共用 benchmark 数据源，benchmark_regime 和 market_filter 会同时改用 CSI800。",
        "mutations": {
            ("universe", "benchmark"): "000906.SH",
        },
    },
    {
        "name": "R_BREADTH_REGIME",
        "label": "Breadth regime 代理",
        "description": "关闭 benchmark_regime，启用现成 breadth_momo 动态 max_positions，并把 min_positions 设为 0，使其能充当宽度 regime。",
        "mutations": {
            ("benchmark_regime", "enabled"): False,
            (
                "position_risk",
                "breadth",
            ): {
                "enabled": True,
                "mode": "dynamic_maxpos",
                "score_type": "B",
                "mapping_mode": "smooth",
                "min_positions": 0,
                "max_positions": 10,
                "step_high": 0.60,
                "step_mid": 0.45,
                "smooth_lo": 0.40,
                "smooth_range": 0.20,
                "ema_fast": 8,
                "ema_slow": 25,
                "gate_threshold": 0.45,
                "gate_quantile_window": 252,
                "gate_quantile_pct": 0.20,
                "gate_persist_days": 3,
                "size_scale_floor": 0.30,
            },
        },
    },
]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_local_env() -> None:
    if ENV_PATH.exists():
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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return float(default)
    if math.isnan(out) or math.isinf(out):
        return float(default)
    return float(out)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


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


def _set_path(cfg: dict[str, Any], path: tuple[Any, ...], value: Any) -> None:
    cursor: Any = cfg
    for key in path[:-1]:
        if not isinstance(cursor.get(key), dict):
            cursor[key] = {}
        cursor = cursor[key]
    cursor[path[-1]] = value


def _allowed_paths(variant_name: str) -> set[tuple[Any, ...]]:
    allowed: set[tuple[Any, ...]] = set()
    if variant_name == "R_CSI800_BENCH":
        allowed.add(("universe", "benchmark"))
    if variant_name == "R_BREADTH_REGIME":
        allowed.update(
            {
                ("benchmark_regime", "enabled"),
                ("position_risk", "breadth"),
                ("position_risk", "breadth", "enabled"),
                ("position_risk", "breadth", "mode"),
                ("position_risk", "breadth", "score_type"),
                ("position_risk", "breadth", "mapping_mode"),
                ("position_risk", "breadth", "min_positions"),
                ("position_risk", "breadth", "max_positions"),
                ("position_risk", "breadth", "step_high"),
                ("position_risk", "breadth", "step_mid"),
                ("position_risk", "breadth", "smooth_lo"),
                ("position_risk", "breadth", "smooth_range"),
                ("position_risk", "breadth", "ema_fast"),
                ("position_risk", "breadth", "ema_slow"),
                ("position_risk", "breadth", "gate_threshold"),
                ("position_risk", "breadth", "gate_quantile_window"),
                ("position_risk", "breadth", "gate_quantile_pct"),
                ("position_risk", "breadth", "gate_persist_days"),
                ("position_risk", "breadth", "size_scale_floor"),
            }
        )
    return allowed


def _assert_variant_contract(base_cfg: dict[str, Any], candidate_cfg: dict[str, Any], variant_name: str) -> list[dict[str, Any]]:
    diffs = _collect_diffs(base_cfg, candidate_cfg)
    allowed = _allowed_paths(variant_name)
    unexpected = [diff for diff in diffs if diff[0] not in allowed]
    if unexpected:
        lines = [
            f"{_path_text(path)}: baseline={base_value!r}, candidate={candidate_value!r}"
            for path, base_value, candidate_value in unexpected[:20]
        ]
        raise RuntimeError(f"{variant_name} drifted beyond allowed paths:\n" + "\n".join(lines))
    return [
        {
            "path": _path_text(path),
            "baseline": base_value,
            "candidate": candidate_value,
        }
        for path, base_value, candidate_value in diffs
    ]


def _build_variant_cfg(base_cfg: dict[str, Any], variant: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cfg = deepcopy(base_cfg)
    for path, value in dict(variant.get("mutations") or {}).items():
        _set_path(cfg, path, deepcopy(value))
    diffs = _assert_variant_contract(base_cfg, cfg, str(variant["name"]))
    return cfg, diffs


def _load_reference_perf() -> dict[str, Any]:
    path = ROOT / "outputs" / "experiments" / REFERENCE_EXP_ID / "perf.json"
    return _load_json(path) if path.exists() else {}


def _baseline_match(perf: dict[str, Any]) -> dict[str, Any]:
    reference_perf = _load_reference_perf()
    checks: dict[str, Any] = {"reference_exp_id": REFERENCE_EXP_ID, "matches": True, "diffs": {}}
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


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    for date_col in ("date", "signal_date", "entry_date"):
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    return df


def _coerce_bool(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().any():
        return numeric.fillna(0.0).ne(0.0)
    text = series.astype(str).str.strip().str.lower()
    return text.isin({"1", "true", "t", "yes", "y", "on"})


def _recompute_perf_from_nav(nav_df: pd.DataFrame, start_date: str) -> dict[str, Any]:
    if nav_df.empty:
        return {}
    df = nav_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    df = df.dropna(subset=["date", "nav"]).sort_values("date")
    df = df.loc[df["date"] >= pd.Timestamp(start_date)].copy()
    if df.empty:
        return {}
    nav0 = float(df["nav"].iloc[0])
    nav1 = float(df["nav"].iloc[-1])
    total_return = (nav1 / nav0 - 1.0) if nav0 > 0 else 0.0
    years = max(len(df) / 252.0, 1e-9)
    cagr = (nav1 / nav0) ** (1.0 / years) - 1.0 if nav0 > 0 and nav1 > 0 else 0.0
    dd = df["nav"] / df["nav"].cummax() - 1.0
    max_drawdown = float(dd.min()) if not dd.empty else 0.0
    daily_ret = df["nav"].pct_change().replace([math.inf, -math.inf], pd.NA).fillna(0.0)
    vol = float(daily_ret.std(ddof=0))
    sharpe = float((daily_ret.mean() / vol) * math.sqrt(252.0)) if vol > 0 else 0.0
    calmar = float(cagr / abs(max_drawdown)) if max_drawdown != 0 else 0.0
    return {
        "start": str(df["date"].iloc[0].date()),
        "end": str(df["date"].iloc[-1].date()),
        "days": int(len(df)),
        "total_return": float(total_return),
        "cagr": float(cagr),
        "max_drawdown": float(max_drawdown),
        "sharpe": float(sharpe),
        "calmar": float(calmar),
    }


def _phase_summary(
    *,
    nav_df: pd.DataFrame,
    daily_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    start: str,
    end: str,
) -> dict[str, Any]:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)

    sub_nav = nav_df.loc[(nav_df["date"] >= start_ts) & (nav_df["date"] <= end_ts)].copy()
    sub_daily = daily_df.loc[(daily_df["date"] >= start_ts) & (daily_df["date"] <= end_ts)].copy()
    sub_trades = trades_df.loc[(trades_df["date"] >= start_ts) & (trades_df["date"] <= end_ts)].copy()

    phase_perf = _recompute_perf_from_nav(sub_nav, start)
    benchmark_regime_on_ratio = None
    if not sub_daily.empty and "benchmark_regime_on" in sub_daily.columns:
        benchmark_regime_on_ratio = float(_coerce_bool(sub_daily["benchmark_regime_on"]).mean())
    strong_risk_on_ratio = None
    if not sub_daily.empty and "strong_risk_on" in sub_daily.columns:
        strong_risk_on_ratio = float(_coerce_bool(sub_daily["strong_risk_on"]).mean())

    return {
        "start": start,
        "end": end,
        "days": int(phase_perf.get("days", 0) or 0),
        "return": float(phase_perf.get("total_return", 0.0) or 0.0),
        "max_drawdown": float(phase_perf.get("max_drawdown", 0.0) or 0.0),
        "avg_gross_exposure": float(pd.to_numeric(sub_daily.get("gross_exposure"), errors="coerce").dropna().mean()) if not sub_daily.empty and "gross_exposure" in sub_daily.columns else 0.0,
        "zero_exposure_ratio": float(pd.to_numeric(sub_daily.get("gross_exposure"), errors="coerce").fillna(0.0).eq(0.0).mean()) if not sub_daily.empty and "gross_exposure" in sub_daily.columns else 0.0,
        "avg_positions_eod": float(pd.to_numeric(sub_daily.get("positions_count_end_of_day"), errors="coerce").dropna().mean()) if not sub_daily.empty and "positions_count_end_of_day" in sub_daily.columns else 0.0,
        "avg_effective_max_positions": float(pd.to_numeric(sub_daily.get("effective_max_positions"), errors="coerce").dropna().mean()) if not sub_daily.empty and "effective_max_positions" in sub_daily.columns else 0.0,
        "benchmark_regime_on_ratio": benchmark_regime_on_ratio,
        "strong_risk_on_ratio": strong_risk_on_ratio,
        "avg_buy_candidate_count": float(pd.to_numeric(sub_daily.get("buy_candidate_count"), errors="coerce").dropna().mean()) if not sub_daily.empty and "buy_candidate_count" in sub_daily.columns else 0.0,
        "avg_selected_count": float(pd.to_numeric(sub_daily.get("selected_count"), errors="coerce").dropna().mean()) if not sub_daily.empty and "selected_count" in sub_daily.columns else 0.0,
        "buy_count": int((sub_trades.get("side", pd.Series(dtype=str)).astype(str).str.upper() == "BUY").sum()) if not sub_trades.empty else 0,
        "sell_count": int((sub_trades.get("side", pd.Series(dtype=str)).astype(str).str.upper() == "SELL").sum()) if not sub_trades.empty else 0,
    }


def _summarize_result(variant: dict[str, Any], result: dict[str, Any], common_start_date: str) -> dict[str, Any]:
    results_dir = Path(str(result.get("results_dir") or "")).resolve()
    perf_path = results_dir / "perf.json"
    perf = _load_json(perf_path) if perf_path.exists() else {}
    run_config = _load_json(results_dir / "run_config.json") if (results_dir / "run_config.json").exists() else {}
    nav_df = _load_csv(results_dir / "nav.csv")
    daily_df = _load_csv(results_dir / "portfolio_daily.csv")
    trades_df = _load_csv(results_dir / "portfolio_trades.csv")
    run_meta = _load_json(results_dir / "run_meta.json") if (results_dir / "run_meta.json").exists() else {}

    native_perf = {
        "total_return": float(perf.get("total_return", result.get("total_return", 0.0)) or 0.0),
        "cagr": float(perf.get("cagr", result.get("cagr", 0.0)) or 0.0),
        "max_drawdown": float(perf.get("max_drawdown", result.get("max_drawdown", 0.0)) or 0.0),
        "sharpe": float(perf.get("sharpe", result.get("sharpe", 0.0)) or 0.0),
        "calmar": float(perf.get("calmar", result.get("calmar", 0.0)) or 0.0),
        "effective_execution_start_date": str(perf.get("effective_execution_start_date", result.get("effective_execution_start_date", "")) or ""),
    }
    common_start_perf = _recompute_perf_from_nav(nav_df, common_start_date)

    first_position_date = ""
    if not daily_df.empty and "positions_count_end_of_day" in daily_df.columns and "date" in daily_df.columns:
        positions_mask = pd.to_numeric(daily_df["positions_count_end_of_day"], errors="coerce").fillna(0.0) > 0
        sub = daily_df.loc[positions_mask]
        if not sub.empty:
            first_position_date = str(sub.iloc[0]["date"].date())

    phases = {
        phase_name: _phase_summary(
            nav_df=nav_df,
            daily_df=daily_df,
            trades_df=trades_df,
            start=phase_start,
            end=phase_end,
        )
        for phase_name, (phase_start, phase_end) in PHASES.items()
    }

    return {
        "variant": str(variant["name"]),
        "label": str(variant["label"]),
        "description": str(variant["description"]),
        "exp_id": str(result.get("exp_id") or ""),
        "results_dir": str(results_dir),
        "benchmark_symbol": str((run_config.get("universe") or {}).get("benchmark") or ""),
        "benchmark_regime_enabled": bool(((run_config.get("benchmark_regime") or {}).get("enabled"))),
        "breadth_enabled": bool((((run_config.get("position_risk") or {}).get("breadth") or {}).get("enabled"))),
        "native_perf": native_perf,
        "common_start_perf": common_start_perf,
        "trades": int(perf.get("trades", result.get("trades", 0)) or 0),
        "turnover": float(perf.get("turnover", result.get("turnover", 0.0)) or 0.0),
        "raw_signal": int(result.get("raw_signal", 0) or 0),
        "blocked": int(result.get("blocked", 0) or 0),
        "orders": int(result.get("orders", 0) or 0),
        "closed_trades": int(result.get("closed_trades", 0) or 0),
        "breadth_score_mean": float(result.get("breadth_score_mean", 0.0) or 0.0),
        "breadth_maxpos_mean": float(result.get("breadth_maxpos_mean", 0.0) or 0.0),
        "trade_mode_main_days": int(result.get("trade_mode_main_days", 0) or 0),
        "trade_mode_light_days": int(result.get("trade_mode_light_days", 0) or 0),
        "trade_mode_notrade_days": int(result.get("trade_mode_notrade_days", 0) or 0),
        "market_filter_bear_days": int(result.get("market_filter_bear_days", 0) or 0),
        "market_state_trans_down_days": int(result.get("market_state_trans_down_days", 0) or 0),
        "market_state_trans_up_days": int(result.get("market_state_trans_up_days", 0) or 0),
        "warmup_effective_execution_start_date": str(result.get("effective_execution_start_date") or ""),
        "first_position_date": first_position_date,
        "avg_effective_max_positions": float(pd.to_numeric(daily_df.get("effective_max_positions"), errors="coerce").dropna().mean()) if not daily_df.empty and "effective_max_positions" in daily_df.columns else 0.0,
        "avg_gross_exposure": float(pd.to_numeric(daily_df.get("gross_exposure"), errors="coerce").dropna().mean()) if not daily_df.empty and "gross_exposure" in daily_df.columns else 0.0,
        "zero_exposure_ratio": float(pd.to_numeric(daily_df.get("gross_exposure"), errors="coerce").fillna(0.0).eq(0.0).mean()) if not daily_df.empty and "gross_exposure" in daily_df.columns else 0.0,
        "benchmark_regime_on_ratio": float(_coerce_bool(daily_df["benchmark_regime_on"]).mean()) if not daily_df.empty and "benchmark_regime_on" in daily_df.columns else None,
        "strong_risk_on_ratio": float(_coerce_bool(daily_df["strong_risk_on"]).mean()) if not daily_df.empty and "strong_risk_on" in daily_df.columns else None,
        "phases": phases,
        "run_meta_data": dict(run_meta.get("data") or {}),
    }


def _build_variant_row(summary: dict[str, Any]) -> dict[str, Any]:
    row = {
        "variant": summary["variant"],
        "label": summary["label"],
        "exp_id": summary["exp_id"],
        "benchmark_symbol": summary["benchmark_symbol"],
        "benchmark_regime_enabled": summary["benchmark_regime_enabled"],
        "breadth_enabled": summary["breadth_enabled"],
        "native_total_return": _safe_float(summary["native_perf"].get("total_return")),
        "native_cagr": _safe_float(summary["native_perf"].get("cagr")),
        "native_max_drawdown": _safe_float(summary["native_perf"].get("max_drawdown")),
        "native_sharpe": _safe_float(summary["native_perf"].get("sharpe")),
        "native_calmar": _safe_float(summary["native_perf"].get("calmar")),
        "native_effective_execution_start_date": summary["native_perf"].get("effective_execution_start_date"),
        "common_start": summary["common_start_perf"].get("start"),
        "common_total_return": _safe_float(summary["common_start_perf"].get("total_return")),
        "common_cagr": _safe_float(summary["common_start_perf"].get("cagr")),
        "common_max_drawdown": _safe_float(summary["common_start_perf"].get("max_drawdown")),
        "common_sharpe": _safe_float(summary["common_start_perf"].get("sharpe")),
        "common_calmar": _safe_float(summary["common_start_perf"].get("calmar")),
        "trades": _safe_int(summary.get("trades")),
        "turnover": _safe_float(summary.get("turnover")),
        "raw_signal": _safe_int(summary.get("raw_signal")),
        "blocked": _safe_int(summary.get("blocked")),
        "orders": _safe_int(summary.get("orders")),
        "closed_trades": _safe_int(summary.get("closed_trades")),
        "breadth_score_mean": _safe_float(summary.get("breadth_score_mean")),
        "breadth_maxpos_mean": _safe_float(summary.get("breadth_maxpos_mean")),
        "avg_effective_max_positions": _safe_float(summary.get("avg_effective_max_positions")),
        "avg_gross_exposure": _safe_float(summary.get("avg_gross_exposure")),
        "zero_exposure_ratio": _safe_float(summary.get("zero_exposure_ratio")),
        "benchmark_regime_on_ratio": summary.get("benchmark_regime_on_ratio"),
        "strong_risk_on_ratio": summary.get("strong_risk_on_ratio"),
        "first_position_date": summary.get("first_position_date"),
    }
    if summary["variant"] == "B0_HS300":
        row["baseline_match"] = bool(_baseline_match(_load_json(Path(summary["results_dir"]) / "perf.json")).get("matches"))
    return row


def _build_phase_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for phase_name, payload in dict(summary.get("phases") or {}).items():
        rows.append(
            {
                "variant": summary["variant"],
                "label": summary["label"],
                "phase": phase_name,
                "phase_label": PHASE_LABELS.get(phase_name, phase_name),
                "start": payload.get("start"),
                "end": payload.get("end"),
                "days": _safe_int(payload.get("days")),
                "return": _safe_float(payload.get("return")),
                "max_drawdown": _safe_float(payload.get("max_drawdown")),
                "avg_gross_exposure": _safe_float(payload.get("avg_gross_exposure")),
                "zero_exposure_ratio": _safe_float(payload.get("zero_exposure_ratio")),
                "avg_positions_eod": _safe_float(payload.get("avg_positions_eod")),
                "avg_effective_max_positions": _safe_float(payload.get("avg_effective_max_positions")),
                "benchmark_regime_on_ratio": payload.get("benchmark_regime_on_ratio"),
                "strong_risk_on_ratio": payload.get("strong_risk_on_ratio"),
                "avg_buy_candidate_count": _safe_float(payload.get("avg_buy_candidate_count")),
                "avg_selected_count": _safe_float(payload.get("avg_selected_count")),
                "buy_count": _safe_int(payload.get("buy_count")),
                "sell_count": _safe_int(payload.get("sell_count")),
            }
        )
    return rows


def _fmt_pct(value: Any) -> str:
    if value is None:
        return "-"
    return f"{_safe_float(value) * 100:.2f}%"


def _fmt_num(value: Any, digits: int = 3) -> str:
    if value is None:
        return "-"
    return f"{_safe_float(value):.{digits}f}"


def _write_report(*, summaries: list[dict[str, Any]], common_start_date: str) -> None:
    by_variant = {str(item["variant"]): item for item in summaries}
    baseline = by_variant["B0_HS300"]
    csi800 = by_variant["R_CSI800_BENCH"]
    breadth = by_variant["R_BREADTH_REGIME"]

    lines: list[str] = []
    lines.append("[V10_REGIME_SOURCE_MINIMAL]")
    lines.append("")
    lines.append("1. 本轮目标")
    lines.append("- 事实：本轮只比较市场 regime 来源，不改股票池、成本、成交时点、个股信号、退出规则。")
    lines.append("- 事实：对照组是 16-26 V10 baseline，变体只有两组：`CSI800 benchmark` 和 `breadth regime`。")
    lines.append(f"- 事实：为避免 warmup 起点漂移污染全窗口指标，三组额外统一按 `{common_start_date}` 重算了一套 common-start 指标。")
    lines.append("")
    lines.append("2. 最小实验设计")
    lines.append("- `B0_HS300`：原始 baseline。")
    lines.append("- `R_CSI800_BENCH`：只把 `universe.benchmark` 改成 `000906.SH`。")
    lines.append("  说明：当前引擎里 `benchmark_regime` 和 `market_filter` 共用 benchmark 数据源，所以这组实际上是 `HS300 -> CSI800` 的整套大盘代理替换。")
    lines.append("- `R_BREADTH_REGIME`：关闭 `benchmark_regime`，启用现成 `breadth_momo` 动态 max_positions，并把 `min_positions=0`，让宽度低迷日可收缩到 0 仓位。")
    lines.append("")
    lines.append("3. 审计结果")
    lines.append("- 事实：这轮没有改策略引擎，只新增研究脚本。")
    lines.append("- 事实：三组都沿用 `t` 日收盘信号、`t+1` 开盘执行，没有引入未来函数。")
    lines.append("- 风险：`R_CSI800_BENCH` 不只是改 `benchmark_regime`，也连带改了 `market_filter` 的 benchmark 来源；这点是当前框架耦合，不是口径漂移被忽略。")
    lines.append(f"- 事实：`B0_HS300` 与历史 baseline `{REFERENCE_EXP_ID}` 的匹配结果是 `{_baseline_match(_load_json(Path(baseline['results_dir']) / 'perf.json')).get('matches')}`。")
    lines.append("")
    lines.append("4. 回测结果对比")
    lines.append(f"- `B0_HS300` common-start：总收益 `{_fmt_pct(baseline['common_start_perf'].get('total_return'))}` / CAGR `{_fmt_pct(baseline['common_start_perf'].get('cagr'))}` / MaxDD `{_fmt_pct(baseline['common_start_perf'].get('max_drawdown'))}` / Sharpe `{_fmt_num(baseline['common_start_perf'].get('sharpe'))}`")
    lines.append(f"- `R_CSI800_BENCH` common-start：总收益 `{_fmt_pct(csi800['common_start_perf'].get('total_return'))}` / CAGR `{_fmt_pct(csi800['common_start_perf'].get('cagr'))}` / MaxDD `{_fmt_pct(csi800['common_start_perf'].get('max_drawdown'))}` / Sharpe `{_fmt_num(csi800['common_start_perf'].get('sharpe'))}`")
    lines.append(f"- `R_BREADTH_REGIME` common-start：总收益 `{_fmt_pct(breadth['common_start_perf'].get('total_return'))}` / CAGR `{_fmt_pct(breadth['common_start_perf'].get('cagr'))}` / MaxDD `{_fmt_pct(breadth['common_start_perf'].get('max_drawdown'))}` / Sharpe `{_fmt_num(breadth['common_start_perf'].get('sharpe'))}`")
    lines.append("")
    lines.append("5. 分阶段事实")
    for phase_name in PHASES:
        b0_phase = baseline["phases"][phase_name]
        csi_phase = csi800["phases"][phase_name]
        br_phase = breadth["phases"][phase_name]
        lines.append(f"- {PHASE_LABELS[phase_name]}：`B0 {_fmt_pct(b0_phase.get('return'))}` / `CSI800 {_fmt_pct(csi_phase.get('return'))}` / `Breadth {_fmt_pct(br_phase.get('return'))}`")
    lines.append("")
    lines.append("6. 诊断")
    lines.append(f"- 事实：`B0_HS300` 的 `benchmark_regime_on_ratio` 是 `{_fmt_pct(baseline.get('benchmark_regime_on_ratio'))}`，`avg_effective_max_positions` 是 `{_fmt_num(baseline.get('avg_effective_max_positions'), 2)}`。")
    lines.append(f"- 事实：`R_CSI800_BENCH` 的 `benchmark_regime_on_ratio` 是 `{_fmt_pct(csi800.get('benchmark_regime_on_ratio'))}`，`avg_effective_max_positions` 是 `{_fmt_num(csi800.get('avg_effective_max_positions'), 2)}`。")
    lines.append(f"- 事实：`R_BREADTH_REGIME` 的 `breadth_score_mean` 是 `{_fmt_num(breadth.get('breadth_score_mean'))}`，`breadth_maxpos_mean` 是 `{_fmt_num(breadth.get('breadth_maxpos_mean'), 2)}`，`avg_effective_max_positions` 是 `{_fmt_num(breadth.get('avg_effective_max_positions'), 2)}`。")
    lines.append(f"- 事实：`R_BREADTH_REGIME` 的首仓日是 `{breadth.get('first_position_date') or '-'}`，baseline 是 `{baseline.get('first_position_date') or '-'}`。")
    lines.append("")
    lines.append("7. 推断")
    lines.append("- 推断：如果 `CSI800 benchmark` 相对 baseline 明显改善，说明 V10 的一部分问题来自 `HS300` 作为大盘代理的错配。")
    lines.append("- 推断：如果 `breadth regime` 改善更明显，说明当前硬性 benchmark gate 过于依赖单指数趋势，而 A 股机会更像由横截面扩散驱动。")
    lines.append("- 推断：如果两组都不改善，就不该继续优先做 regime 来源替换，应回到上游候选生成或个股强度评分。")
    lines.append("")
    lines.append("8. 产物")
    lines.append(f"- 汇总表：[summary_all.csv]({(OUTPUT_ROOT / 'summary_all.csv').resolve()})")
    lines.append(f"- 阶段表：[phase_comparison.csv]({(OUTPUT_ROOT / 'phase_comparison.csv').resolve()})")
    lines.append(f"- 报告：[report.md]({(OUTPUT_ROOT / 'report.md').resolve()})")

    (OUTPUT_ROOT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_one(variant: dict[str, Any], base_cfg: dict[str, Any], common_start_date: str) -> dict[str, Any]:
    semantic_cfg, diffs = _build_variant_cfg(base_cfg, variant)
    request_payload = {
        "preset": "single",
        "config_json": semantic_cfg,
        "fast_mode": True,
    }
    t0 = time.perf_counter()
    print(f"\n{'=' * 84}")
    print(f"{variant['name']} / {variant['label']}")
    print(f"{'=' * 84}")

    def progress(pct: int, message: str) -> None:
        elapsed = time.perf_counter() - t0
        print(f"  [{pct:3d}%] {message} ({elapsed:.1f}s)")

    result = run_experiment_request(request_payload, progress_hook=progress)
    summary = _summarize_result(variant, result, common_start_date)
    elapsed = time.perf_counter() - t0
    print(
        "  done: "
        f"exp_id={summary['exp_id']} "
        f"common_cagr={_safe_float(summary['common_start_perf'].get('cagr')):.4f} "
        f"common_max_dd={_safe_float(summary['common_start_perf'].get('max_drawdown')):.4f} "
        f"elapsed={elapsed:.1f}s"
    )
    return {
        "variant": str(variant["name"]),
        "request_payload": request_payload,
        "config_diffs": diffs,
        "result": result,
        "summary": summary,
    }


def main() -> None:
    _load_local_env()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    base_cfg = _load_json(BASE_CFG_PATH)
    reference_perf = _load_reference_perf()
    common_start_date = str(reference_perf.get("effective_execution_start_date") or "2016-08-29")

    records: list[dict[str, Any]] = []
    validation_summary = {
        "reference_exp_id": REFERENCE_EXP_ID,
        "common_start_date": common_start_date,
        "variants": {},
    }
    for variant in VARIANTS:
        record = _run_one(variant, base_cfg, common_start_date)
        records.append(record)
        variant_name = str(variant["name"])
        _write_json(OUTPUT_ROOT / f"request_payload_{variant_name}.json", record["request_payload"])
        _write_json(OUTPUT_ROOT / f"summary_{variant_name}.json", record["summary"])
        validation_summary["variants"][variant_name] = {
            "config_diffs": record["config_diffs"],
            "results_dir": record["summary"]["results_dir"],
            "exp_id": record["summary"]["exp_id"],
        }

    summaries = [record["summary"] for record in records]
    summary_rows = [_build_variant_row(summary) for summary in summaries]
    phase_rows: list[dict[str, Any]] = []
    for summary in summaries:
        phase_rows.extend(_build_phase_rows(summary))

    _write_json(OUTPUT_ROOT / "summary_all.json", summaries)
    _write_json(OUTPUT_ROOT / "validation_summary.json", validation_summary)
    pd.DataFrame(summary_rows).to_csv(OUTPUT_ROOT / "summary_all.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(phase_rows).to_csv(OUTPUT_ROOT / "phase_comparison.csv", index=False, encoding="utf-8-sig")
    _write_report(summaries=summaries, common_start_date=common_start_date)


if __name__ == "__main__":
    main()
