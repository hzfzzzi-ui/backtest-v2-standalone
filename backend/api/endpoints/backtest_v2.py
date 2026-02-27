from __future__ import annotations

import json
import math
import os
import hashlib
import subprocess
import sys
import threading
import time
import uuid
from decimal import Decimal
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from pandas.errors import EmptyDataError
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from .backtest_v2_artifacts import stabilize_experiment_result

router = APIRouter(tags=["backtest_v2"])

_JOBS: dict[str, dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()

try:
    import numpy as _np  # type: ignore
except Exception:  # pragma: no cover
    _np = None

_ROWS_NUMERIC_FIELDS = [
    "total_return",
    "max_drawdown",
    "cagr",
    "sharpe",
    "calmar",
    "trades",
    "turnover",
    "top10_profit_concentration",
    "raw_signal",
    "blocked",
    "orders",
    "skipped",
    "closed_trades",
    "gate_on_rate",
    "mf_rank_applied_rate",
    "trend_slope_block_count",
    "atr_stop_exit_count",
    "atr_trail_exit_count",
    "atr_trail_update_count",
]

_ROWS_INTEGER_FIELDS = {
    "trades",
    "raw_signal",
    "blocked",
    "orders",
    "skipped",
    "closed_trades",
    "trend_slope_block_count",
    "atr_stop_exit_count",
    "atr_trail_exit_count",
    "atr_trail_update_count",
}

_PIPELINE_STAGE_NAMES = [
    "Universe",
    "Signal",
    "Filters/Gates",
    "Rank",
    "Sizing",
    "Execution",
    "Risk/Exit",
    "Portfolio",
]

_LEGACY_PRESET_ALIAS: dict[str, str] = {
    "G1-G4": "TREND_QUALITY_VALIDATE_V1",
    "REGIME_BUFFER_2X2": "TREND_QUALITY_VALIDATE_V1",
    "ATR_RISK_2X2": "TREND_QUALITY_VALIDATE_V1",
}

_FLOW_SCRIPT_CONFIG_ID = "cfg_flow_smoke_v1"


def _flow_script_config_json() -> dict[str, Any]:
    return {
        "mode": "experiment",
        "strategy_pack": "SMA_CROSS",
        "universe_mode": "CUSTOM",
        "universe": {
            "start": "2025-01-01",
            "end": "2025-03-31",
            "benchmark": "000300.SH",
            "symbols": ["600000.SH", "000001.SZ", "600519.SH"],
            "limit": 100,
            "filters": {
                "exclude_st": True,
                "exclude_suspended": True,
                "min_list_days": 120,
                "min_avg_turnover_20d": 100000000,
                "limit_rule": "skip",
            },
        },
        "signal_generation": {
            "enabled": True,
            "strategy": "SMA_CROSS",
            "sma": {"fast_ma": 5, "slow_ma": 20, "entry_buffer_pct": 1.0},
        },
        "signal_composition": {"enabled": True, "compose_mode": "WEIGHTED_SCORE"},
        "exit_rules": {
            "enabled": True,
            "signal_reverse": True,
            "atr_stop": {"enabled": True, "k": 0.8},
            "trailing": {"enabled": False, "k": 2.0},
        },
        "position_risk": {
            "enabled": True,
            "max_positions": 10,
            "single_stock_cap": 0.1,
            "industry_cap": 0.3,
            "lot": 100,
            "cash_shortage_policy": "skip",
        },
        "flow_script": {
            "script_id": "flow_smoke_v1",
            "description": "最小通流：validate -> experiment(run_async) -> group inspect -> execution preview",
            "recommended_preset": "G1-G4",
        },
    }


def _ensure_builtin_flow_script_config() -> None:
    root = _configs_root()
    p = root / f"{_FLOW_SCRIPT_CONFIG_ID}.json"
    cfg_obj = sanitize_json(_flow_script_config_json())
    cfg_hash = _hash_json(cfg_obj)
    saved_at = datetime.now().isoformat()
    payload = {
        "config_id": _FLOW_SCRIPT_CONFIG_ID,
        "config_hash": cfg_hash,
        "saved_at": saved_at,
        "name": "最小通流脚本",
        "tags": ["flow_script", "builtin"],
        "config_json": cfg_obj,
    }
    if p.exists():
        try:
            prev = json.loads(p.read_text(encoding="utf-8-sig"))
            if isinstance(prev, dict) and prev.get("config_hash") == cfg_hash:
                return
        except Exception:
            pass
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _coerce_number(value: Any, *, integer: bool = False) -> int | float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return int(value) if integer else float(value)
    if isinstance(value, (int, float)):
        n = float(value)
        if math.isnan(n) or math.isinf(n):
            return None
        return int(n) if integer else n
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            n = float(text)
        except Exception:
            return None
        if math.isnan(n) or math.isinf(n):
            return None
        return int(n) if integer else n
    return None


def _parse_ps_object_row(raw: str) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if not (text.startswith("@{") and text.endswith("}")):
        return None
    out: dict[str, Any] = {}
    for part in text[2:-1].split(";"):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        out[str(k).strip()] = str(v).strip()
    return out


def sanitize_json(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    if _np is not None and isinstance(obj, _np.generic):  # numpy scalar -> python scalar
        return sanitize_json(obj.item())
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, (str, int, bool)) or obj is None:
        return obj
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, tuple):
        return [sanitize_json(v) for v in obj]
    if isinstance(obj, list):
        return [sanitize_json(v) for v in obj]
    if isinstance(obj, dict):
        return {str(k): sanitize_json(v) for k, v in obj.items()}
    return str(obj)


