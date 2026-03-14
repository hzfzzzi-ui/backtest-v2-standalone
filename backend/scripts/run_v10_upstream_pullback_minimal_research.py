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
OUTPUT_ROOT = ROOT / "outputs" / "ops" / "v10_upstream_pullback_minimal_20260313"
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
VARIANTS: list[tuple[str, dict[tuple[Any, ...], Any]]] = [
    ("B0", {}),
    (
        "P1",
        {
            ("signal_generation", "breakout", "enable_pullback_candidates"): True,
            ("signal_generation", "breakout", "pullback_variant_mode"): "pb_tight_combo",
        },
    ),
    (
        "P1b",
        {
            ("signal_generation", "breakout", "enable_pullback_candidates"): True,
            ("signal_generation", "breakout", "pullback_variant_mode"): "pb_reclaim_ma20",
        },
    ),
]
SOURCE_ORDER = ["breakout", "pullback_overlap", "pullback_only"]
ALPHA_SOURCE_ALIAS = {
    "breakout": "breakout",
    "pullback": "pullback_only",
    "pullback_only": "pullback_only",
    "breakout+pullback": "pullback_overlap",
    "pullback_overlap": "pullback_overlap",
}


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
                ("signal_generation", "breakout", "enable_pullback_candidates"),
                ("signal_generation", "breakout", "pullback_variant_mode"),
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
        raise RuntimeError(
            f"{window_key}/{variant_name} drifted beyond allowed paths:\n" + "\n".join(lines)
        )
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
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 1e-12 else (999.0 if gross_profit > 0 else 0.0),
        "avg_hold_days": float(hold_qty_days / hold_qty_total) if hold_qty_total > 0 else 0.0,
        "avg_win_return": float(sum(positive_returns) / len(positive_returns)) if positive_returns else 0.0,
        "avg_loss_return": float(sum(negative_returns) / len(negative_returns)) if negative_returns else 0.0,
        "closed_roundtrips": int(len(realized_pnls)),
    }


def _variant_patch_lookup(variant_name: str) -> dict[tuple[Any, ...], Any]:
    for name, patch in VARIANTS:
        if name == variant_name:
            return patch
    return {}


