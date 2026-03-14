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
OUTPUT_ROOT = ROOT / "outputs" / "ops" / "v10_quality_then_residual_s3_20260313"
ENV_PATH = ROOT / ".env"
FAST_MODE = True
HARD_GATE_CAGR = 0.10
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
    "1626": {
        "role": "main",
        "start": "2016-03-01",
        "end": "2026-03-01",
        "periods": {
            "phase_2018_bear": ("2018-01-02", "2018-12-28"),
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
            "phase_2018_bear": ("2018-01-02", "2018-12-28"),
            "phase_2021_2022_drawdown": ("2021-02-19", "2022-10-31"),
            "phase_2024_2026_recovery": ("2024-02-06", "2026-02-27"),
        },
    },
}
VARIANTS: list[tuple[str, dict[tuple[Any, ...], Any]]] = [
    ("B0", {}),
    (
        "S3_A_Q55",
        {
            ("signal_generation", "ranking", "score_source_mode"): "QUALITY_THEN_RESIDUAL",
            ("signal_generation", "ranking", "breakout_quality_gate_min_score"): 0.55,
            ("signal_generation", "ranking", "breakout_quality_margin_cap_pct"): 0.08,
            ("signal_generation", "ranking", "breakout_quality_fade_cap_pct"): 0.035,
            ("signal_generation", "ranking", "breakout_quality_open_gap_cap_pct"): 0.04,
        },
    ),
    (
        "S3_B_Q65",
        {
            ("signal_generation", "ranking", "score_source_mode"): "QUALITY_THEN_RESIDUAL",
            ("signal_generation", "ranking", "breakout_quality_gate_min_score"): 0.65,
            ("signal_generation", "ranking", "breakout_quality_margin_cap_pct"): 0.08,
            ("signal_generation", "ranking", "breakout_quality_fade_cap_pct"): 0.035,
            ("signal_generation", "ranking", "breakout_quality_open_gap_cap_pct"): 0.04,
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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _coerce_bool(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().any():
        return numeric.fillna(0.0).ne(0.0)
    text = series.astype(str).str.strip().str.lower()
    return text.isin({"1", "true", "t", "yes", "y", "on"})


def _window_output_dir(window_key: str) -> Path:
    return OUTPUT_ROOT / window_key


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
        else:
            same = abs(_safe_float(lhs) - _safe_float(rhs)) <= 1e-9
        if not same:
            checks["matches"] = False
            checks["diffs"][key] = {"candidate": lhs, "reference": rhs}
    return checks


def _variant_params(variant_name: str) -> dict[str, Any]:
    for name, patch in VARIANTS:
        if name != variant_name:
            continue
        return {
            "ranking_mode": str(patch.get(("signal_generation", "ranking", "score_source_mode"), "RESIDUAL_ONLY")).strip().lower(),
            "quality_gate_min_score": float(patch.get(("signal_generation", "ranking", "breakout_quality_gate_min_score"), 0.0) or 0.0),
            "quality_margin_cap_pct": float(patch.get(("signal_generation", "ranking", "breakout_quality_margin_cap_pct"), 0.0) or 0.0),
            "quality_fade_cap_pct": float(patch.get(("signal_generation", "ranking", "breakout_quality_fade_cap_pct"), 0.0) or 0.0),
            "quality_open_gap_cap_pct": float(patch.get(("signal_generation", "ranking", "breakout_quality_open_gap_cap_pct"), 0.0) or 0.0),
        }
    return {
        "ranking_mode": "residual_only",
        "quality_gate_min_score": 0.0,
        "quality_margin_cap_pct": 0.0,
        "quality_fade_cap_pct": 0.0,
        "quality_open_gap_cap_pct": 0.0,
    }


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
                ("signal_generation", "ranking", "score_source_mode"),
                ("signal_generation", "ranking", "breakout_quality_gate_min_score"),
                ("signal_generation", "ranking", "breakout_quality_margin_cap_pct"),
                ("signal_generation", "ranking", "breakout_quality_fade_cap_pct"),
                ("signal_generation", "ranking", "breakout_quality_open_gap_cap_pct"),
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
        {
            "path": _path_text(path),
            "baseline": base_value,
            "candidate": candidate_value,
        }
        for path, base_value, candidate_value in diffs
    ]


def _build_variant_cfg(window_key: str, variant_name: str, patch: dict[tuple[Any, ...], Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cfg = deepcopy(_BASE_CFG)
    cfg.setdefault("universe", {})["start"] = str(WINDOWS[window_key]["start"])
    cfg.setdefault("universe", {})["end"] = str(WINDOWS[window_key]["end"])
    for path, value in patch.items():
        _set_path(cfg, path, deepcopy(value))
    diff_rows = _assert_variant_contract(_BASE_CFG, cfg, window_key=window_key, variant_name=variant_name)
    return cfg, diff_rows


def _compute_trade_stats(trades_df: pd.DataFrame) -> dict[str, Any]:
    if trades_df.empty:
        return {
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_hold_days": 0.0,
            "avg_win_return": 0.0,
            "avg_loss_return": 0.0,
            "closed_roundtrips": 0,
        }
    df = trades_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["side"] = df["side"].astype(str).str.upper()
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    lots: dict[str, list[dict[str, Any]]] = {}
    realized_pnls: list[float] = []
    realized_returns: list[float] = []
    hold_qty_days = 0.0
    hold_qty_total = 0.0

    for row in df.itertuples(index=False):
        symbol = str(getattr(row, "symbol", "")).lower()
        side = str(getattr(row, "side", "")).upper()
        qty = int(float(getattr(row, "qty", 0) or 0))
        if qty <= 0:
            continue
        net_amount = _safe_float(getattr(row, "net_amount", 0.0))
        if side == "BUY":
            lots.setdefault(symbol, []).append(
                {
                    "qty": qty,
                    "cost_ps": net_amount / max(qty, 1),
                    "date": pd.Timestamp(getattr(row, "date")),
                }
            )
            continue
        if side != "SELL":
            continue

        recv_ps = net_amount / max(qty, 1)
        remain = qty
        symbol_lots = lots.setdefault(symbol, [])
        while remain > 0 and symbol_lots:
            lot = symbol_lots[0]
            take = min(remain, int(lot["qty"]))
            cost_ps = float(lot["cost_ps"])
            pnl = float(take) * (recv_ps - cost_ps)
            ret = (recv_ps / cost_ps - 1.0) if cost_ps > 1e-12 else 0.0
            realized_pnls.append(float(pnl))
            realized_returns.append(float(ret))
            held_days = max((pd.Timestamp(getattr(row, "date")) - pd.Timestamp(lot["date"])).days, 0)
            hold_qty_days += float(held_days) * float(take)
            hold_qty_total += float(take)
            lot["qty"] = int(lot["qty"]) - int(take)
            remain -= int(take)
            if int(lot["qty"]) <= 0:
                symbol_lots.pop(0)

    wins = [value for value in realized_pnls if value > 0]
    losses = [value for value in realized_pnls if value < 0]
    positive_returns = [value for value in realized_returns if value > 0]
    negative_returns = [value for value in realized_returns if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "win_rate": float(len(wins) / len(realized_pnls)) if realized_pnls else 0.0,
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 1e-12 else 0.0,
        "avg_hold_days": float(hold_qty_days / hold_qty_total) if hold_qty_total > 1e-12 else 0.0,
        "avg_win_return": float(sum(positive_returns) / len(positive_returns)) if positive_returns else 0.0,
        "avg_loss_return": float(sum(negative_returns) / len(negative_returns)) if negative_returns else 0.0,
        "closed_roundtrips": int(len(realized_pnls)),
    }


def _compute_trade_stats_and_concentration(trades_df: pd.DataFrame, nav_df: pd.DataFrame) -> dict[str, Any]:
    stats = _compute_trade_stats(trades_df)
    stats.update(
        {
            "top5_positive_symbol_pnl_share": 0.0,
            "top5_negative_symbol_pnl_share": 0.0,
            "top5_positive_month_return_share": 0.0,
            "top5_negative_month_return_share": 0.0,
        }
    )
    if not trades_df.empty:
        df = trades_df.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["side"] = df["side"].astype(str).str.upper()
        df["symbol"] = df["symbol"].astype(str).str.lower()
        df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        lots: dict[str, list[dict[str, Any]]] = {}
        symbol_pnls: dict[str, float] = {}
        for row in df.itertuples(index=False):
            symbol = str(getattr(row, "symbol", "")).lower()
            side = str(getattr(row, "side", "")).upper()
            qty = int(float(getattr(row, "qty", 0) or 0))
            if qty <= 0:
                continue
            net_amount = _safe_float(getattr(row, "net_amount", 0.0))
            if side == "BUY":
                lots.setdefault(symbol, []).append({"qty": qty, "cost_ps": net_amount / max(qty, 1)})
                continue
            if side != "SELL":
                continue
            recv_ps = net_amount / max(qty, 1)
            remain = qty
            symbol_lots = lots.setdefault(symbol, [])
            while remain > 0 and symbol_lots:
                lot = symbol_lots[0]
                take = min(remain, int(lot["qty"]))
                pnl = float(take) * (recv_ps - float(lot["cost_ps"]))
                symbol_pnls[symbol] = float(symbol_pnls.get(symbol, 0.0) + pnl)
                lot["qty"] = int(lot["qty"]) - int(take)
                remain -= int(take)
                if int(lot["qty"]) <= 0:
                    symbol_lots.pop(0)
        pos_symbol = sorted((value for value in symbol_pnls.values() if value > 0), reverse=True)
        neg_symbol = sorted((abs(value) for value in symbol_pnls.values() if value < 0), reverse=True)
        pos_total = float(sum(pos_symbol))
        neg_total = float(sum(neg_symbol))
        stats["top5_positive_symbol_pnl_share"] = float(sum(pos_symbol[:5]) / pos_total) if pos_total > 1e-12 else 0.0
        stats["top5_negative_symbol_pnl_share"] = float(sum(neg_symbol[:5]) / neg_total) if neg_total > 1e-12 else 0.0
    if not nav_df.empty:
        monthly = (
            nav_df.assign(month=nav_df["date"].dt.to_period("M"))
            .groupby("month", dropna=False)["nav"]
            .agg(["first", "last"])
            .reset_index(drop=True)
        )
        if not monthly.empty:
            monthly["ret"] = monthly.apply(
                lambda row: (float(row["last"]) / float(row["first"]) - 1.0) if float(row["first"]) > 0 else 0.0,
                axis=1,
            )
            pos_month = sorted((float(value) for value in monthly["ret"] if float(value) > 0), reverse=True)
            neg_month = sorted((abs(float(value)) for value in monthly["ret"] if float(value) < 0), reverse=True)
            pos_total = float(sum(pos_month))
            neg_total = float(sum(neg_month))
            stats["top5_positive_month_return_share"] = float(sum(pos_month[:5]) / pos_total) if pos_total > 1e-12 else 0.0
            stats["top5_negative_month_return_share"] = float(sum(neg_month[:5]) / neg_total) if neg_total > 1e-12 else 0.0
    return stats


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


def _collect_quality_buy_stats(trades_df: pd.DataFrame) -> dict[str, Any]:
    stats = {
        "buy_count": 0,
        "quality_pass_buy_count": 0,
        "avg_buy_breakout_quality_score": 0.0,
        "avg_buy_breakout_margin_raw": 0.0,
        "avg_buy_breakout_open_gap_raw": 0.0,
        "avg_buy_breakout_fade_raw": 0.0,
    }
    if trades_df.empty or "meta_json" not in trades_df.columns:
        return stats
    quality_scores: list[float] = []
    breakout_margins: list[float] = []
    open_gaps: list[float] = []
    fades: list[float] = []
    for row in trades_df.itertuples(index=False):
        if str(getattr(row, "side", "")).upper() != "BUY":
            continue
        stats["buy_count"] += 1
        try:
            meta = json.loads(str(getattr(row, "meta_json", "") or "{}"))
        except Exception:
            continue
        if bool(meta.get("breakout_quality_pass", False)):
            stats["quality_pass_buy_count"] += 1
        q_score = _safe_float(meta.get("breakout_quality_score"), default=float("nan"))
        if pd.notna(q_score):
            quality_scores.append(float(q_score))
        margin = _safe_float(meta.get("breakout_margin_raw"), default=float("nan"))
        if pd.notna(margin):
            breakout_margins.append(float(margin))
        open_gap = _safe_float(meta.get("breakout_open_gap_raw"), default=float("nan"))
        if pd.notna(open_gap):
            open_gaps.append(float(open_gap))
        fade = _safe_float(meta.get("breakout_fade_raw"), default=float("nan"))
        if pd.notna(fade):
            fades.append(float(fade))
    if quality_scores:
        stats["avg_buy_breakout_quality_score"] = float(sum(quality_scores) / len(quality_scores))
    if breakout_margins:
        stats["avg_buy_breakout_margin_raw"] = float(sum(breakout_margins) / len(breakout_margins))
    if open_gaps:
        stats["avg_buy_breakout_open_gap_raw"] = float(sum(open_gaps) / len(open_gaps))
    if fades:
        stats["avg_buy_breakout_fade_raw"] = float(sum(fades) / len(fades))
    return stats


def _collect_daily_signal_stats(daily_df: pd.DataFrame) -> dict[str, Any]:
    if daily_df.empty:
        return {
            "avg_raw_buy_signal_count": 0.0,
            "avg_buy_candidate_count": 0.0,
            "sorting_triggered_days": 0,
            "avg_positions_eod": 0.0,
        }
    out = {}
    out["avg_raw_buy_signal_count"] = float(pd.to_numeric(daily_df.get("raw_buy_signal_count"), errors="coerce").fillna(0.0).mean())
    out["avg_buy_candidate_count"] = float(pd.to_numeric(daily_df.get("buy_candidate_count"), errors="coerce").fillna(0.0).mean())
    out["avg_positions_eod"] = float(pd.to_numeric(daily_df.get("positions_count_end_of_day"), errors="coerce").fillna(0.0).mean())
    if "sorting_triggered" in daily_df.columns:
        out["sorting_triggered_days"] = int(_coerce_bool(daily_df["sorting_triggered"]).sum())
    else:
        out["sorting_triggered_days"] = 0
    return out


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
        if "meta_json" in trades_df.columns:
            trades_df["meta_json"] = trades_df["meta_json"].astype(str)
    daily_path = results_dir / "portfolio_daily.csv"
    daily_df = pd.read_csv(daily_path) if daily_path.exists() else pd.DataFrame()
    if not daily_df.empty and "date" in daily_df.columns:
        daily_df["date"] = pd.to_datetime(daily_df["date"], errors="coerce")

    trade_stats = _compute_trade_stats_and_concentration(trades_df, nav_df)
    quality_buy_stats = _collect_quality_buy_stats(trades_df)
    daily_stats = _collect_daily_signal_stats(daily_df)
    period_metrics = {
        period_name: _period_metrics(nav_df, start=period_start, end=period_end)
        for period_name, (period_start, period_end) in WINDOWS[window_key]["periods"].items()
    }
    variant_params = _variant_params(variant_name)
    summary = {
        "window": window_key,
        "window_role": WINDOWS[window_key]["role"],
        "variant": variant_name,
        "exp_id": str(result.get("exp_id") or ""),
        "results_dir": str(results_dir),
        "ranking_mode": str(variant_params["ranking_mode"]),
        "breakout_quality_gate_min_score": float(variant_params["quality_gate_min_score"]),
        "breakout_quality_margin_cap_pct": float(variant_params["quality_margin_cap_pct"]),
        "breakout_quality_fade_cap_pct": float(variant_params["quality_fade_cap_pct"]),
        "breakout_quality_open_gap_cap_pct": float(variant_params["quality_open_gap_cap_pct"]),
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
        "avg_hold_days": float(trade_stats["avg_hold_days"]),
        "avg_win_return": float(trade_stats["avg_win_return"]),
        "avg_loss_return": float(trade_stats["avg_loss_return"]),
        "closed_roundtrips": int(trade_stats["closed_roundtrips"]),
        "top5_positive_symbol_pnl_share": float(trade_stats["top5_positive_symbol_pnl_share"]),
        "top5_negative_symbol_pnl_share": float(trade_stats["top5_negative_symbol_pnl_share"]),
        "top5_positive_month_return_share": float(trade_stats["top5_positive_month_return_share"]),
        "top5_negative_month_return_share": float(trade_stats["top5_negative_month_return_share"]),
        "buy_count": int(quality_buy_stats["buy_count"]),
        "quality_pass_buy_count": int(quality_buy_stats["quality_pass_buy_count"]),
        "avg_buy_breakout_quality_score": float(quality_buy_stats["avg_buy_breakout_quality_score"]),
        "avg_buy_breakout_margin_raw": float(quality_buy_stats["avg_buy_breakout_margin_raw"]),
        "avg_buy_breakout_open_gap_raw": float(quality_buy_stats["avg_buy_breakout_open_gap_raw"]),
        "avg_buy_breakout_fade_raw": float(quality_buy_stats["avg_buy_breakout_fade_raw"]),
        "avg_raw_buy_signal_count": float(daily_stats["avg_raw_buy_signal_count"]),
        "avg_buy_candidate_count": float(daily_stats["avg_buy_candidate_count"]),
        "avg_positions_eod": float(daily_stats["avg_positions_eod"]),
        "sorting_triggered_days": int(daily_stats["sorting_triggered_days"]),
        "period_metrics": period_metrics,
    }
    if variant_name == "B0" and window_key in REFERENCE_EXP_IDS:
        summary["baseline_match"] = _baseline_match(window_key, perf)
    return summary


def _run_one(window_key: str, variant_name: str, patch: dict[tuple[Any, ...], Any]) -> dict[str, Any]:
    semantic_cfg, diff_rows = _build_variant_cfg(window_key, variant_name, patch)
    request_payload = {"preset": "single", "config_json": semantic_cfg, "fast_mode": FAST_MODE}
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
        f"sharpe={summary['sharpe']:.4f} "
        f"max_dd={summary['max_drawdown']:.4f} "
        f"elapsed={elapsed:.1f}s"
    )
    return {"window": window_key, "variant": variant_name, "request_payload": request_payload, "diff_rows": diff_rows, "summary": summary}


def run_window(window_key: str, variant_names: list[str] | None = None) -> list[dict[str, Any]]:
    if window_key not in WINDOWS:
        raise RuntimeError(f"unsupported window: {window_key}")
    selected = {name for name in (variant_names or [name for name, _ in VARIANTS])}
    output_dir = _window_output_dir(window_key)
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for variant_name, patch in VARIANTS:
        if variant_name not in selected:
            continue
        record = _run_one(window_key, variant_name, patch)
        records.append(record)
        _write_json(output_dir / f"request_payload_{variant_name}.json", record["request_payload"])
        _write_json(output_dir / f"diff_rows_{variant_name}.json", record["diff_rows"])
    summaries = [record["summary"] for record in records]
    _write_json(output_dir / f"summary_{window_key}.json", summaries)
    rows = []
    for summary in summaries:
        row = {key: value for key, value in summary.items() if key not in {"period_metrics", "baseline_match"}}
        for period_name, metrics in dict(summary.get("period_metrics") or {}).items():
            row[f"{period_name}_return"] = float(metrics.get("return", 0.0) or 0.0)
            row[f"{period_name}_max_drawdown"] = float(metrics.get("max_drawdown", 0.0) or 0.0)
            row[f"{period_name}_days"] = int(metrics.get("days", 0) or 0)
        if isinstance(summary.get("baseline_match"), dict):
            row["baseline_match"] = bool(summary["baseline_match"].get("matches"))
        rows.append(row)
    pd.DataFrame(rows).to_csv(output_dir / f"summary_{window_key}.csv", index=False, encoding="utf-8-sig")
    return records


def _gate_rows(summary_map: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    base_main = summary_map.get(("1626", "B0"), {})
    base_cagr = float(base_main.get("cagr", 0.0) or 0.0)
    base_sharpe = float(base_main.get("sharpe", 0.0) or 0.0)
    base_max_dd = float(base_main.get("max_drawdown", 0.0) or 0.0)
    rows: list[dict[str, Any]] = []
    for variant_name, _ in VARIANTS:
        main_summary = summary_map.get(("1626", variant_name), {})
        gate_summary = summary_map.get(("0717", variant_name), {})
        main_cagr = float(main_summary.get("cagr", 0.0) or 0.0)
        main_sharpe = float(main_summary.get("sharpe", 0.0) or 0.0)
        main_max_dd = float(main_summary.get("max_drawdown", 0.0) or 0.0)
        hard_cagr = float(gate_summary.get("cagr", 0.0) or 0.0)
        main_window_pass = bool(
            main_cagr >= base_cagr and main_sharpe >= base_sharpe and main_max_dd >= base_max_dd - 0.03
        )
        hard_gate_pass = bool(hard_cagr >= HARD_GATE_CAGR)
        rows.append(
            {
                "variant": variant_name,
                "main_cagr": main_cagr,
                "main_sharpe": main_sharpe,
                "main_max_drawdown": main_max_dd,
                "main_window_pass": main_window_pass,
                "hard_gate_0717_cagr": hard_cagr,
                "hard_gate_pass": hard_gate_pass,
                "eligible_for_0726_audit": bool(main_window_pass and hard_gate_pass),
            }
        )
    return rows


def _write_report(all_records: list[dict[str, Any]], gate_rows: list[dict[str, Any]]) -> None:
    summaries = [record["summary"] for record in all_records]
    _write_json(OUTPUT_ROOT / "summary_all.json", summaries)
    pd.DataFrame([{key: value for key, value in row.items() if key != "period_metrics"} for row in summaries]).to_csv(
        OUTPUT_ROOT / "summary_all.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(gate_rows).to_csv(OUTPUT_ROOT / "gate_results.csv", index=False, encoding="utf-8-sig")

    lines = [
        "# V10 Quality Then Residual S3 Research",
        "",
        "- baseline: `baseline_V10`",
        "- main_change: `先质量门控，后 residual 强度排序`",
        "- fixed: planner / regime source / exit / cost / execution unchanged",
        f"- fast_mode: `{str(FAST_MODE).lower()}`",
        "",
        "## Gates",
        "",
        "- Gate 1: `16-26` is the main scoring window. Variant must not degrade the main window.",
        f"- Gate 2: `07-17` is the hard constraint. `CAGR >= {HARD_GATE_CAGR:.0%}` is required.",
        "- Gate 3: `07-26` runs only for variants passing both gates.",
        "",
        "## Window Summary",
        "",
        "| window | variant | ranking_mode | gate_min | Total Return | CAGR | MaxDD | Sharpe | Trades | BuyCount | AvgBuyQuality | AvgBuyMargin | AvgBuyGap | AvgBuyFade | AvgRawSignals | AvgCandidates | Start | exp_id |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in summaries:
        lines.append(
            f"| {row['window']} | {row['variant']} | {row['ranking_mode']} | {float(row['breakout_quality_gate_min_score']):.2f} | "
            f"{float(row['total_return']):.2%} | {float(row['cagr']):.2%} | "
            f"{float(row['max_drawdown']):.2%} | {float(row['sharpe']):.3f} | {int(row['trades'])} | {int(row['buy_count'])} | "
            f"{float(row['avg_buy_breakout_quality_score']):.3f} | {float(row['avg_buy_breakout_margin_raw']):.2%} | "
            f"{float(row['avg_buy_breakout_open_gap_raw']):.2%} | {float(row['avg_buy_breakout_fade_raw']):.2%} | "
            f"{float(row['avg_raw_buy_signal_count']):.2f} | "
            f"{float(row['avg_buy_candidate_count']):.2f} | `{row['effective_execution_start_date']}` | `{row['exp_id']}` |"
        )
    if gate_rows:
        lines.extend(
            [
                "",
                "## Gate Results",
                "",
                "| variant | main_pass | 16-26 CAGR | 16-26 Sharpe | 16-26 MaxDD | 07-17 CAGR | 07-17 hard_gate_pass | 07-26 audit |",
                "|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in gate_rows:
            lines.append(
                f"| {row['variant']} | {str(bool(row['main_window_pass'])).lower()} | {float(row['main_cagr']):.2%} | "
                f"{float(row['main_sharpe']):.3f} | {float(row['main_max_drawdown']):.2%} | {float(row['hard_gate_0717_cagr']):.2%} | "
                f"{str(bool(row['hard_gate_pass'])).lower()} | {str(bool(row['eligible_for_0726_audit'])).lower()} |"
            )
    (OUTPUT_ROOT / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", choices=["1626", "0717", "0726", "full"], default="full")
    args = parser.parse_args()

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    if args.window == "1626":
        _write_report(run_window("1626"), [])
        return
    if args.window == "0717":
        _write_report(run_window("0717"), [])
        return
    if args.window == "0726":
        _write_report(run_window("0726"), [])
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
    _write_report(all_records, gate_rows)


_load_local_env()
_BASE_CFG = _load_json(BASE_CFG_PATH)


if __name__ == "__main__":
    main()