def normalize_row(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        out = dict(row)
    elif isinstance(row, str):
        parsed = _parse_ps_object_row(row)
        if parsed is not None:
            out = parsed
        else:
            out = {"group_id": row.strip(), "status": "FAILED", "error_message": "ROW_PARSE_FAILED"}
    else:
        out = {"group_id": str(row), "status": "FAILED", "error_message": "ROW_TYPE_INVALID"}

    out = sanitize_json(out)
    status_raw = str(out.get("status") or "").strip().upper()
    if status_raw not in {"OK", "FAILED", "CANCELED"}:
        status_raw = "FAILED" if out.get("status") else "OK"
    tier_raw = str(out.get("tier") or "T0").strip().upper()
    if tier_raw not in {"T0", "T1", "T2", "T3"}:
        tier_raw = "T0"

    out["group_id"] = str(out.get("group_id") or "")
    out["status"] = status_raw
    out["tier"] = tier_raw
    out["group_dir"] = str(out.get("group_dir") or "")
    out["group_files"] = dict(out.get("group_files") or {})

    for field in _ROWS_NUMERIC_FIELDS:
        out[field] = _coerce_number(out.get(field), integer=field in _ROWS_INTEGER_FIELDS)

    return out


def _resolve_candidate_dir(raw: Any, results_dir: Path) -> Path | None:
    text = str(raw or "").strip()
    if not text:
        return None
    p = Path(text)
    if not p.is_absolute():
        p = results_dir / p
    p = p.resolve()
    return p if p.exists() and p.is_dir() else None


def _to_rel(path: Path, root: Path) -> str:
    p = path.resolve()
    r = root.resolve()
    if p.is_relative_to(r):
        return str(p.relative_to(r)).replace("\\", "/")
    return str(p).replace("\\", "/")


def _write_nav_csv(group_dir: Path, row: dict[str, Any], missing_fields: list[str]) -> Path:
    nav_path = group_dir / "nav.csv"
    if nav_path.exists():
        return nav_path
    eq_path = group_dir / "equity_curve.csv"
    if eq_path.exists():
        try:
            df = pd.read_csv(eq_path)
            value_col = None
            for col in ("nav", "strategy_nav", "equity", "portfolio_value"):
                if col in df.columns:
                    value_col = col
                    break
            if value_col is not None:
                date_col = "date" if "date" in df.columns else ("dt" if "dt" in df.columns else None)
                if date_col is None:
                    out = pd.DataFrame({"date": pd.to_datetime(df.index, errors="coerce"), "nav": pd.to_numeric(df[value_col], errors="coerce")})
                else:
                    out = pd.DataFrame({"date": pd.to_datetime(df[date_col], errors="coerce"), "nav": pd.to_numeric(df[value_col], errors="coerce")})
                out["date"] = out["date"].dt.strftime("%Y-%m-%d")
                out = out.dropna(subset=["date", "nav"])
                if not out.empty:
                    out.to_csv(nav_path, index=False)
                    return nav_path
        except Exception:
            pass
    missing_fields.append("missing_nav_source")
    pd.DataFrame(columns=["date", "nav"]).to_csv(nav_path, index=False)
    return nav_path


def _write_funnel_csv(group_dir: Path, row: dict[str, Any], missing_fields: list[str]) -> Path:
    path = group_dir / "funnel.csv"
    if path.exists():
        return path
    has_source = any(row.get(k) is not None for k in ("raw_signal", "blocked", "orders", "skipped", "closed_trades"))
    if not has_source:
        missing_fields.append("missing_funnel_source")
    data = {
        "raw_signal": int(_coerce_number(row.get("raw_signal"), integer=True) or 0),
        "blocked": int(_coerce_number(row.get("blocked"), integer=True) or 0),
        "orders": int(_coerce_number(row.get("orders"), integer=True) or 0),
        "skipped": int(_coerce_number(row.get("skipped"), integer=True) or 0),
        "closed_trades": int(_coerce_number(row.get("closed_trades"), integer=True) or 0),
    }
    pd.DataFrame([data]).to_csv(path, index=False)
    return path


def _write_reason_code_counts_csv(group_dir: Path, missing_fields: list[str]) -> Path:
    path = group_dir / "reason_code_counts.csv"
    if path.exists():
        return path

    def _norm_code(code: Any, *, prefix: str | None = None) -> str:
        text = str(code or "").strip().upper()
        if not text:
            return ""
        text = text.replace(" ", "_")
        if prefix and not text.startswith(f"{prefix}_"):
            text = f"{prefix}_{text}"
        return text

    counts: dict[str, int] = {}

    def _add(code: Any, cnt: Any = 1, *, prefix: str | None = None) -> None:
        c = _norm_code(code, prefix=prefix)
        if not c:
            return
        n = int(_coerce_number(cnt, integer=True) or 0)
        if n <= 0:
            return
        counts[c] = int(counts.get(c, 0) + n)

    # 1) Explicit summary csv has highest priority.
    src = group_dir / "reason_code_summary.csv"
    if src.exists():
        try:
            df = pd.read_csv(src)
            code_col = "code" if "code" in df.columns else ("reason_code" if "reason_code" in df.columns else None)
            count_col = "count" if "count" in df.columns else ("orders" if "orders" in df.columns else None)
            if code_col and count_col:
                for _, row in df.iterrows():
                    _add(row.get(code_col), row.get(count_col))
        except Exception:
            pass

    # 2) report_summary/report audit source (blocked/skipped/exit).
    summary = _load_json_file(group_dir / "report_summary.json")
    report = _load_json_file(group_dir / "report.json")
    run_meta = _load_json_file(group_dir / "run_meta.json")

    for src_obj in (summary, report, run_meta):
        if not isinstance(src_obj, dict):
            continue

        reasons = src_obj.get("reasons")
        if isinstance(reasons, list):
            for item in reasons:
                if not isinstance(item, dict):
                    continue
                _add(
                    item.get("reason_code"),
                    item.get("count") if item.get("count") is not None else item.get("orders"),
                )

        exit_map = src_obj.get("exit_reason_breakdown")
        if isinstance(exit_map, dict):
            for code, cnt in exit_map.items():
                _add(code, cnt)

        for key in ("blocked_reasons_top3", "top_blocked_reason"):
            m = src_obj.get(key)
            if isinstance(m, dict):
                for code, cnt in m.items():
                    _add(code, cnt, prefix="BLOCKED")
        m2 = (src_obj.get("signal_stats") or {}).get("blocked_reasons_top3")
        if isinstance(m2, dict):
            for code, cnt in m2.items():
                _add(code, cnt, prefix="BLOCKED")

        for key in ("skipped_reasons_top3", "top_skip_reason"):
            m = src_obj.get(key)
            if isinstance(m, dict):
                for code, cnt in m.items():
                    _add(code, cnt, prefix="SKIPPED")
        m3 = (src_obj.get("execution_stats") or {}).get("skipped_reasons_top3")
        if isinstance(m3, dict):
            for code, cnt in m3.items():
                _add(code, cnt, prefix="SKIPPED")

        audit_rules = src_obj.get("audit_rules")
        if isinstance(audit_rules, dict):
            br = audit_rules.get("blocked_reasons_top3")
            if isinstance(br, dict):
                for code, cnt in br.items():
                    _add(code, cnt, prefix="BLOCKED")
            sr = audit_rules.get("top_skip_reason")
            if isinstance(sr, dict):
                for code, cnt in sr.items():
                    _add(code, cnt, prefix="SKIPPED")

    # 3) CSV fallback from orders/signals (best effort).
    orders_csv = group_dir / "orders.csv"
    if orders_csv.exists():
        try:
            odf = pd.read_csv(orders_csv)
            if not odf.empty:
                if "reason_code" in odf.columns:
                    vc = odf["reason_code"].astype(str).str.strip().replace({"": "UNKNOWN"}).value_counts().to_dict()
                    for code, cnt in vc.items():
                        _add(code, cnt)
                if "skip_reason" in odf.columns:
                    vc2 = odf["skip_reason"].astype(str).str.strip().replace({"": "UNKNOWN"}).value_counts().to_dict()
                    for code, cnt in vc2.items():
                        _add(code, cnt, prefix="SKIPPED")
        except Exception:
            pass
    signals_csv = group_dir / "signals.csv"
    if signals_csv.exists():
        try:
            sdf = pd.read_csv(signals_csv)
            if not sdf.empty and "reason_code" in sdf.columns:
                vc = sdf["reason_code"].astype(str).str.strip().replace({"": "UNKNOWN"}).value_counts().to_dict()
                for code, cnt in vc.items():
                    _add(code, cnt, prefix="BLOCKED")
        except Exception:
            pass

    if counts:
        data = sorted(counts.items(), key=lambda kv: (-int(kv[1]), str(kv[0])))
        total = float(sum(int(v) for _, v in data))
        out_df = pd.DataFrame(
            [
                {
                    "code": str(code),
                    "count": int(cnt),
                    "ratio": (float(cnt) / total) if total > 0 else 0.0,
                }
                for code, cnt in data
            ]
        )
        out_df.to_csv(path, index=False)
        return path

    missing_fields.append("missing_reason_code_source")
    pd.DataFrame([{"code": "", "count": 0, "ratio": 0.0}]).to_csv(path, index=False)
    return path


def _infer_universe_size(row: dict[str, Any], meta: dict[str, Any], missing_fields: list[str]) -> int | None:
    # Priority: real size from row/run profile/symbols_count fields.
    candidates = [
        row.get("universe_size"),
        row.get("universe_filtered_count"),
        row.get("symbols_count"),
        (meta.get("run_profile_summary") or {}).get("symbols_count") if isinstance(meta.get("run_profile_summary"), dict) else None,
        meta.get("symbols_count"),
    ]
    for c in candidates:
        n = _coerce_number(c, integer=True)
        if n is not None and int(n) > 0:
            return int(n)

    approx = _coerce_number(row.get("universe_limit"), integer=True)
    if approx is None:
        approx = _coerce_number(meta.get("universe_limit"), integer=True)
    if approx is not None and int(approx) > 0:
        missing_fields.append("universe_size_approx")
        return int(approx)
    return None


def build_run_meta(
    *,
    group_dir: Path,
    row: dict[str, Any],
    meta: dict[str, Any],
    artifacts: dict[str, str],
    missing_fields: list[str],
) -> dict[str, Any]:
    counters: dict[str, int | float] = {}
    counter_fields = [
        "raw_signal",
        "blocked",
        "orders",
        "skipped",
        "closed_trades",
        "gate_on_rate",
        "mf_rank_applied_rate",
        "trend_slope_block_count",
        "atr_stop_exit_count",
        "atr_trail_exit_count",
        "atr_trail_update_count",
    ]
    for field in counter_fields:
        raw = row.get(field)
        if raw is None:
            missing_fields.append(f"missing_counter_{field}_source")
        n = _coerce_number(raw, integer=field in _ROWS_INTEGER_FIELDS)
        counters[field] = int(n or 0) if field in _ROWS_INTEGER_FIELDS else float(n or 0.0)

    pipeline = [
        {"name": "Universe", "enabled": True, "params": {}, "counters": {"universe_size": int(_coerce_number(row.get("universe_size"), integer=True) or 0)}},
        {"name": "Signal", "enabled": True, "params": {}, "counters": {"raw_signal": counters["raw_signal"]}},
        {"name": "Filters/Gates", "enabled": True, "params": {}, "counters": {"blocked": counters["blocked"], "gate_on_rate": counters["gate_on_rate"], "trend_slope_block_count": counters["trend_slope_block_count"]}},
        {"name": "Rank", "enabled": True, "params": {}, "counters": {"mf_rank_applied_rate": counters["mf_rank_applied_rate"]}},
        {"name": "Sizing", "enabled": True, "params": {}, "counters": {}},
        {"name": "Execution", "enabled": True, "params": {}, "counters": {"orders": counters["orders"], "skipped": counters["skipped"]}},
        {"name": "Risk/Exit", "enabled": True, "params": {}, "counters": {"atr_stop_exit_count": counters["atr_stop_exit_count"], "atr_trail_exit_count": counters["atr_trail_exit_count"], "atr_trail_update_count": counters["atr_trail_update_count"]}},
        {"name": "Portfolio", "enabled": True, "params": {}, "counters": {"closed_trades": counters["closed_trades"]}},
    ]
    # hard guard to keep stage order stable
    if [s["name"] for s in pipeline] != _PIPELINE_STAGE_NAMES:
        raise ValueError("pipeline stage order drift")

    filters = meta.get("filters")
    if not isinstance(filters, dict):
        filters = {}

    universe_size = _infer_universe_size(row, meta, missing_fields)

    run_meta = {
        "run_id": str(row.get("run_id") or ""),
        "exp_id": str(meta.get("exp_id") or ""),
        "group_id": str(row.get("group_id") or ""),
        "preset": str(meta.get("preset") or ""),
        "data": {
            "start": meta.get("start_date"),
            "end": meta.get("end_date"),
            "benchmark": meta.get("benchmark"),
            "compare_symbol": meta.get("compare_symbol"),
            "universe_mode": str(meta.get("universe_mode") or "db_index_constituents"),
            "universe_size": universe_size,
            "universe_limit": _coerce_number(meta.get("universe_limit"), integer=True),
            "filters": filters,
        },
        "code": {
            "git_commit": meta.get("git_commit"),
            "engine_mode": str(meta.get("engine_mode") or "VECTOR_FAST_STRICT"),
            "execution_profile": str(meta.get("execution_profile") or "tradable"),
            "fast_mode": bool(meta.get("fast_mode", True)),
        },
        "pipeline": pipeline,
        "counters": counters,
        "artifacts": artifacts,
        "missing_fields": sorted(set(str(x) for x in missing_fields)),
    }
    return sanitize_json(run_meta)


def _infer_manifest_dims(matrix_head: Any) -> tuple[dict[str, Any], list[str]]:
    missing: list[str] = []
    if not isinstance(matrix_head, list) or not matrix_head:
        return {}, ["missing_dims_from_matrix_head"]
    if not all(isinstance(x, dict) for x in matrix_head):
        return {}, ["missing_dims_from_matrix_head"]
    cols: list[str] = []
    seen = set()
    for row in matrix_head:
        for k in row.keys():
            sk = str(k)
            if sk not in seen:
                seen.add(sk)
                cols.append(sk)
    if not cols:
        return {}, ["missing_dims_from_matrix_head"]
    return {"matrix_head_columns": cols, "matrix_head_rows": len(matrix_head)}, missing


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _pick_from_paths(obj: Any, paths: list[tuple[str, ...]], *, integer: bool = False) -> int | float | None:
    if not isinstance(obj, dict):
        return None
    for path in paths:
        cur: Any = obj
        ok = True
        for key in path:
            if not isinstance(cur, dict) or key not in cur:
                ok = False
                break
            cur = cur.get(key)
        if not ok:
            continue
        n = _coerce_number(cur, integer=integer)
        if n is not None:
            return int(n) if integer else float(n)
    return None


def _extract_debug_atr_counters(group_dir: Path) -> dict[str, int]:
    path = group_dir / "debug_atr.csv"
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path)
    except Exception:
        return {}
    if df.empty:
        return {}

    out: dict[str, int] = {}
    if "reason_code" in df.columns:
        reason = df["reason_code"].astype(str).str.upper()
        out["atr_stop_exit_count"] = int(reason.eq("ATR_STOP_LOSS").sum())
        out["atr_trail_exit_count"] = int(reason.eq("ATR_TRAIL_EXIT").sum())

    # No stable engine-level field yet; infer best-effort from debug rows.
    trail_updates = 0
    if "triggered_rule" in df.columns:
        tr = df["triggered_rule"].astype(str).str.upper()
        trail_updates = int(
            (
                tr.str.contains("TRAIL", na=False)
                & tr.str.contains("UPDATE|RAISE|ADJUST", regex=True, na=False)
                & (~tr.str.contains("EXIT", na=False))
            ).sum()
        )
    if trail_updates <= 0 and {"symbol", "trail_price"}.issubset(df.columns):
        try:
            tmp = df.copy()
            if "date" in tmp.columns:
                tmp["__d"] = pd.to_datetime(tmp["date"], errors="coerce")
                tmp = tmp.sort_values(["symbol", "__d"])
            else:
                tmp = tmp.sort_values(["symbol"])
            tp = pd.to_numeric(tmp["trail_price"], errors="coerce")
            diff = tp.groupby(tmp["symbol"]).diff().abs()
            trail_updates = int(diff.fillna(0.0).gt(1e-12).sum())
        except Exception:
            trail_updates = 0
    out["atr_trail_update_count"] = int(max(trail_updates, 0))
    return out