def _normalize_source(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "unknown"
    return ALPHA_SOURCE_ALIAS.get(text, text)


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


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


def _collect_candidate_source_stats(results_dir: Path) -> tuple[dict[str, Any], pd.DataFrame]:
    funnel = _safe_read_csv(results_dir / "alpha_funnel.csv")
    if not funnel.empty and {"alpha_source", "candidate_count", "selected_count"}.issubset(funnel.columns):
        df = funnel.copy()
        df["alpha_source"] = df["alpha_source"].map(_normalize_source)
        grouped = (
            df.groupby("alpha_source", dropna=False)[["candidate_count", "selected_count", "rejected_count"]]
            .sum(numeric_only=True)
            .reset_index()
        )
    else:
        candidate_df = _safe_read_csv(results_dir / "candidate_signals.csv")
        if candidate_df.empty or "alpha_source" not in candidate_df.columns:
            grouped = pd.DataFrame(columns=["alpha_source", "candidate_count", "selected_count", "rejected_count"])
        else:
            df = candidate_df.copy()
            if "is_candidate" in df.columns:
                df = df[df["is_candidate"].astype(bool)]
            df["alpha_source"] = df["alpha_source"].map(_normalize_source)
            df["selected_flag"] = df.get("selected_flag", False)
            grouped = (
                df.groupby("alpha_source", dropna=False)
                .agg(
                    candidate_count=("symbol", "count"),
                    selected_count=("selected_flag", lambda s: int(pd.Series(s).astype(bool).sum())),
                )
                .reset_index()
            )
            grouped["rejected_count"] = grouped["candidate_count"] - grouped["selected_count"]

    if grouped.empty:
        stats = {
            "alpha_candidate_total": 0,
            "breakout_candidates": 0,
            "pullback_overlap_candidates": 0,
            "pullback_only_candidates": 0,
            "breakout_selected": 0,
            "pullback_overlap_selected": 0,
            "pullback_only_selected": 0,
        }
        return stats, grouped

    grouped["alpha_source"] = grouped["alpha_source"].fillna("unknown").astype(str)
    grouped = grouped.sort_values("alpha_source").reset_index(drop=True)
    stats = {
        "alpha_candidate_total": int(grouped["candidate_count"].sum()),
        "breakout_candidates": int(grouped.loc[grouped["alpha_source"] == "breakout", "candidate_count"].sum()),
        "pullback_overlap_candidates": int(grouped.loc[grouped["alpha_source"] == "pullback_overlap", "candidate_count"].sum()),
        "pullback_only_candidates": int(grouped.loc[grouped["alpha_source"] == "pullback_only", "candidate_count"].sum()),
        "breakout_selected": int(grouped.loc[grouped["alpha_source"] == "breakout", "selected_count"].sum()),
        "pullback_overlap_selected": int(grouped.loc[grouped["alpha_source"] == "pullback_overlap", "selected_count"].sum()),
        "pullback_only_selected": int(grouped.loc[grouped["alpha_source"] == "pullback_only", "selected_count"].sum()),
    }
    return stats, grouped


def _collect_pullback_variant_stats(results_dir: Path) -> pd.DataFrame:
    candidate_df = _safe_read_csv(results_dir / "candidate_signals.csv")
    if candidate_df.empty or "pullback_variant" not in candidate_df.columns:
        return pd.DataFrame(
            columns=[
                "pullback_variant",
                "candidate_count",
                "selected_count",
                "executed_buys",
                "realized_matches",
                "win_rate",
                "avg_return",
                "avg_hold_days",
                "realized_pnl",
            ]
        )
    df = candidate_df.copy()
    if "is_candidate" in df.columns:
        df = df[df["is_candidate"].astype(bool)]
    if df.empty:
        return pd.DataFrame()
    df["alpha_source"] = df.get("alpha_source", "").map(_normalize_source)
    df["pullback_variant"] = df["pullback_variant"].fillna("").astype(str)
    df["selected_flag"] = df.get("selected_flag", False)
    df = df[(df["alpha_source"].isin({"pullback_only", "pullback_overlap"})) & (df["pullback_variant"] != "")]
    if df.empty:
        return pd.DataFrame()
    return (
        df.groupby("pullback_variant", dropna=False)
        .agg(
            candidate_count=("symbol", "count"),
            selected_count=("selected_flag", lambda s: int(pd.Series(s).astype(bool).sum())),
        )
        .reset_index()
    )


def _collect_source_trade_stats(results_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    trades = _safe_read_csv(results_dir / "portfolio_trades.csv")
    if trades.empty or "symbol" not in trades.columns or "side" not in trades.columns:
        return pd.DataFrame(), pd.DataFrame()

    df = trades.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["symbol"] = df["symbol"].astype(str).str.lower()
    df = df.dropna(subset=["date", "symbol"])
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    open_lots: dict[str, list[dict[str, Any]]] = {}
    buy_counts: dict[str, int] = {}
    matched_rows: list[dict[str, Any]] = []

    for row in df.sort_values(["date"], kind="mergesort").itertuples(index=False):
        sym = str(getattr(row, "symbol", "")).lower()
        side = str(getattr(row, "side", "")).upper()
        qty = int(float(getattr(row, "qty", 0) or 0))
        if qty <= 0:
            continue
        meta = _safe_json_dict(getattr(row, "meta_json", None))
        net_amount = _safe_float(getattr(row, "net_amount", None))
        fill_price = _safe_float(getattr(row, "fill_price", None))
        price = fill_price if fill_price else _safe_float(getattr(row, "price", None))
        unit_value = (net_amount / max(qty, 1)) if net_amount else price
        if unit_value is None:
            continue
        day = pd.Timestamp(getattr(row, "date"))

        if side == "BUY":
            alpha_source = _normalize_source(meta.get("alpha_source"))
            buy_counts[alpha_source] = int(buy_counts.get(alpha_source, 0)) + 1
            open_lots.setdefault(sym, []).append(
                {
                    "qty": qty,
                    "unit_cost": float(unit_value),
                    "date": day,
                    "alpha_source": alpha_source,
                    "pullback_variant": str(meta.get("pullback_variant") or ""),
                }
            )
            continue

        if side != "SELL":
            continue

        remain = qty
        lots = open_lots.get(sym, [])
        while remain > 0 and lots:
            head = lots[0]
            matched = min(remain, int(head["qty"]))
            unit_cost = float(head["unit_cost"])
            pnl = float(unit_value - unit_cost) * matched
            ret = (float(unit_value) / unit_cost - 1.0) if unit_cost > 1e-8 else None
            hold_days = int((day - pd.Timestamp(head["date"])).days)
            matched_rows.append(
                {
                    "alpha_source": str(head["alpha_source"]),
                    "pullback_variant": str(head["pullback_variant"]),
                    "matched_qty": int(matched),
                    "return_pct": ret,
                    "hold_days": hold_days,
                    "pnl": pnl,
                }
            )
            head["qty"] = int(head["qty"]) - matched
            remain -= matched
            if int(head["qty"]) <= 0:
                lots.pop(0)
        if lots:
            open_lots[sym] = lots

    matched_df = pd.DataFrame(matched_rows)
    if matched_df.empty:
        source_df = pd.DataFrame(
            [
                {
                    "alpha_source": source,
                    "executed_buys": int(buy_counts.get(source, 0)),
                    "realized_matches": 0,
                    "win_rate": None,
                    "avg_return": None,
                    "avg_hold_days": None,
                    "realized_pnl": 0.0,
                    "realized_pnl_share": None,
                }
                for source in sorted(buy_counts.keys())
            ]
        )
        return source_df, matched_df

    grouped = (
        matched_df.groupby("alpha_source", dropna=False)
        .agg(
            realized_matches=("matched_qty", "count"),
            win_rate=("pnl", lambda s: float((pd.Series(s) > 0).mean())),
            avg_return=("return_pct", "mean"),
            avg_hold_days=("hold_days", "mean"),
            realized_pnl=("pnl", "sum"),
        )
        .reset_index()
    )
    grouped["executed_buys"] = grouped["alpha_source"].map(lambda source: int(buy_counts.get(str(source), 0)))
    total_realized_pnl = float(grouped["realized_pnl"].sum())
    grouped["realized_pnl_share"] = grouped["realized_pnl"] / total_realized_pnl if abs(total_realized_pnl) > 1e-8 else None
    grouped = grouped[
        [
            "alpha_source",
            "executed_buys",
            "realized_matches",
            "win_rate",
            "avg_return",
            "avg_hold_days",
            "realized_pnl",
            "realized_pnl_share",
        ]
    ]
    return grouped.sort_values("alpha_source").reset_index(drop=True), matched_df


def _merge_source_stats(*, phase_name: str, candidate_stats_df: pd.DataFrame, trade_stats_df: pd.DataFrame) -> pd.DataFrame:
    left = candidate_stats_df.copy()
    if left.empty:
        left = pd.DataFrame({"alpha_source": SOURCE_ORDER})
        left["candidate_count"] = 0
        left["selected_count"] = 0
        left["rejected_count"] = 0
    right = trade_stats_df.copy()
    if right.empty:
        right = pd.DataFrame({"alpha_source": SOURCE_ORDER})
        right["executed_buys"] = 0
        right["realized_matches"] = 0
        right["win_rate"] = None
        right["avg_return"] = None
        right["avg_hold_days"] = None
        right["realized_pnl"] = 0.0
        right["realized_pnl_share"] = None
    merged = left.merge(right, on="alpha_source", how="outer")
    for col in ("candidate_count", "selected_count", "rejected_count", "executed_buys", "realized_matches"):
        if col in merged.columns:
            merged[col] = merged[col].fillna(0).astype(int)
    merged.insert(0, "phase", phase_name)
    merged["source_order"] = merged["alpha_source"].map({name: idx for idx, name in enumerate(SOURCE_ORDER, start=1)}).fillna(99)
    return merged.sort_values(["phase", "source_order", "alpha_source"]).drop(columns=["source_order"]).reset_index(drop=True)


def _merge_variant_stats(*, phase_name: str, candidate_variant_df: pd.DataFrame, matched_df: pd.DataFrame) -> pd.DataFrame:
    left = candidate_variant_df.copy()
    if left.empty:
        return pd.DataFrame()
    right = pd.DataFrame(columns=["pullback_variant"])
    if not matched_df.empty and "pullback_variant" in matched_df.columns:
        raw = matched_df.copy()
        raw["pullback_variant"] = raw["pullback_variant"].fillna("").astype(str)
        raw = raw[raw["pullback_variant"] != ""]
        if not raw.empty:
            right = (
                raw.groupby("pullback_variant", dropna=False)
                .agg(
                    realized_matches=("matched_qty", "count"),
                    win_rate=("pnl", lambda s: float((pd.Series(s) > 0).mean())),
                    avg_return=("return_pct", "mean"),
                    avg_hold_days=("hold_days", "mean"),
                    realized_pnl=("pnl", "sum"),
                )
                .reset_index()
            )
            buy_orders = raw.groupby("pullback_variant", dropna=False).size().reset_index(name="executed_buys_proxy")
            right = right.merge(buy_orders, on="pullback_variant", how="left")
    merged = left.merge(right, on="pullback_variant", how="left")
    for col in ("executed_buys_proxy", "realized_matches"):
        if col in merged.columns:
            merged[col] = merged[col].fillna(0).astype(int)
    merged.insert(0, "phase", phase_name)
    return merged.sort_values(["phase", "pullback_variant"]).reset_index(drop=True)


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


def _summarize_results(window_key: str, variant_name: str, result: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
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
    trade_stats = _compute_trade_stats(trades_df)
    candidate_stats, candidate_source_df = _collect_candidate_source_stats(results_dir)
    trade_source_df, matched_df = _collect_source_trade_stats(results_dir)
    source_df = _merge_source_stats(
        phase_name=f"{window_key}_{variant_name}",
        candidate_stats_df=candidate_source_df,
        trade_stats_df=trade_source_df,
    )
    variant_df = _merge_variant_stats(
        phase_name=f"{window_key}_{variant_name}",
        candidate_variant_df=_collect_pullback_variant_stats(results_dir),
        matched_df=matched_df,
    )
    window_periods = WINDOWS[window_key]["periods"]
    period_metrics = {
        period_name: _period_metrics(nav_df, start=period_start, end=period_end)
        for period_name, (period_start, period_end) in window_periods.items()
    }

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
        "win_rate": float(trade_stats["win_rate"]),
        "profit_factor": float(trade_stats["profit_factor"]),
        "avg_hold_days": float(trade_stats["avg_hold_days"]),
        "avg_win_return": float(trade_stats["avg_win_return"]),
        "avg_loss_return": float(trade_stats["avg_loss_return"]),
        "closed_roundtrips": int(trade_stats["closed_roundtrips"]),
        "period_metrics": period_metrics,
        "pullback_enabled": bool(variant_name != "B0"),
        "pullback_variant_mode": "",
    }
    summary.update(candidate_stats)
    summary["breakout_executed_buys"] = int(source_df.loc[source_df["alpha_source"] == "breakout", "executed_buys"].sum())
    summary["pullback_overlap_executed_buys"] = int(source_df.loc[source_df["alpha_source"] == "pullback_overlap", "executed_buys"].sum())
    summary["pullback_only_executed_buys"] = int(source_df.loc[source_df["alpha_source"] == "pullback_only", "executed_buys"].sum())
    if variant_name == "B0":
        summary["baseline_match"] = _baseline_match(window_key, perf)
    else:
        summary["pullback_variant_mode"] = str(
            _variant_patch_lookup(variant_name).get(("signal_generation", "breakout", "pullback_variant_mode"), "")
        )
    return summary, source_df, variant_df


def _run_one(window_key: str, variant_name: str, patch: dict[tuple[Any, ...], Any]) -> dict[str, Any]:
    semantic_cfg, diff_rows = _build_variant_cfg(window_key, variant_name, patch)
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
    summary, source_df, variant_df = _summarize_results(window_key, variant_name, result)
    elapsed = time.perf_counter() - t0
    print(
        "  done: "
        f"exp_id={summary['exp_id']} "
        f"cagr={summary['cagr']:.4f} "
        f"max_dd={summary['max_drawdown']:.4f} "
        f"pullback_only_candidates={summary['pullback_only_candidates']} "
        f"elapsed={elapsed:.1f}s"
    )
    return {
        "window": window_key,
        "variant": variant_name,
        "request_payload": request_payload,
        "diff_rows": diff_rows,
        "summary": summary,
        "source_df": source_df,
        "variant_df": variant_df,
    }


def _window_output_dir(window_key: str) -> Path:
    return OUTPUT_ROOT / window_key


def run_window(window_key: str) -> list[dict[str, Any]]:
    if window_key not in WINDOWS:
        raise RuntimeError(f"unsupported window: {window_key}")
    output_dir = _window_output_dir(window_key)
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    source_frames: list[pd.DataFrame] = []
    variant_frames: list[pd.DataFrame] = []
    for variant_name, patch in VARIANTS:
        record = _run_one(window_key, variant_name, patch)
        records.append(record)
        _write_json(output_dir / f"request_payload_{variant_name}.json", record["request_payload"])
        _write_json(output_dir / f"diff_rows_{variant_name}.json", record["diff_rows"])
        if not record["source_df"].empty:
            source_frames.append(record["source_df"])
        if not record["variant_df"].empty:
            variant_frames.append(record["variant_df"])
    summaries = [record["summary"] for record in records]
    _write_json(output_dir / f"summary_{window_key}.json", summaries)
    source_out = pd.concat(source_frames, ignore_index=True) if source_frames else pd.DataFrame()
    source_out.to_csv(output_dir / f"source_contribution_{window_key}.csv", index=False, encoding="utf-8-sig")
    variant_out = pd.concat(variant_frames, ignore_index=True) if variant_frames else pd.DataFrame()
    variant_out.to_csv(output_dir / f"pullback_variant_contribution_{window_key}.csv", index=False, encoding="utf-8-sig")
    rows: list[dict[str, Any]] = []
    for summary in summaries:
        row = {
            key: value
            for key, value in summary.items()
            if key not in {"period_metrics", "baseline_match"}
        }
        for period_name, metrics in dict(summary.get("period_metrics") or {}).items():
            row[f"{period_name}_return"] = float(metrics.get("return", 0.0) or 0.0)
            row[f"{period_name}_max_drawdown"] = float(metrics.get("max_drawdown", 0.0) or 0.0)
            row[f"{period_name}_days"] = int(metrics.get("days", 0) or 0)
        if isinstance(summary.get("baseline_match"), dict):
            row["baseline_match"] = bool(summary["baseline_match"].get("matches"))
        rows.append(row)
    pd.DataFrame(rows).to_csv(output_dir / f"summary_{window_key}.csv", index=False, encoding="utf-8-sig")
    _write_json(
        output_dir / f"validation_{window_key}.json",
        {
            "window": window_key,
            "baseline_reference_exp_id": REFERENCE_EXP_IDS[window_key],
            "baseline_match": next((row.get("baseline_match") for row in summaries if row["variant"] == "B0"), None),
            "allowed_paths": sorted(_path_text(path) for path in _allowed_paths(window_key, "P1")),
        },
    )
    return records


def _write_report(all_records: list[dict[str, Any]]) -> None:
    summaries = [record["summary"] for record in all_records]
    _write_json(OUTPUT_ROOT / "summary_all.json", summaries)
    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(OUTPUT_ROOT / "summary_all.csv", index=False, encoding="utf-8-sig")

    comparison_rows: list[dict[str, Any]] = []
    for window_key in ("0717", "1626"):
        base_rows = [row for row in summaries if row["window"] == window_key and row["variant"] == "B0"]
        if not base_rows:
            continue
        base = base_rows[0]
        for row in summaries:
            if row["window"] != window_key or row["variant"] == "B0":
                continue
            comparison_rows.append(
                {
                    "window": window_key,
                    "variant": row["variant"],
                    "delta_cagr": float(row["cagr"] - base["cagr"]),
                    "delta_max_drawdown": float(row["max_drawdown"] - base["max_drawdown"]),
                    "delta_sharpe": float(row["sharpe"] - base["sharpe"]),
                    "delta_turnover": float(row["turnover"] - base["turnover"]),
                    "delta_trades": int(row["trades"] - base["trades"]),
                    "delta_alpha_candidates": int(row["alpha_candidate_total"] - base["alpha_candidate_total"]),
                    "delta_pullback_only_candidates": int(row["pullback_only_candidates"] - base["pullback_only_candidates"]),
                    "delta_pullback_only_buys": int(row["pullback_only_executed_buys"] - base["pullback_only_executed_buys"]),
                }
            )
    pd.DataFrame(comparison_rows).to_csv(OUTPUT_ROOT / "comparison.csv", index=False, encoding="utf-8-sig")

    source_frames = [record["source_df"] for record in all_records if not record["source_df"].empty]
    pd.concat(source_frames, ignore_index=True).to_csv(
        OUTPUT_ROOT / "source_contribution_all.csv",
        index=False,
        encoding="utf-8-sig",
    ) if source_frames else pd.DataFrame().to_csv(OUTPUT_ROOT / "source_contribution_all.csv", index=False, encoding="utf-8-sig")

    variant_frames = [record["variant_df"] for record in all_records if not record["variant_df"].empty]
    pd.concat(variant_frames, ignore_index=True).to_csv(
        OUTPUT_ROOT / "pullback_variant_contribution_all.csv",
        index=False,
        encoding="utf-8-sig",
    ) if variant_frames else pd.DataFrame().to_csv(OUTPUT_ROOT / "pullback_variant_contribution_all.csv", index=False, encoding="utf-8-sig")

    lines = [
        "# V10 Upstream Pullback Minimal Research",
        "",
        "- base_config: `baseline_V10`",
        "- main_change: `signal_generation.breakout.enable_pullback_candidates / pullback_variant_mode`",
        "- unchanged: benchmark, universe_mode, PIT membership, costs, execution, exit rules, max_positions",
        "",
        "## Summary",
        "",
        "| window | variant | Total Return | CAGR | MaxDD | Sharpe | Calmar | Trades | WinRate | AvgHoldDays | Alpha Candidates | Pullback Only Candidates | Pullback Only Buys | exp_id |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in summaries:
        lines.append(
            f"| {row['window']} | {row['variant']} | {float(row['total_return']):.2%} | {float(row['cagr']):.2%} | "
            f"{float(row['max_drawdown']):.2%} | {float(row['sharpe']):.3f} | {float(row['calmar']):.3f} | "
            f"{int(row['trades'])} | {float(row['win_rate']):.2%} | {float(row['avg_hold_days']):.2f} | "
            f"{int(row['alpha_candidate_total'])} | {int(row['pullback_only_candidates'])} | {int(row['pullback_only_executed_buys'])} | "
            f"`{row['exp_id']}` |"
        )
    if comparison_rows:
        lines.extend(
            [
                "",
                "## Baseline Deltas",
                "",
                "| window | variant | dCAGR | dMaxDD | dSharpe | dTurnover | dTrades | dAlphaCandidates | dPullbackOnlyCandidates | dPullbackOnlyBuys |",
                "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in comparison_rows:
            lines.append(
                f"| {row['window']} | {row['variant']} | {float(row['delta_cagr']):.2%} | {float(row['delta_max_drawdown']):.2%} | "
                f"{float(row['delta_sharpe']):.3f} | {float(row['delta_turnover']):.2%} | {int(row['delta_trades'])} | "
                f"{int(row['delta_alpha_candidates'])} | {int(row['delta_pullback_only_candidates'])} | {int(row['delta_pullback_only_buys'])} |"
            )
    (OUTPUT_ROOT / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", choices=["0717", "1626", "all"], default="all")
    args = parser.parse_args()

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    if args.window == "all":
        all_records: list[dict[str, Any]] = []
        for window_key in ("0717", "1626"):
            all_records.extend(run_window(window_key))
        _write_report(all_records)
        return
    records = run_window(args.window)
    _write_report(records)


_load_local_env()
_BASE_CFG = _load_json(BASE_CFG_PATH)


if __name__ == "__main__":
    main()