def _extract_reason_code_counts(group_dir: Path) -> dict[str, int]:
    path = group_dir / "reason_code_counts.csv"
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path)
    except Exception:
        return {}
    if df.empty:
        return {}
    code_col = "code" if "code" in df.columns else ("reason_code" if "reason_code" in df.columns else None)
    count_col = "count" if "count" in df.columns else ("orders" if "orders" in df.columns else None)
    if code_col is None or count_col is None:
        return {}
    code = df[code_col].astype(str).str.upper()
    cnt = pd.to_numeric(df[count_col], errors="coerce").fillna(0).astype(int)
    out = {
        "atr_stop_exit_count": int(cnt[code.eq("ATR_STOP_LOSS")].sum()),
        "atr_trail_exit_count": int(cnt[code.eq("ATR_TRAIL_EXIT")].sum()),
        "reversal_exit_count": int(cnt[code.isin(["SIGNAL_REVERSE", "SMA_CROSS_DOWN"])].sum()),
        "time_exit_count": int(cnt[code.eq("TIME_EXIT")].sum()),
    }
    return out


def _extract_trigger_counters(row: dict[str, Any], group_dir: Path) -> tuple[dict[str, Any], list[str]]:
    out = dict(row or {})
    missing: list[str] = []
    summary = _load_json_file(group_dir / "report_summary.json")
    report = _load_json_file(group_dir / "report.json")
    run_meta = _load_json_file(group_dir / "run_meta.json")
    debug_atr = _extract_debug_atr_counters(group_dir)
    reason_counts = _extract_reason_code_counts(group_dir)

    float_sources = [
        out,
        summary.get("metrics"),
        summary.get("kpis"),
        summary.get("audit_rules"),
        summary,
        report.get("metrics"),
        report.get("summary"),
        report.get("audit_rules"),
        report,
        run_meta.get("counters"),
        run_meta,
    ]
    int_sources = [
        out,
        summary.get("execution_stats"),
        summary.get("metrics"),
        summary.get("kpis"),
        summary.get("audit_rules"),
        summary,
        report.get("metrics"),
        report.get("summary"),
        report.get("audit_rules"),
        report,
        run_meta.get("counters"),
        run_meta,
    ]

    float_field_paths: dict[str, list[tuple[str, ...]]] = {
        "gate_on_rate": [("gate_on_rate",), ("mf_gate_on_rate",)],
        "mf_rank_applied_rate": [("mf_rank_applied_rate",)],
    }
    int_field_paths: dict[str, list[tuple[str, ...]]] = {
        "trend_slope_block_count": [("trend_slope_block_count",), ("blocked_by_trend_count",)],
        "atr_stop_exit_count": [
            ("atr_stop_exit_count",),
            ("atr_stop_loss_count",),
            ("exit_reason_breakdown", "ATR_STOP_LOSS"),
        ],
        "atr_trail_exit_count": [
            ("atr_trail_exit_count",),
            ("exit_reason_breakdown", "ATR_TRAIL_EXIT"),
        ],
        "atr_trail_update_count": [("atr_trail_update_count",)],
        "reversal_exit_count": [
            ("reversal_exit_count",),
            ("exit_reason_breakdown", "SIGNAL_REVERSE"),
            ("exit_reason_breakdown", "SMA_CROSS_DOWN"),
        ],
        "time_exit_count": [
            ("time_exit_count",),
            ("exit_reason_breakdown", "TIME_EXIT"),
        ],
    }

    for field, paths in float_field_paths.items():
        val = _coerce_number(out.get(field))
        if val is None:
            for src in float_sources:
                val = _pick_from_paths(src, paths, integer=False)
                if val is not None:
                    break
        out[field] = None if val is None else float(val)

    for field, paths in int_field_paths.items():
        val = _coerce_number(out.get(field), integer=True)
        if val is None:
            for src in int_sources:
                val = _pick_from_paths(src, paths, integer=True)
                if val is not None:
                    break
        # Keep the strongest evidence across sources; avoid stale zero overriding debug-derived counts.
        if field in debug_atr:
            dbg = int(debug_atr.get(field) or 0)
            if val is None or dbg > int(val):
                val = dbg
        if field in reason_counts:
            rc = int(reason_counts.get(field) or 0)
            if val is None or rc > int(val):
                val = rc
        out[field] = None if val is None else int(val)

    if out.get("atr_stop_exit_count") is None and out.get("atr_trail_exit_count") is None:
        reasons = summary.get("reasons")
        if isinstance(reasons, list):
            stop_n = 0
            trail_n = 0
            for item in reasons:
                if not isinstance(item, dict):
                    continue
                rc = str(item.get("reason_code") or "").strip().upper()
                c = int(_coerce_number(item.get("count") if item.get("count") is not None else item.get("orders"), integer=True) or 0)
                if rc == "ATR_STOP_LOSS":
                    stop_n += c
                if rc == "ATR_TRAIL_EXIT":
                    trail_n += c
            if stop_n > 0:
                out["atr_stop_exit_count"] = stop_n
            if trail_n > 0:
                out["atr_trail_exit_count"] = trail_n

    # Derive constraint counters from candidate_diag_reason_counts
    diag = {}
    for src in [run_meta.get("counters"), run_meta, summary.get("metrics"), summary, report.get("metrics"), report]:
        if isinstance(src, dict):
            cdr = src.get("candidate_diag_reason_counts")
            if isinstance(cdr, dict) and cdr:
                diag = cdr
                break
    if out.get("cash_skip_count") is None:
        out["cash_skip_count"] = int(diag.get("SKIP_CASH_INSUFFICIENT", 0) or 0)
    if out.get("lot_skip_count") is None:
        out["lot_skip_count"] = int(diag.get("SKIP_LOT_TOO_SMALL", 0) or 0)
    if out.get("cap_hit_single") is None:
        out["cap_hit_single"] = int(diag.get("BLOCK_SINGLE_CAP", 0) or 0)
    if out.get("cap_hit_industry") is None:
        out["cap_hit_industry"] = int(diag.get("BLOCK_INDUSTRY_CAP", 0) or 0)

    # Compute slots_left = max_positions - avg_positions
    if out.get("slots_left") is None:
        avg_pos = _coerce_number(out.get("avg_positions"), integer=False)
        if avg_pos is None:
            for src in float_sources:
                avg_pos = _pick_from_paths(src, [("avg_positions",)], integer=False)
                if avg_pos is not None:
                    break
        max_pos = _coerce_number(out.get("max_positions"), integer=True)
        if max_pos is None:
            for src in int_sources:
                max_pos = _pick_from_paths(src, [("max_positions",)], integer=True)
                if max_pos is not None:
                    break
        if avg_pos is not None and max_pos is not None:
            out["slots_left"] = round(float(max_pos) - float(avg_pos), 1)
        out["avg_positions"] = float(avg_pos) if avg_pos is not None else None

    # Also extract reversal / time exit from reason_code_counts.csv
    if out.get("reversal_exit_count") is None or out.get("time_exit_count") is None:
        rc_path = group_dir / "reason_code_counts.csv"
        if rc_path.exists():
            try:
                rc_df = pd.read_csv(rc_path)
                code_col = "code" if "code" in rc_df.columns else ("reason_code" if "reason_code" in rc_df.columns else None)
                cnt_col = "count" if "count" in rc_df.columns else ("orders" if "orders" in rc_df.columns else None)
                if code_col and cnt_col:
                    codes = rc_df[code_col].astype(str).str.upper()
                    counts = pd.to_numeric(rc_df[cnt_col], errors="coerce").fillna(0).astype(int)
                    if out.get("reversal_exit_count") is None:
                        out["reversal_exit_count"] = int(counts[codes.isin(["SIGNAL_REVERSE", "SMA_CROSS_DOWN"])].sum())
                    if out.get("time_exit_count") is None:
                        out["time_exit_count"] = int(counts[codes.eq("TIME_EXIT")].sum())
            except Exception:
                pass

    if out.get("atr_stop_exit_count") is None and out.get("atr_trail_exit_count") is None and out.get("atr_trail_update_count") is None:
        missing.append("missing_atr_trigger_counters")
    if out.get("gate_on_rate") is None:
        missing.append("missing_gate_on_rate_source")
    if out.get("mf_rank_applied_rate") is None:
        missing.append("missing_mf_rank_applied_rate_source")
    if out.get("trend_slope_block_count") is None:
        missing.append("missing_trend_slope_block_count_source")
    if out.get("atr_trail_update_count") is None:
        missing.append("missing_atr_trail_update_counter_source")
    out["missing_fields"] = sorted(set(list(out.get("missing_fields") or []) + missing))
    return out, missing


def _jobs_root() -> Path:
    root = _results_root() / "jobs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _job_file(job_id: str) -> Path:
    return _jobs_root() / f"{job_id}.json"


def _persist_job(job: dict[str, Any]) -> None:
    try:
        _job_file(str(job.get("job_id"))).write_text(
            json.dumps(_sanitize_for_json(job), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def _load_job_from_disk(job_id: str) -> dict[str, Any] | None:
    p = _job_file(job_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


class BacktestV2RunRequest(BaseModel):
    start_date: str = "2021-01-01"
    end_date: str = "2026-02-01"
    symbols: list[str] = Field(default_factory=lambda: ["600000.SH", "000001.SZ", "600519.SH"])
    benchmark: str = "000300.SH"
    compare_symbol: str = "000001.SH"
    initial_capital: float = 100000.0
    fast: int = 5
    slow: int = 20
    order_size: int = 1000
    execution_profile: str = "basic"
    sizing_mode: str = "fixed_qty"
    order_value: float = 10000.0
    reserve_cash_ratio: float = 0.02
    allow_pyramiding: bool = False
    force_run: bool = False
    validation_request_id: str | None = None
    validation_passed: bool | None = None
    validation_warnings: list[str] | None = None


class BacktestV2ExperimentRequest(BaseModel):
    preset: str = "G1-G4"
    symbols: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None
    benchmark: str | None = None
    compare_symbol: str | None = None
    initial_capital: float | None = None
    max_positions: int | None = None
    base_order_value: float | None = None
    univote_lot_mode: str | None = None
    lot_size: int | None = None
    universe_limit: int | None = None
    fast_mode: bool | None = None
    config_path: str | None = None
    config_id: str | None = None
    workbench_mode: str | None = None
    workbench_config: dict[str, Any] | None = None
    universe_mode: str = "CUSTOM"
    industries: list[str] = []
    price_adj: str = "hfq"


class BacktestV2ConfigSaveRequest(BaseModel):
    config_json: dict[str, Any]
    name: str | None = None
    tags: list[str] | None = None


class BacktestV2ExecutionPreviewRequest(BaseModel):
    config_id: str | None = None
    config_json: dict[str, Any] | None = None
    exp_id: str | None = None
    results_dir: str | None = None
    as_of_date: str | None = None
    top_n: int = 10


class BacktestV2ArtifactReadRequest(BaseModel):
    results_dir: str
    rel_path: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _bt_root() -> Path:
    env_root = os.environ.get("BACKTEST_V2_ROOT", "").strip()
    if env_root:
        return Path(env_root).resolve()
    return (_repo_root() / "backend" / "core").resolve()


def _results_root() -> Path:
    raw = os.environ.get("RESULTS_ROOT", "outputs").strip() or "outputs"
    p = Path(raw)
    if not p.is_absolute():
        p = (_repo_root() / p).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _configs_root() -> Path:
    root = _results_root() / "configs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _execution_root() -> Path:
    root = _results_root() / "execution"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _hash_json(obj: Any) -> str:
    payload = json.dumps(sanitize_json(obj), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _build_universe_stats(validate_result: dict[str, Any], symbols: list[str]) -> dict[str, Any]:
    checks = validate_result.get("checks") if isinstance(validate_result.get("checks"), dict) else {}
    meta = validate_result.get("meta") if isinstance(validate_result.get("meta"), dict) else {}
    coverage = checks.get("coverage") if isinstance(checks.get("coverage"), dict) else {}
    by_symbol = coverage.get("by_symbol") if isinstance(coverage.get("by_symbol"), dict) else {}

    total_symbols = int(len(symbols))
    coverage_nonzero = int(sum(1 for _, v in by_symbol.items() if int(_coerce_number(v, integer=True) or 0) > 0))
    tradable_symbols = int(_coerce_number(validate_result.get("tradable_symbols"), integer=True) or coverage_nonzero or total_symbols)
    after_filters_symbols = int(_coerce_number(validate_result.get("after_filters_symbols"), integer=True) or tradable_symbols)
    universe_size = int(_coerce_number(validate_result.get("universe_size"), integer=True) or after_filters_symbols)

    trading_days = int(
        _coerce_number(validate_result.get("trading_days"), integer=True)
        or _coerce_number(meta.get("trading_days"), integer=True)
        or 0
    )
    missing_rate = _coerce_number(validate_result.get("missing_rate"))
    if missing_rate is None:
        sanity = checks.get("sanity") if isinstance(checks.get("sanity"), dict) else {}
        null_count = float(_coerce_number(sanity.get("null_count")) or 0.0)
        rows = float(_coerce_number(coverage.get("rows")) or 0.0)
        missing_rate = (null_count / rows) if rows > 0 else 0.0

    filter_breakdown = validate_result.get("filter_breakdown")
    if not isinstance(filter_breakdown, list):
        filter_breakdown = [
            {"name": "all_symbols", "before": total_symbols, "after": total_symbols},
            {"name": "tradable", "before": total_symbols, "after": tradable_symbols},
            {"name": "liquidity_filters", "before": tradable_symbols, "after": after_filters_symbols},
            {"name": "final_universe", "before": after_filters_symbols, "after": universe_size},
        ]

    return sanitize_json(
        {
            "total_symbols": total_symbols,
            "tradable_symbols": tradable_symbols,
            "after_filters_symbols": after_filters_symbols,
            "universe_size": universe_size,
            "trading_days": trading_days,
            "missing_rate": missing_rate if missing_rate is not None else 0.0,
            "data_snapshot_id": validate_result.get("data_snapshot_id"),
            "filter_breakdown": filter_breakdown,
        }
    )


def _list_recent_experiments(limit: int = 20) -> list[Path]:
    root = _results_root() / "experiments"
    if not root.exists():
        return []
    dirs = [p for p in root.iterdir() if p.is_dir()]
    dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return dirs[: max(1, int(limit))]


def _resolve_experiment_dir(exp_id: str | None = None, results_dir: str | None = None) -> Path | None:
    if results_dir:
        p = Path(str(results_dir))
        if not p.is_absolute():
            p = (_repo_root() / p).resolve()
        if p.exists() and p.is_dir():
            return p
    if exp_id:
        p = (_results_root() / "experiments" / str(exp_id)).resolve()
        if p.exists() and p.is_dir():
            return p
    recent = _list_recent_experiments(limit=1)
    return recent[0] if recent else None

def _load_base_config(bt_root: Path) -> dict[str, Any]:
    cfg_path = bt_root / "configs" / "pams_cn_pg.json"
    if not cfg_path.exists():
        raise HTTPException(status_code=500, detail=f"missing config template: {cfg_path}")
    return json.loads(cfg_path.read_text(encoding="utf-8-sig"))


def _build_runtime_config(bt_root: Path, body: BacktestV2RunRequest) -> tuple[Path, str]:
    cfg = _load_base_config(bt_root)
    cfg["universe"]["start"] = body.start_date
    cfg["universe"]["end"] = body.end_date
    cfg["universe"]["symbols"] = body.symbols
    cfg["universe"]["benchmark"] = body.benchmark
    cfg["universe"]["benchmark_compare_symbol"] = body.compare_symbol
    cfg["initial_capital"] = float(body.initial_capital)
    cfg["strategy"]["fast"] = int(body.fast)
    cfg["strategy"]["slow"] = int(body.slow)
    cfg["strategy"]["order_size"] = int(body.order_size)
    cfg.setdefault("execution", {})
    cfg["execution"]["profile"] = str(body.execution_profile)
    cfg["execution"]["allow_pyramiding"] = bool(body.allow_pyramiding)
    cfg.setdefault("sizing", {})
    cfg["sizing"]["mode"] = str(body.sizing_mode)
    cfg["sizing"]["order_value"] = float(body.order_value)
    cfg["sizing"]["reserve_cash_ratio"] = float(body.reserve_cash_ratio)

    run_id = f"run_{uuid.uuid4().hex[:10]}"
    cfg_path = bt_root / "configs" / f".tmp_{run_id}.json"
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg_path, run_id


def _run_backtest_v2(bt_root: Path, cfg_path: Path, run_id: str) -> Path:
    out_dir = _results_root() / run_id
    env = os.environ.copy()
    env["PAMS_PG_HOST"] = env.get("PGHOST", env.get("PAMS_PG_HOST", "pams-postgres"))
    env["PAMS_PG_PORT"] = env.get("PGPORT", env.get("PAMS_PG_PORT", "5432"))
    env["PAMS_PG_DBNAME"] = env.get("PGDATABASE", env.get("PAMS_PG_DBNAME", "pams"))
    env["PAMS_PG_USER"] = env.get("PGUSER", env.get("PAMS_PG_USER", "pams"))
    env["PAMS_PG_PASSWORD"] = env.get("PGPASSWORD", env.get("PAMS_PG_PASSWORD", ""))

    cmd = [
        sys.executable,
        "-m",
        "backtest_v2.cli.main",
        "run",
        "--config",
        str(cfg_path),
        "--out",
        str(out_dir),
    ]
    proc = subprocess.run(cmd, cwd=str(bt_root), env=env, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"backtest_v2 run failed: {proc.stderr.strip() or proc.stdout.strip()}",
        )
    return out_dir


def _read_validation_audit(bt_root: Path, request_id: str) -> dict[str, Any] | None:
    p = _results_root() / request_id / "audit" / "validate_data.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _validation_warnings_to_strings(value: Any) -> list[str]:
    if value is None:
        return []
    out: list[str] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                code = str(item.get("code", "")).strip()
                msg = str(item.get("message", "")).strip()
                out.append(f"{code}: {msg}" if code else (msg or json.dumps(item, ensure_ascii=False)))
            else:
                out.append(str(item))
    return out


def _write_data_validation_section(out_dir: Path, body: BacktestV2RunRequest, bt_root: Path) -> None:
    report_path = out_dir / "report.json"
    if not report_path.exists():
        return
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))

    audit = None
    if body.validation_request_id:
        audit = _read_validation_audit(bt_root, body.validation_request_id)

    warnings = _validation_warnings_to_strings(body.validation_warnings)
    if not warnings and audit:
        warnings = _validation_warnings_to_strings(audit.get("warnings"))

    passed = body.validation_passed
    if passed is None and audit is not None:
        passed = bool(audit.get("pass"))

    report["data_validation"] = {
        "request_id": body.validation_request_id,
        "passed": passed,
        "warnings": warnings,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_path = out_dir / "report_summary.json"
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
            audit = summary.get("audit", {})
            audit["validation"] = {
                "request_id": body.validation_request_id,
                "passed": passed,
                "warnings": warnings,
            }
            summary["audit"] = audit
            summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    conclusions_path = out_dir / "conclusions_10.json"
    if conclusions_path.exists():
        try:
            conclusions = json.loads(conclusions_path.read_text(encoding="utf-8-sig"))
            items = conclusions.get("items", [])
            if isinstance(items, list):
                for item in items:
                    if int(item.get("id", -1)) != 1:
                        continue
                    if passed is False:
                        item["status"] = "FAIL"
                        item["value"] = "passed=false"
                        item["detail"] = f"validation_warnings={len(warnings)}"
                    elif passed is True:
                        item["status"] = "WARN" if len(warnings) > 0 else "PASS"
                        item["value"] = "passed=true"
                        item["detail"] = f"validation_warnings={len(warnings)}"
                    else:
                        item["status"] = "PASS"
                        item["value"] = "not_provided"
                        item["detail"] = "未绑定 validate 结果（passed=null）"
                    break
            conclusions_path.write_text(json.dumps(conclusions, ensure_ascii=False, indent=2), encoding="utf-8")
            txt_path = out_dir / "conclusions_10.txt"
            if txt_path.exists():
                lines = [f"run_id: {conclusions.get('run_id', '')}"]
                for item in items:
                    lines.append(
                        f"{item.get('id')}. [{item.get('status')}] {item.get('title')} | {item.get('value')} | {item.get('detail')}"
                    )
                nxt = conclusions.get("suggested_next_change", {})
                lines.append(f"next: {nxt.get('code', '')} | {nxt.get('reason', '')}")
                txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception:
            pass


def _parse_symbols_from_query(request: Request) -> list[str]:
    vals = request.query_params.getlist("symbols")
    if not vals:
        return []
    if len(vals) == 1:
        return [x.strip() for x in vals[0].split(",") if x.strip()]
    out: list[str] = []
    for v in vals:
        out.extend([x.strip() for x in v.split(",") if x.strip()])
    return out


def _read_result(out_dir: Path) -> dict[str, Any]:
    report_path = out_dir / "report.json"
    summary_path = out_dir / "report_summary.json"
    trades_path = out_dir / "trades.csv"
    orders_path = out_dir / "orders.csv"
    equity_path = out_dir / "equity_curve.csv"
    warnings_path = out_dir / "warnings.json"
    conclusions_path = out_dir / "conclusions_10.json"
    benchmark_curve_path = out_dir / "benchmark_curve.csv"
    trade_pnl_path = out_dir / "trade_pnl.csv"
    signals_path = out_dir / "signals.csv"
    if not report_path.exists():
        raise HTTPException(status_code=500, detail=f"missing report file: {report_path}")

    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    report_summary: dict[str, Any] | None = None
    if summary_path.exists():
        try:
            report_summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
        except Exception:
            report_summary = None

    conclusions_10: dict[str, Any] | None = None
    if conclusions_path.exists():
        try:
            conclusions_10 = json.loads(conclusions_path.read_text(encoding="utf-8-sig"))
        except Exception:
            conclusions_10 = None

    benchmark_curve_preview: list[dict[str, Any]] = []
    if benchmark_curve_path.exists():
        try:
            cdf = pd.read_csv(benchmark_curve_path).head(2000)
            benchmark_curve_preview = cdf.to_dict(orient="records")
        except EmptyDataError:
            benchmark_curve_preview = []

    trade_concentration = {}
    if report_summary and isinstance(report_summary.get("trade_concentration"), dict):
        trade_concentration = report_summary.get("trade_concentration") or {}
    trades_preview: list[dict[str, Any]] = []
    if trades_path.exists():
        try:
            tdf = pd.read_csv(trades_path).head(200)
            trades_preview = tdf.to_dict(orient="records")
        except EmptyDataError:
            trades_preview = []

    return {
        "report": report,
        "summary": report.get("summary", {}),
        "report_summary": report_summary,
        "conclusions_10": conclusions_10 or (report_summary or {}).get("conclusions_10"),
        "chart": (report_summary or {}).get("chart", {}),
        "trade_concentration": trade_concentration,
        "benchmark_curve_preview": benchmark_curve_preview,
        "cost_breakdown": report.get("cost_breakdown", {}),
        "audit_rules": report.get("audit_rules", {}),
        "trades_preview": trades_preview,
        "files": {
            "report": str(report_path),
            "report_summary": str(summary_path),
            "trades": str(trades_path),
            "orders": str(orders_path),
            "equity": str(equity_path),
            "warnings": str(warnings_path),
            "conclusions_10": str(conclusions_path),
            "benchmark_curve": str(benchmark_curve_path),
            "trade_pnl": str(trade_pnl_path),
            "signals": str(signals_path),
        },
    }


def _sanitize_for_json(value: Any) -> Any:
    return sanitize_json(value)


def _create_job(job_type: str, eta_seconds: int = 300) -> str:
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    now = time.time()
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "job_type": job_type,
            "status": "queued",
            "message": "绛夊緟鎵ц",
            "progress_pct": 0,
            "created_at_ts": now,
            "updated_at_ts": now,
            "started_at_ts": None,
            "finished_at_ts": None,
            "eta_seconds": int(max(30, eta_seconds)),
            "result": None,
            "error": None,
        }
        _persist_job(_JOBS[job_id])
    return job_id


def _update_job(job_id: str, **kwargs: Any) -> None:
    now = time.time()
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job.update(kwargs)
        job["updated_at_ts"] = now
        if kwargs.get("status") == "running" and job.get("started_at_ts") is None:
            job["started_at_ts"] = now
        if kwargs.get("status") in {"success", "failed"}:
            job["finished_at_ts"] = now
        _persist_job(job)


def _is_cancel_requested(job_id: str) -> bool:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is not None:
            return bool(job.get("cancel_requested"))
    disk_job = _load_job_from_disk(job_id)
    return bool(disk_job and disk_job.get("cancel_requested"))


def _mark_job_canceled(job_id: str, message: str = "任务已取消") -> dict[str, Any] | None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            job = _load_job_from_disk(job_id)
            if job is None:
                return None
            _JOBS[job_id] = job
        status = str(job.get("status") or "")
        if status in {"success", "failed", "canceled"}:
            return job
        now = time.time()
        job["cancel_requested"] = True
        job["status"] = "canceled"
        job["message"] = message
        job["finished_at_ts"] = now
        job["updated_at_ts"] = now
        _persist_job(job)
        return job


def _job_payload(job: dict[str, Any]) -> dict[str, Any]:
    status = str(job.get("status") or "queued")
    progress = int(job.get("progress_pct") or 0)
    if status == "success":
        progress = 100
    if status == "canceled":
        progress = min(progress, 99)
    return {
        "job_id": job.get("job_id"),
        "job_type": job.get("job_type"),
        "status": status,
        "message": job.get("message"),
        "progress_pct": progress,
        "created_at": datetime.fromtimestamp(float(job.get("created_at_ts") or time.time())).isoformat(),
        "updated_at": datetime.fromtimestamp(float(job.get("updated_at_ts") or time.time())).isoformat(),
        "result": job.get("result"),
        "error": job.get("error"),
    }


@router.get("/api/backtest_v2/industries")
def get_industries():
    """返回 pit_industry_history 中所有不重复的 L1 行业名列表。"""
    try:
        import psycopg
        conn = psycopg.connect(
            host=os.environ.get("PGHOST", os.environ.get("PAMS_PG_HOST", "pams-postgres")),
            port=int(os.environ.get("PGPORT", os.environ.get("PAMS_PG_PORT", "5432"))),
            dbname=os.environ.get("PGDATABASE", os.environ.get("PAMS_PG_DBNAME", "pams")),
            user=os.environ.get("PGUSER", os.environ.get("PAMS_PG_USER", "pams")),
            password=os.environ.get("PGPASSWORD", os.environ.get("PAMS_PG_PASSWORD", "")),
            autocommit=True,
        )
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT industry_l1 FROM public.pit_industry_history ORDER BY industry_l1")
            industries = [r[0] for r in cur.fetchall()]
        conn.close()
    except Exception:
        industries = []
    return {"industries": industries}


@router.get("/api/backtest_v2/results/{run_id}")
def get_backtest_v2_result(run_id: str):
    out_dir = _results_root() / run_id
    if not out_dir.exists():
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    payload = _sanitize_for_json(_read_result(out_dir))
    payload["run_id"] = run_id
    return payload


@router.get("/api/backtest_v2/validate_data")
def validate_backtest_v2_data(
    request: Request,
    start: str = Query(...),
    end: str = Query(...),
    benchmark: str = Query("000300.SH"),
    audit_dump: bool = Query(True),
    strict_suspended: bool = Query(False),
    allow_cn_index_fallback: bool = Query(False),
):
    symbols = _parse_symbols_from_query(request)
    if not symbols:
        raise HTTPException(status_code=400, detail="symbols is required")
    try:
        start_d = date.fromisoformat(start)
        end_d = date.fromisoformat(end)
    except Exception:
        raise HTTPException(status_code=400, detail="start/end must be YYYY-MM-DD")
    if start_d > end_d:
        raise HTTPException(status_code=400, detail="start must be <= end")

    bt_root = _bt_root()
    if not bt_root.exists():
        raise HTTPException(status_code=500, detail=f"backtest_V2 root not found: {bt_root}")

    from backend.core.data.validate_pg import PGConnConfig, validate_data  # type: ignore

    cfg = PGConnConfig(
        host=os.environ.get("PGHOST", os.environ.get("PAMS_PG_HOST", "pams-postgres")),
        port=int(os.environ.get("PGPORT", os.environ.get("PAMS_PG_PORT", "5432"))),
        dbname=os.environ.get("PGDATABASE", os.environ.get("PAMS_PG_DBNAME", "pams")),
        user=os.environ.get("PGUSER", os.environ.get("PAMS_PG_USER", "pams")),
        password=os.environ.get("PGPASSWORD", os.environ.get("PAMS_PG_PASSWORD", "")),
        statement_timeout_ms=60000,
    )
    result = validate_data(
        pg=cfg,
        symbols=symbols,
        start=start_d,
        end=end_d,
        benchmark=benchmark,
        audit_dump=audit_dump,
        strict_suspended=strict_suspended,
        allow_cn_index_fallback=allow_cn_index_fallback,
        results_root=_results_root(),
    )
    if isinstance(result, dict):
        result.setdefault("request_id", f"val_{uuid.uuid4().hex[:10]}")
        result.setdefault("results_root", str(_results_root().resolve()))
        result["universe_stats"] = _build_universe_stats(result, symbols)
    return _sanitize_for_json(result)


@router.post("/api/backtest_v2/experiment/run")
def run_backtest_v2_experiment(body: BacktestV2ExperimentRequest):
    return _run_backtest_v2_experiment_sync(body)


def _run_backtest_v2_experiment_sync(
    body: BacktestV2ExperimentRequest,
    progress_hook: Callable[[int, str], None] | None = None,
) -> dict[str, Any]:
    bt_root = _bt_root()
    if not bt_root.exists():
        raise HTTPException(status_code=500, detail=f"backtest_V2 root not found: {bt_root}")

    try:
        from backend.core.tools.experiment_runner import run_experiment  # type: ignore
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"failed to import experiment tools: {exc}")

    cfg_rel = body.config_path.strip() if (body.config_path or "").strip() else "configs/pams_cn_pg.json"
    cfg_path = (bt_root / cfg_rel).resolve()
    if not cfg_path.exists():
        cfg_path_alt = (bt_root.parent / cfg_rel).resolve()
        if cfg_path_alt.exists():
            cfg_path = cfg_path_alt
        else:
            raise HTTPException(status_code=400, detail=f"config not found: {cfg_path}")

    try:
        base_cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid config json: {cfg_path} ({exc})")

    overrides: dict[str, Any] = {}
    if body.symbols:
        overrides["symbols"] = list(body.symbols)
    if body.start_date:
        overrides["start_date"] = body.start_date
    if body.end_date:
        overrides["end_date"] = body.end_date
    if body.benchmark:
        overrides["benchmark"] = body.benchmark
    if body.compare_symbol:
        overrides["compare_symbol"] = body.compare_symbol
    if body.initial_capital is not None:
        overrides["initial_capital"] = float(body.initial_capital)
    if body.max_positions is not None:
        overrides["max_positions"] = int(body.max_positions)
    if body.base_order_value is not None:
        overrides["base_order_value"] = float(body.base_order_value)
    if body.lot_size is not None:
        overrides["lot_size"] = int(body.lot_size)
    if body.universe_limit is not None:
        overrides["universe_limit"] = int(body.universe_limit)
    if body.fast_mode is not None:
        overrides["fast_mode"] = bool(body.fast_mode)
    if body.config_id:
        overrides["config_id"] = str(body.config_id)
    if body.workbench_mode:
        overrides["workbench_mode"] = str(body.workbench_mode)
    if isinstance(body.workbench_config, dict):
        overrides["workbench_config"] = sanitize_json(dict(body.workbench_config))
    if body.universe_mode:
        overrides["universe_mode"] = str(body.universe_mode)
    if body.industries:
        overrides["industries"] = list(body.industries)
    if body.price_adj:
        overrides["price_adj"] = str(body.price_adj)

    env_backup = {
        "PAMS_PG_HOST": os.environ.get("PAMS_PG_HOST"),
        "PAMS_PG_PORT": os.environ.get("PAMS_PG_PORT"),
        "PAMS_PG_DBNAME": os.environ.get("PAMS_PG_DBNAME"),
        "PAMS_PG_USER": os.environ.get("PAMS_PG_USER"),
        "PAMS_PG_PASSWORD": os.environ.get("PAMS_PG_PASSWORD"),
    }
    os.environ["PAMS_PG_HOST"] = os.environ.get("PGHOST", env_backup["PAMS_PG_HOST"] or "pams-postgres")
    os.environ["PAMS_PG_PORT"] = os.environ.get("PGPORT", env_backup["PAMS_PG_PORT"] or "5432")
    os.environ["PAMS_PG_DBNAME"] = os.environ.get("PGDATABASE", env_backup["PAMS_PG_DBNAME"] or "pams")
    os.environ["PAMS_PG_USER"] = os.environ.get("PGUSER", env_backup["PAMS_PG_USER"] or "pams")
    os.environ["PAMS_PG_PASSWORD"] = os.environ.get("PGPASSWORD", env_backup["PAMS_PG_PASSWORD"] or "")

    requested_preset = str(body.preset or "").strip()
    try:
        result = run_experiment(str(cfg_path), requested_preset or "single", overrides, progress_hook=progress_hook)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"experiment run failed: {exc}")
    finally:
        for k, v in env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    try:
        _attach_run_profile_summary(result)
    except Exception:
        pass

    try:
        result = stabilize_experiment_result(
            bt_root=bt_root,
            result=result if isinstance(result, dict) else {},
            base_cfg=base_cfg,
            overrides=overrides,
            run_profile_summary=result.get("run_profile_summary") if isinstance(result, dict) else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f"artifact stabilization failed: {exc}")

    result.setdefault("exp_id", "")
    result.setdefault("results_dir", "")
    result.setdefault("status", "OK")
    result["requested_preset"] = requested_preset
    return sanitize_json(result)

def _attach_run_profile_summary(result: dict[str, Any]) -> None:
    if not isinstance(result, dict):
        return
    results_dir_raw = str(result.get("results_dir") or "").strip()
    if not results_dir_raw:
        return
    rp = Path(results_dir_raw) / "run_profile.json"
    if not rp.exists():
        return
    try:
        obj = json.loads(rp.read_text(encoding="utf-8-sig"))
    except Exception:
        return
    stages = obj.get("stage_seconds") if isinstance(obj.get("stage_seconds"), dict) else {}
    summary: dict[str, Any] = {
        "run_profile_path": str(rp),
        "total_wall_seconds": float(obj.get("total_wall_seconds", 0.0) or 0.0),
        "stage_seconds": {str(k): float(v or 0.0) for k, v in stages.items()},
        "symbols_count": int(obj.get("symbols_count", 0) or 0),
        "trading_days": int(obj.get("trading_days", 0) or 0),
        "variant_count": int(obj.get("variant_count", 0) or 0),
        "row_count": int(obj.get("row_count", 0) or 0),
        "rows_per_second": float(obj.get("rows_per_second", 0.0) or 0.0),
        "bottleneck_stage": str(obj.get("bottleneck_stage") or ""),
        "bottleneck_label": str(obj.get("bottleneck_label") or "BOTTLENECK_UNKNOWN"),
    }
    perf = obj.get("perf") if isinstance(obj.get("perf"), dict) else {}
    if perf:
        summary["perf"] = {
            "db_load_seconds": float(perf.get("db_load_seconds", 0.0) or 0.0),
            "precompute_seconds": float(perf.get("precompute_seconds", 0.0) or 0.0),
            "simulation_seconds": float(perf.get("simulation_seconds", 0.0) or 0.0),
            "io_write_seconds": float(perf.get("io_write_seconds", 0.0) or 0.0),
            "db_queries": int(perf.get("db_queries", 0) or 0),
            "cache_hit_rate": float(perf.get("cache_hit_rate", 0.0) or 0.0),
        }
    tips: list[str] = []
    b = summary["bottleneck_label"]
    if b == "BOTTLENECK_DATA_LOAD":
        tips.append("数据加载是主要瓶颈：建议减少 universe_limit 或缩短回测区间。")
    elif b == "BOTTLENECK_SIMULATION":
        tips.append("仿真执行是主要瓶颈：建议启用 fast_mode 并关闭非必要明细写盘。")
    elif b == "BOTTLENECK_PRECOMPUTE":
        tips.append("预计算是主要瓶颈：建议缩短 lookback 或减少因子维度。")
    elif b == "BOTTLENECK_IO":
        tips.append("写盘是主要瓶颈：建议关闭 trades/candidates 明细输出。")
    if float(summary.get("rows_per_second", 0.0) or 0.0) <= 0.0:
        tips.append("当前 rows_per_second=0，建议检查实验是否无有效分组输出。")
    summary["optimization_tips"] = tips
    result["run_profile_summary"] = summary


def _run_backtest_v2_experiment_job(job_id: str, body: BacktestV2ExperimentRequest) -> None:
    try:
        preset = str(body.preset or "G1-G4")
        if _is_cancel_requested(job_id):
            _update_job(job_id, status="canceled", message="实验已取消")
            return
        _update_job(job_id, status="running", progress_pct=3, message=f"开始实验：{preset}")

        def _progress_cb(pct: int, msg: str) -> None:
            if _is_cancel_requested(job_id):
                return
            _update_job(job_id, status="running", progress_pct=int(max(0, min(99, pct))), message=str(msg))

        payload = _run_backtest_v2_experiment_sync(body, progress_hook=_progress_cb)
        if _is_cancel_requested(job_id):
            _update_job(job_id, status="canceled", message="实验已取消")
            return
        _update_job(job_id, status="running", progress_pct=95, message="汇总矩阵与报告")
        if _is_cancel_requested(job_id):
            _update_job(job_id, status="canceled", message="实验已取消")
            return
        _update_job(job_id, status="success", progress_pct=100, message="实验完成", result=payload)
    except Exception as exc:
        msg = str(exc)
        if isinstance(exc, HTTPException):
            msg = str(exc.detail)
        if _is_cancel_requested(job_id):
            _update_job(job_id, status="canceled", message="实验已取消")
            return
        _update_job(job_id, status="failed", message="实验失败", error=msg)


@router.post("/api/backtest_v2/experiment/run_async")
def run_backtest_v2_experiment_async(body: BacktestV2ExperimentRequest):
    preset_key = str(body.preset or "").strip().upper()
    eta = 480
    if preset_key in {"G1-G4", "REGIME_BUFFER_2X2", "ATR_RISK_2X2", "ATR_PORTFOLIO_VALIDATE_V1", "PORTFOLIO_FILL_VALIDATE_V1", "TREND_FILTER_VALIDATE_V1", "TREND_TIER_VALIDATE_V1", "TREND_ACCEL_BRAKE_VALIDATE_V1", "TREND_BRAKE_CONFIRM_VALIDATE_V1", "STRENGTH_RANK_VALIDATE_V1", "FULL_RANGE_VALIDATE_V1", "CANDIDATE_DIAG_VALIDATE_V1", "SLOT_DEBUG_VALIDATE_V1", "MAX_POSITION_EXPAND_VALIDATE_V1", "STRONG_ONLY_VALIDATE_V1", "MULTIFACTOR_RANKING_VALIDATE_V1", "MULTIFACTOR_RANKING_WALKFORWARD_V1", "MF_RANK_REGIME_GATE_VALIDATE_V1", "MULTIFACTOR_BALANCED_V1", "MULTIFACTOR_FUSION_COMPARE_V1", "MULTIFACTOR_INCREMENTAL_V1", "MULTIFACTOR_INCREMENTAL_V1_6_1A", "EXPERIMENT_6_1A", "6.1A", "MULTIFACTOR_INCREMENTAL_V1_6_1B", "EXPERIMENT_6_1B", "6.1B", "MULTIFACTOR_INCREMENTAL_V1_6_1_LIMIT", "MULTIFACTOR_INCREMENTAL_V1_6_4", "EXPERIMENT_6_4", "6.4", "EXPERIMENT_6_1_LIMIT", "6.1L"}:
        eta = 240
    elif preset_key in {"STRENGTH_RANK_VALIDATE_V2", "STRENGTH_RANK_VALIDATE_V2A", "STRENGTH_RANK_VALIDATE_V2B", "ENGINE_PERF_COMPARE_V1", "ENGINE_PERF_COMPARE_V2"}:
        eta = 180 if bool(body.fast_mode) else 360
    elif preset_key in {"ATR_PARAM_SCAN_V1"}:
        eta = 1200
    elif preset_key in {"ATR_PARAM_VALIDATE_UNIVOTE", "ATR_PARAM_VALIDATE_UNIVOTE_V2"}:
        eta = 900
    job_id = _create_job("experiment", eta_seconds=eta)
    th = threading.Thread(target=_run_backtest_v2_experiment_job, args=(job_id, body), daemon=True)
    th.start()
    return {"job_id": job_id, "status": "queued"}


@router.get("/api/backtest_v2/jobs/{job_id}")
def get_backtest_v2_job(job_id: str):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if not job:
        disk_job = _load_job_from_disk(job_id)
        if not disk_job:
            raise HTTPException(status_code=404, detail=f"job not found: {job_id}")
        payload = _job_payload(dict(disk_job))
    else:
        payload = _job_payload(dict(job))
    return _sanitize_for_json(payload)


@router.post("/api/backtest_v2/jobs/{job_id}/cancel")
def cancel_backtest_v2_job(job_id: str):
    job = _mark_job_canceled(job_id, message="用户取消")
    if not job:
        raise HTTPException(status_code=404, detail=f"job not found: {job_id}")
    return _sanitize_for_json(_job_payload(dict(job)))


@router.get("/api/backtest_v2/series/benchmark")
def get_benchmark_series(
    symbol: str = Query(...),
    start: str = Query(...),
    end: str = Query(...),
):
    try:
        start_d = date.fromisoformat(start)
        end_d = date.fromisoformat(end)
    except Exception:
        raise HTTPException(status_code=422, detail="start/end must be YYYY-MM-DD")

    from backend.core.config.loader import load_config
    from backend.core.data.pg_provider import PostgresDataProvider
    from backend.core.data.errors import DatabaseConnectionError

    bt_root = _bt_root()
    cfg_path = bt_root / "configs" / "pams_cn_pg.json"
    if not cfg_path.exists():
        cfg_path = bt_root.parent / "configs" / "pams_cn_pg.json"
        if not cfg_path.exists():
            raise HTTPException(status_code=500, detail=f"config not found: {cfg_path}")
    cfg_obj, _ = load_config(str(cfg_path))

    provider = PostgresDataProvider(
        db=cfg_obj.db,
        runtime=cfg_obj.db_runtime,
        data_source=cfg_obj.data_source,
        schema_mapping=cfg_obj.schema_mapping,
        rules_path=cfg_path.parent / "instrument_rules_cn.csv",
    )

    try:
        df = provider.load_benchmark_daily(symbol, start_d, end_d)
    except DatabaseConnectionError:
        raise HTTPException(status_code=503, detail="database connection failed")
    except (ValueError, Exception) as exc:
        if "not found" in str(exc) or "empty" in str(exc):
            return _sanitize_for_json({"points": [], "source": "empty"})
        raise HTTPException(status_code=500, detail=str(exc))

    if df.empty or "close" not in df.columns:
        return _sanitize_for_json({"points": [], "source": "empty"})

    df = df.sort_values("date").reset_index(drop=True)
    first_close = df["close"].iloc[0]
    if first_close == 0 or pd.isna(first_close):
        return _sanitize_for_json({"points": [], "source": "empty"})

    # 归一化 OHLC：所有价格字段 ÷ 第一天 close，供前端蜡烛图渲染
    fc = float(first_close)
    has_ohlc = all(c in df.columns for c in ("open", "high", "low"))
    points = []
    for _, row in df.iterrows():
        p = {
            "date": str(row["date"])[:10],
            "nav": round(float(row["close"]) / fc, 6),
            "close": round(float(row["close"]) / fc, 6),
        }
        if has_ohlc:
            p["open"] = round(float(row["open"]) / fc, 6)
            p["high"] = round(float(row["high"]) / fc, 6)
            p["low"] = round(float(row["low"]) / fc, 6)
        else:
            p["open"] = p["close"]
            p["high"] = p["close"]
            p["low"] = p["close"]
        points.append(p)
    return _sanitize_for_json({"points": points, "source": "api"})


@router.post("/api/backtest_v2/stock_names")
def get_stock_names(body: dict):
    """批量查询股票中文名称，入参 {"symbols": ["sh600067", "sz000001", ...]}"""
    symbols = body.get("symbols") or []
    if not symbols:
        return {"names": {}}
    from backend.core.config.loader import load_config
    bt_root = _bt_root()
    cfg_path = bt_root / "configs" / "pams_cn_pg.json"
    if not cfg_path.exists():
        cfg_path = bt_root.parent / "configs" / "pams_cn_pg.json"
    if not cfg_path.exists():
        return {"names": {}}
    cfg_obj, _ = load_config(str(cfg_path))
    try:
        import os
        import psycopg
        db_password = cfg_obj.db.password or os.environ.get("PGPASSWORD", "") or os.environ.get("POSTGRES_PASSWORD", "")
        conn = psycopg.connect(
            host=cfg_obj.db.host,
            port=cfg_obj.db.port,
            dbname=cfg_obj.db.dbname,
            user=cfg_obj.db.user,
            password=db_password,
        )
        cur = conn.cursor()
        cur.execute(
            "SELECT symbol, name FROM pit_security_master WHERE symbol = ANY(%s) AND name IS NOT NULL AND name != ''",
            (list(symbols),),
        )
        names = {row[0]: row[1] for row in cur.fetchall()}
        conn.close()
        return {"names": names}
    except Exception:
        return {"names": {}}


@router.post("/api/backtest_v2/configs")
def save_backtest_v2_config(body: BacktestV2ConfigSaveRequest):
    cfg_obj = sanitize_json(dict(body.config_json or {}))
    cfg_hash = _hash_json(cfg_obj)
    config_id = f"cfg_{cfg_hash[:12]}"
    saved_at = datetime.now().isoformat()
    payload = {
        "config_id": config_id,
        "config_hash": cfg_hash,
        "saved_at": saved_at,
        "name": str(body.name or ""),
        "tags": [str(x) for x in (body.tags or [])],
        "config_json": cfg_obj,
    }
    p = _configs_root() / f"{config_id}.json"
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return _sanitize_for_json({"config_id": config_id, "saved_at": saved_at, "config_hash": cfg_hash})


@router.get("/api/backtest_v2/configs/{config_id}")
def get_backtest_v2_config(config_id: str):
    _ensure_builtin_flow_script_config()
    p = _configs_root() / f"{str(config_id)}.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"config not found: {config_id}")
    try:
        obj = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"config load failed: {exc}")
    return _sanitize_for_json(obj)


@router.get("/api/backtest_v2/configs")
def list_backtest_v2_configs(latest: int = Query(20, ge=1, le=200)):
    _ensure_builtin_flow_script_config()
    root = _configs_root()
    rows: list[dict[str, Any]] = []
    for p in root.glob("cfg_*.json"):
        try:
            obj = json.loads(p.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        rows.append(
            {
                "config_id": str(obj.get("config_id") or p.stem),
                "saved_at": str(obj.get("saved_at") or ""),
                "name": str(obj.get("name") or ""),
                "tags": [str(x) for x in (obj.get("tags") or [])],
                "config_hash": str(obj.get("config_hash") or ""),
            }
        )
    rows.sort(
        key=lambda x: (
            1 if "flow_script" in set(x.get("tags") or []) else 0,
            str(x.get("saved_at") or ""),
        ),
        reverse=True,
    )
    return _sanitize_for_json({"items": rows[: int(latest)]})


def _read_reason_top_codes(path: Path, top_n: int = 5) -> list[str]:
    if not path.exists():
        return []
    try:
        df = pd.read_csv(path)
    except Exception:
        return []
    if df.empty:
        return []
    code_col = "code" if "code" in df.columns else ("reason_code" if "reason_code" in df.columns else None)
    count_col = "count" if "count" in df.columns else ("orders" if "orders" in df.columns else None)
    if code_col is None or count_col is None:
        return []
    tmp = df[[code_col, count_col]].copy()
    tmp.columns = ["code", "count"]
    tmp["count"] = pd.to_numeric(tmp["count"], errors="coerce").fillna(0)
    tmp = tmp.sort_values(["count", "code"], ascending=[False, True])
    return [str(x) for x in tmp["code"].head(max(1, int(top_n))).tolist() if str(x).strip()]


def _latest_trade_date_from_results(results_dir: Path) -> str | None:
    dates: list[str] = []
    for p in list(results_dir.glob("groups/*/nav.csv"))[:50]:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if "date" not in df.columns or df.empty:
            continue
        s = str(df["date"].dropna().astype(str).max() or "").strip()
        if s:
            dates.append(s)
    return max(dates) if dates else None


@router.post("/api/backtest_v2/execution/preview")
def preview_backtest_v2_execution(body: BacktestV2ExecutionPreviewRequest):
    cfg_obj: dict[str, Any] = {}
    cfg_id = str(body.config_id or "").strip()
    if cfg_id:
        p = _configs_root() / f"{cfg_id}.json"
        if p.exists():
            try:
                obj = json.loads(p.read_text(encoding="utf-8-sig"))
                cfg_obj = dict(obj.get("config_json") or {})
            except Exception:
                cfg_obj = {}
    if not cfg_obj and isinstance(body.config_json, dict):
        cfg_obj = dict(body.config_json or {})

    results_dir = _resolve_experiment_dir(exp_id=body.exp_id, results_dir=body.results_dir)
    if results_dir is None:
        raise HTTPException(status_code=404, detail="no experiment results found for execution preview")
    manifest = _load_json_file(results_dir / "manifest.json")
    if not manifest:
        raise HTTPException(status_code=404, detail=f"manifest not found: {results_dir / 'manifest.json'}")

    as_of = str(body.as_of_date or "").strip()
    if not as_of:
        as_of = _latest_trade_date_from_results(results_dir) or date.today().isoformat()

    groups = list(manifest.get("groups") or [])
    scored_groups: list[dict[str, Any]] = []
    for g in groups:
        if not isinstance(g, dict):
            continue
        gid = str(g.get("group_id") or "").strip()
        if not gid:
            continue
        gf = dict(g.get("group_files") or {})
        gdir = str(g.get("group_dir") or "")
        group_dir = (results_dir / gdir).resolve() if gdir else (results_dir / "groups" / gid).resolve()
        perf = _load_json_file((results_dir / str(gf.get("perf") or "")).resolve()) if gf.get("perf") else _load_json_file(group_dir / "perf.json")
        run_meta = _load_json_file((results_dir / str(gf.get("run_meta") or "")).resolve()) if gf.get("run_meta") else _load_json_file(group_dir / "run_meta.json")
        reason_path = (results_dir / str(gf.get("reason_codes") or "")).resolve() if gf.get("reason_codes") else (group_dir / "reason_code_counts.csv")
        cagr = float(_coerce_number(perf.get("cagr")) or 0.0)
        mdd = float(_coerce_number(perf.get("max_drawdown")) or 0.0)
        sharpe = float(_coerce_number(perf.get("sharpe")) or 0.0)
        score = cagr + sharpe * 0.1 + mdd * 0.4
        scored_groups.append(
            {
                "group_id": gid,
                "score": score,
                "cagr": cagr,
                "max_drawdown": mdd,
                "sharpe": sharpe,
                "reasons": _read_reason_top_codes(reason_path, top_n=5),
                "triggers": dict((run_meta.get("counters") or {})),
            }
        )
    scored_groups.sort(key=lambda x: (-float(x.get("score") or 0.0), str(x.get("group_id") or "")))
    top_n = max(1, int(body.top_n or 10))
    picked = scored_groups[:top_n]

    source = "manifest_groups"
    symbols_cfg = list((cfg_obj.get("universe") or {}).get("symbols") or cfg_obj.get("symbols") or [])
    candidates: list[dict[str, Any]] = []
    if symbols_cfg:
        # Symbol-level preview from config universe, scored by top group score.
        base_score = float(picked[0].get("score") if picked else 0.0)
        for idx, s in enumerate(symbols_cfg[:top_n], start=1):
            candidates.append(
                {
                    "symbol": str(s),
                    "score": base_score - (idx - 1) * 1e-6,
                    "rank": idx,
                    "reasons": ["source=config_symbols", f"active_group={picked[0]['group_id'] if picked else 'N/A'}"],
                }
            )
        source = "config_symbols_fallback"
    else:
        for idx, g in enumerate(picked, start=1):
            candidates.append(
                {
                    "symbol": str(g.get("group_id") or ""),
                    "score": float(g.get("score") or 0.0),
                    "rank": idx,
                    "reasons": [f"group={g.get('group_id')}", *[str(x) for x in (g.get("reasons") or [])[:3]]],
                }
            )

    max_positions = int(_coerce_number((cfg_obj.get("portfolio") or {}).get("max_positions"), integer=True) or _coerce_number(cfg_obj.get("max_positions"), integer=True) or max(1, len(candidates)))
    single_cap = float(_coerce_number((cfg_obj.get("risk") or {}).get("single_stock_cap"), integer=False) or _coerce_number(cfg_obj.get("single_stock_cap"), integer=False) or 0.1)
    npos = min(max_positions, max(1, len(candidates)))
    eq_w = 1.0 / float(npos)
    target_positions = []
    for item in candidates[:npos]:
        tw = min(eq_w, single_cap)
        cap_reason = "single_stock_cap" if tw < eq_w else ""
        target_positions.append({"symbol": item["symbol"], "target_weight": round(float(tw), 6), "cap_reason": cap_reason})

    out_obj = {
        "as_of_date_used": as_of,
        "source": source,
        "results_dir": str(results_dir),
        "candidates": candidates,
        "target_positions": target_positions,
    }
    cfg_hash = _hash_json(cfg_obj) if cfg_obj else "na"
    key = hashlib.sha1(f"{results_dir}|{as_of}|{top_n}|{cfg_hash}".encode("utf-8")).hexdigest()[:12]
    out_path = _execution_root() / f"execution_list_{key}.json"
    out_path.write_text(json.dumps(sanitize_json(out_obj), ensure_ascii=False, indent=2), encoding="utf-8")
    out_obj["files"] = {"execution_list_json_path": str(out_path)}
    return _sanitize_for_json(out_obj)


@router.post("/api/backtest_v2/artifacts/read")
def read_backtest_v2_artifact(body: BacktestV2ArtifactReadRequest):
    results_dir = Path(str(body.results_dir or "")).resolve()
    if not results_dir.exists():
        raise HTTPException(status_code=404, detail=f"results_dir not found: {results_dir}")
    rel = str(body.rel_path or "").strip().replace("\\", "/").lstrip("/")
    if not rel:
        raise HTTPException(status_code=400, detail="rel_path is required")
    target = (results_dir / rel).resolve()
    if not str(target).startswith(str(results_dir)):
        raise HTTPException(status_code=400, detail="invalid rel_path")
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"artifact not found: {target}")
    ext = target.suffix.lower()
    if ext == ".json":
        try:
            obj = json.loads(target.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"json parse failed: {exc}")
        return _sanitize_for_json({"kind": "json", "path": rel, "data": obj})
    if ext == ".csv":
        try:
            df = pd.read_csv(target)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"csv parse failed: {exc}")
        return _sanitize_for_json({"kind": "csv", "path": rel, "rows": df.to_dict(orient="records"), "columns": list(df.columns)})
    text = target.read_text(encoding="utf-8", errors="ignore")
    return _sanitize_for_json({"kind": "text", "path": rel, "text": text[:200000]})


# ── Experiment History API ──────────────────────────────────────────────────

def _experiments_root() -> Path:
    return _results_root() / "experiments"


def _read_index() -> list[dict[str, Any]]:
    index_path = _experiments_root() / "index.json"
    if not index_path.exists():
        return []
    try:
        entries = json.loads(index_path.read_text(encoding="utf-8"))
        return entries if isinstance(entries, list) else []
    except Exception:
        return []


def _write_index(entries: list[dict[str, Any]]) -> None:
    index_path = _experiments_root() / "index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


@router.get("/api/backtest_v2/experiments")
def list_experiments():
    """Return experiment list (newest first), with lazy orphan cleanup."""
    entries = _read_index()
    exp_root = _experiments_root()
    # Filter out orphan entries whose directories no longer exist
    valid = [e for e in entries if (exp_root / str(e.get("exp_id", ""))).is_dir()]
    if len(valid) != len(entries):
        _write_index(valid)
    # Sort by created_at descending
    valid.sort(key=lambda e: str(e.get("created_at", "")), reverse=True)
    return valid


@router.get("/api/backtest_v2/experiments/{exp_id}/report")
def get_experiment_report(exp_id: str):
    """Return report.html as text/html."""
    report_path = _experiments_root() / exp_id / "report.html"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="report not found")
    html = report_path.read_text(encoding="utf-8")
    return HTMLResponse(content=html)


@router.delete("/api/backtest_v2/experiments/{exp_id}")
def delete_experiment(exp_id: str):
    """Delete a single experiment directory and remove from index."""
    import shutil
    exp_dir = _experiments_root() / exp_id
    if not exp_dir.is_dir():
        raise HTTPException(status_code=404, detail="experiment not found")
    shutil.rmtree(exp_dir, ignore_errors=True)
    entries = _read_index()
    entries = [e for e in entries if e.get("exp_id") != exp_id]
    _write_index(entries)
    return {"status": "deleted"}


@router.delete("/api/backtest_v2/experiments")
def clear_all_experiments():
    """Delete all experiment directories and reset index."""
    import shutil
    exp_root = _experiments_root()
    count = 0
    if exp_root.exists():
        for d in exp_root.iterdir():
            if d.is_dir() and d.name.startswith("exp_"):
                shutil.rmtree(d, ignore_errors=True)
                count += 1
    _write_index([])
    return {"status": "cleared", "count": count}


