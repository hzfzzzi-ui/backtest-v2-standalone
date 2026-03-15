from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request

from backend.api.backtest_v2.protocol import (
    normalize_counters as protocol_normalize_counters,
    resolve_artifact_path,
)
from backend.api.shared.json_utils import (
    sanitize_json,
    coerce_number as _coerce_number,
    load_json_file as _load_json_file,
    hash_json as _hash_json,
    sanitize_for_json as _sanitize_for_json,
)
from backend.api.shared.paths import (
    bt_root as _bt_root,
    results_root as _results_root,
    execution_root as _execution_root,
)
from backend.core.tools.experiment_artifact_access import (
    experiment_surface_flags,
    load_manifest as load_experiment_manifest,
    manifest_artifact_rel,
    resolve_declared_artifact_path,
    resolve_experiment_dir_by_id,
)
from backend.api.backtest_v2.contracts.requests import (
    ArtifactReadRequest as PublicBacktestV2ArtifactReadRequest,
    ExecutionPreviewRequest as PublicBacktestV2ExecutionPreviewRequest,
)
from backend.core.tools.runtime_data_access import (
    list_runtime_industries,
    load_benchmark_series_frame,
    load_runtime_data_access,
    load_symbol_series_frame,
    resolve_stock_names as resolve_runtime_stock_names,
    resolve_validation_universe,
)
from backend.core.universe.lineage import annotate_universe_meta
from backend.api.backtest_v2 import configs_impl as _config_store
from backend.api.backtest_v2 import runner_impl
from backend.api.backtest_v2 import history_impl

router = APIRouter(tags=["backtest_v2"])
router.include_router(_config_store.router)
router.include_router(runner_impl.router)
router.include_router(history_impl.router)

logger = logging.getLogger(__name__)


# ── Pydantic models (main-file-only) ───────────────────────────────────────


BacktestV2ExecutionPreviewRequest = PublicBacktestV2ExecutionPreviewRequest


BacktestV2ArtifactReadRequest = PublicBacktestV2ArtifactReadRequest


# ── Helper functions (main-file-only) ──────────────────────────────────────


def _resolve_reason_codes_path(group_dir: Path) -> Path:
    return resolve_artifact_path(group_dir, "reason_codes")


def _normalized_run_meta_counters(run_meta: dict[str, Any]) -> tuple[dict[str, Any], int]:
    counters = run_meta.get("counters") if isinstance(run_meta, dict) else {}
    return protocol_normalize_counters(counters if isinstance(counters, dict) else {})


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
    path = _resolve_reason_codes_path(group_dir)
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
    return {
        "atr_stop_exit_count": int(cnt[code.eq("ATR_STOP_LOSS")].sum()),
        "atr_trail_exit_count": int(cnt[code.eq("ATR_TRAIL_EXIT")].sum()),
        "reversal_exit_count": int(cnt[code.isin(["SIGNAL_REVERSE", "SMA_CROSS_DOWN"])].sum()),
        "time_exit_count": int(cnt[code.eq("TIME_EXIT")].sum()),
    }


def _build_universe_stats(
    validate_result: dict[str, Any],
    symbols: list[str],
    resolved_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    checks = validate_result.get("checks") if isinstance(validate_result.get("checks"), dict) else {}
    meta = validate_result.get("meta") if isinstance(validate_result.get("meta"), dict) else {}
    coverage = checks.get("coverage") if isinstance(checks.get("coverage"), dict) else {}
    by_symbol = coverage.get("by_symbol") if isinstance(coverage.get("by_symbol"), dict) else {}
    resolved = resolved_meta if isinstance(resolved_meta, dict) else {}

    total_symbols = int(
        _coerce_number(resolved.get("raw_count"), integer=True)
        or _coerce_number(validate_result.get("resolved_symbols_count"), integer=True)
        or len(symbols)
    )
    coverage_nonzero = int(sum(1 for _, v in by_symbol.items() if int(_coerce_number(v, integer=True) or 0) > 0))
    tradable_symbols = int(
        _coerce_number(resolved.get("tradable_symbols"), integer=True)
        or _coerce_number(validate_result.get("tradable_symbols"), integer=True)
        or coverage_nonzero
        or total_symbols
    )
    after_filters_symbols = int(
        _coerce_number(resolved.get("after_filters_symbols"), integer=True)
        or _coerce_number(validate_result.get("after_filters_symbols"), integer=True)
        or tradable_symbols
    )
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
        if resolved:
            filter_breakdown = [
                {"name": "resolver", "before": total_symbols, "after": total_symbols},
                {"name": "runtime_filters", "before": tradable_symbols, "after": after_filters_symbols},
                {"name": "final_universe", "before": after_filters_symbols, "after": universe_size},
            ]
        else:
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
            "validation_scope": validate_result.get("validation_scope") or ("runtime_resolved" if resolved else "sample_symbols"),
            "scope_label": validate_result.get("scope_label") or ("按真实 universe resolver 口径验证" if resolved else "按样本 symbols 验证"),
            "universe_mode": resolved.get("universe_mode"),
            "resolve_asof": resolved.get("resolve_asof"),
            "dynamic_all_a_entry": resolved.get("dynamic_all_a_entry"),
        }
    )

def _validate_public_execution_preview_request(body: BacktestV2ExecutionPreviewRequest) -> None:
    if not isinstance(body.config_json, dict):
        raise HTTPException(status_code=400, detail="execution preview requires config_json")
    if not str(body.exp_id or "").strip():
        raise HTTPException(status_code=400, detail="execution preview requires exp_id")


def _load_manifest_or_404(exp_id: str) -> tuple[Path, dict[str, Any]]:
    results_dir = resolve_experiment_dir_by_id(exp_id)
    if results_dir is None:
        raise HTTPException(status_code=404, detail=f"experiment not found: {exp_id}")
    manifest = load_experiment_manifest(results_dir)
    if not manifest:
        raise HTTPException(status_code=404, detail=f"manifest not found: {results_dir / 'manifest.json'}")
    return results_dir, manifest


def _read_declared_artifact_payload(results_dir: Path, manifest: dict[str, Any], rel: str) -> dict[str, Any]:
    target = resolve_declared_artifact_path(results_dir, manifest, rel)
    if target is None:
        raise HTTPException(status_code=400, detail=f"artifact path is not declared by manifest: {rel}")
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


def _parse_list_from_query(request: Request, key: str) -> list[str]:
    vals = request.query_params.getlist(key)
    if not vals:
        raw = str(request.query_params.get(key) or "").strip()
        return [x.strip() for x in raw.split(",") if x.strip()] if raw else []
    out: list[str] = []
    for v in vals:
        out.extend([x.strip() for x in str(v).split(",") if x.strip()])
    return out


def _parse_bool_from_query(request: Request, key: str, default: bool = False) -> bool:
    raw = request.query_params.get(key)
    if raw is None:
        return bool(default)
    s = str(raw).strip().lower()
    if not s:
        return bool(default)
    return s in {"1", "true", "yes", "y", "on"}


def _parse_int_from_query(request: Request, key: str, default: int = 0) -> int:
    n = _coerce_number(request.query_params.get(key), integer=True)
    return int(n) if n is not None else int(default)


def _parse_float_from_query(request: Request, key: str, default: float = 0.0) -> float:
    n = _coerce_number(request.query_params.get(key))
    return float(n) if n is not None else float(default)

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


# ── Market data routes ─────────────────────────────────────────────────────


@router.get("/api/backtest_v2/industries")
def get_industries():
    """返回 pit_industry_history 中所有不重复的 L1 行业名列表。"""
    return {"industries": list_runtime_industries(bt_root=_bt_root())}


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

    from backend.core.data.errors import DatabaseConnectionError

    try:
        df = load_benchmark_series_frame(symbol=symbol, start=start_d, end=end_d, bt_root=_bt_root())
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


@router.get("/api/backtest_v2/series/symbol")
def get_symbol_series(
    symbol: str = Query(...),
    start: str = Query(...),
    end: str = Query(...),
):
    try:
        start_d = date.fromisoformat(start)
        end_d = date.fromisoformat(end)
    except Exception:
        raise HTTPException(status_code=422, detail="start/end must be YYYY-MM-DD")

    from backend.core.data.errors import DatabaseConnectionError
    from backend.core.data.mapping import normalize_stock_symbol

    target_symbol = str(symbol or "").strip()
    if not target_symbol:
        raise HTTPException(status_code=422, detail="symbol is required")

    try:
        norm_symbol = normalize_stock_symbol(target_symbol)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"invalid symbol: {exc}")

    access = load_runtime_data_access(_bt_root())

    try:
        df = load_symbol_series_frame(symbol=norm_symbol, start=start_d, end=end_d, access=access)
    except DatabaseConnectionError:
        raise HTTPException(status_code=503, detail="database connection failed")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if df.empty or "close" not in df.columns:
        return _sanitize_for_json({"points": [], "source": "empty", "symbol": norm_symbol})

    sdf = df[df["symbol"].astype(str).str.lower() == norm_symbol.lower()].copy()
    if sdf.empty:
        return _sanitize_for_json({"points": [], "source": "empty", "symbol": norm_symbol})
    sdf = sdf.sort_values("date").reset_index(drop=True)
    first_close = sdf["close"].iloc[0]
    if first_close == 0 or pd.isna(first_close):
        return _sanitize_for_json({"points": [], "source": "empty", "symbol": norm_symbol})

    # ── 停牌填充：用交易日历 reindex + ffill ──
    has_ohlc = all(c in sdf.columns for c in ("open", "high", "low"))
    sdf["date"] = pd.to_datetime(sdf["date"]).dt.normalize()
    original_dates = set(sdf["date"].tolist())
    try:
        cal = access.provider.load_trading_calendar_cn(start_d, end_d)
    except Exception:
        cal = pd.DatetimeIndex([])
    if len(cal) > 0:
        sdf = sdf.set_index("date").reindex(cal).sort_index()
        # forward-fill OHLCV 列
        fill_cols = ["close"] + (["open", "high", "low"] if has_ohlc else [])
        sdf[fill_cols] = sdf[fill_cols].ffill()
        # 停牌日标记
        sdf["suspended"] = ~sdf.index.isin(original_dates)
        # 停牌日 OHLC 全部设为 close（平线）
        susp_mask = sdf["suspended"]
        if has_ohlc and susp_mask.any():
            for col in ("open", "high", "low"):
                sdf.loc[susp_mask, col] = sdf.loc[susp_mask, "close"]
        # 去掉 ffill 前无数据的行（查询起始前已停牌的情况）
        sdf = sdf.dropna(subset=["close"])
        sdf = sdf.reset_index().rename(columns={"index": "date"})
    else:
        sdf["suspended"] = False

    fc = float(first_close)
    points = []
    for _, row in sdf.iterrows():
        close_abs = round(float(row["close"]), 6)
        _c = round(close_abs / fc, 6)
        p = {
            "date": str(row["date"])[:10],
            "nav": _c,
            "close": close_abs,
            "suspended": bool(row.get("suspended", False)),
        }
        if has_ohlc:
            p["open"] = round(float(row["open"]), 6)
            p["high"] = round(float(row["high"]), 6)
            p["low"] = round(float(row["low"]), 6)
        else:
            p["open"] = close_abs
            p["high"] = close_abs
            p["low"] = close_abs
        points.append(p)
    return _sanitize_for_json({"points": points, "source": "api", "symbol": norm_symbol})


@router.post("/api/backtest_v2/stock_names")
def get_stock_names(body: dict):
    """批量查询股票中文名称，入参 {"symbols": ["sh600067", "sz000001", ...]}"""
    symbols = body.get("symbols") or []
    if not symbols:
        return {"names": {}}
    return {"names": resolve_runtime_stock_names(list(symbols), bt_root=_bt_root())}


# ── Validate data route ────────────────────────────────────────────────────


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
    from backend.core.universe.hs300_csi500 import UniverseLoadError

    universe_mode = str(request.query_params.get("universe_mode") or ("CUSTOM" if _parse_symbols_from_query(request) else "ALL_A")).strip().upper()
    symbols = _parse_symbols_from_query(request)
    industries = _parse_list_from_query(request, "industries")
    universe_limit_raw = _parse_int_from_query(request, "universe_limit", 0)
    universe_limit = universe_limit_raw if universe_limit_raw > 0 else None
    exclude_st = _parse_bool_from_query(request, "exclude_st", True)
    exclude_suspended = _parse_bool_from_query(request, "exclude_suspended", True)
    min_list_days = _parse_int_from_query(request, "min_list_days", 120)
    min_avg_turnover_20d = _parse_float_from_query(request, "min_avg_turnover_20d", 1e8)
    min_avg_turnover_rate_20d = _parse_float_from_query(request, "min_avg_turnover_rate_20d", 0.0)
    turnover_rate_field = str(request.query_params.get("turnover_rate_field") or "turnover_rate_f").strip().lower() or "turnover_rate_f"
    price_min = _parse_float_from_query(request, "price_min", 0.0)
    price_max = _parse_float_from_query(request, "price_max", 99999.0)
    limit_rule = str(request.query_params.get("limit_rule") or "ignore").strip().lower() or "ignore"

    if universe_mode == "CUSTOM" and not symbols:
        raise HTTPException(status_code=400, detail="symbols is required for CUSTOM universe_mode")

    try:
        validation_snapshot = resolve_validation_universe(
            bt_root=bt_root,
            universe_mode=universe_mode,
            symbols=symbols,
            industries=industries,
            universe_limit=universe_limit,
            start=start_d,
            end=end_d,
            exclude_st=exclude_st,
            exclude_suspended=exclude_suspended,
            min_list_days=min_list_days,
            min_avg_turnover_20d=min_avg_turnover_20d,
            min_avg_turnover_rate_20d=min_avg_turnover_rate_20d,
            turnover_rate_field=turnover_rate_field,
            price_min=price_min,
            price_max=price_max,
            limit_rule=limit_rule,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except UniverseLoadError as exc:
        failed_meta = dict(exc.meta or {})
        failed_meta = annotate_universe_meta(
            failed_meta,
            mode=universe_mode,
            start=start_d,
            end=end_d,
        )
        failed_meta.setdefault("tradable_symbols", 0)
        failed_meta.setdefault("after_filters_symbols", 0)
        failed_meta.setdefault("raw_count", int(_coerce_number(failed_meta.get("raw_count"), integer=True) or 0))
        result = {
            "pass": False,
            "request_id": f"val_{uuid.uuid4().hex[:10]}",
            "results_root": str(_results_root().resolve()),
            "meta": {
                "symbols_count": 0,
                "symbols": [],
                "date_range": {"start": start_d.isoformat(), "end": end_d.isoformat()},
                "benchmark": benchmark,
                "universe_mode": universe_mode,
                "industries": industries,
                "universe_limit": universe_limit,
            },
            "checks": {},
            "warnings": [],
            "errors": [{"code": exc.status, "message": str(exc)}],
            "resolved_symbols_count": 0,
            "validation_scope": "runtime_resolved",
            "scope_label": f"按真实 universe resolver 口径验证 ({universe_mode})",
        }
        result["universe_stats"] = _build_universe_stats(result, [], resolved_meta=failed_meta)
        return _sanitize_for_json(result)
    resolved_symbols = list(validation_snapshot.resolved_symbols)
    resolved_meta = dict(validation_snapshot.resolved_meta)
    resolve_asof = validation_snapshot.resolve_asof
    dynamic_all_a_entry = validation_snapshot.dynamic_all_a_entry

    if not resolved_symbols:
        result = {
            "pass": False,
            "request_id": f"val_{uuid.uuid4().hex[:10]}",
            "results_root": str(_results_root().resolve()),
            "meta": {
                "symbols_count": 0,
                "symbols": [],
                "date_range": {"start": start_d.isoformat(), "end": end_d.isoformat()},
                "benchmark": benchmark,
                "universe_mode": universe_mode,
                "industries": industries,
                "universe_limit": universe_limit,
            },
            "checks": {},
            "warnings": [],
            "errors": [{"code": "EMPTY:RUNTIME_UNIVERSE", "message": "runtime-resolved universe is empty after filters"}],
            "resolved_symbols_count": 0,
            "validation_scope": "runtime_resolved",
            "scope_label": f"按真实 universe resolver 口径验证 ({universe_mode})",
        }
        result["universe_stats"] = _build_universe_stats(result, [], resolved_meta=resolved_meta)
        return _sanitize_for_json(result)

    cfg = PGConnConfig(
        host=os.environ.get("PGHOST", os.environ.get("PAMS_PG_HOST", "pams-postgres")),
        port=int(os.environ.get("PGPORT", os.environ.get("PAMS_PG_PORT", "5432"))),
        dbname=os.environ.get("PGDATABASE", os.environ.get("PAMS_PG_DBNAME", "pams")),
        user=os.environ.get("PGUSER", os.environ.get("PAMS_PG_USER", "pams")),
        password=os.environ.get("PGPASSWORD", os.environ.get("PAMS_PG_PASSWORD", "")),
        statement_timeout_ms=60000,
    )
    try:
        result = validate_data(
            pg=cfg,
            symbols=resolved_symbols,
            start=start_d,
            end=end_d,
            benchmark=benchmark,
            audit_dump=audit_dump,
            strict_suspended=strict_suspended,
            allow_cn_index_fallback=allow_cn_index_fallback,
            required_turnover_rate_field=turnover_rate_field if min_avg_turnover_rate_20d > 0.0 else None,
            results_root=_results_root(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if isinstance(result, dict):
        result.setdefault("request_id", f"val_{uuid.uuid4().hex[:10]}")
        result.setdefault("results_root", str(_results_root().resolve()))
        result["resolved_symbols_count"] = int(len(resolved_symbols))
        result["resolved_symbols_sample"] = list(resolved_symbols[:20])
        result["tradable_symbols"] = int(_coerce_number(resolved_meta.get("tradable_symbols"), integer=True) or len(resolved_symbols))
        result["after_filters_symbols"] = int(_coerce_number(resolved_meta.get("after_filters_symbols"), integer=True) or len(resolved_symbols))
        result["validation_scope"] = "runtime_resolved"
        result["scope_label"] = f"按真实 universe resolver 口径验证 ({universe_mode})"
        meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
        meta["universe_mode"] = universe_mode
        meta["industries"] = list(industries)
        meta["universe_limit"] = universe_limit
        meta["resolve_asof"] = str(resolve_asof)
        meta["dynamic_all_a_entry"] = bool(dynamic_all_a_entry)
        meta["min_avg_turnover_rate_20d"] = float(min_avg_turnover_rate_20d)
        meta["turnover_rate_field"] = turnover_rate_field
        result["meta"] = meta
        result["universe_stats"] = _build_universe_stats(result, resolved_symbols, resolved_meta=resolved_meta)
    return _sanitize_for_json(result)


# ── Results / execution preview / artifact read routes ─────────────────────


@router.post("/api/backtest_v2/execution/preview")
def preview_backtest_v2_execution(body: BacktestV2ExecutionPreviewRequest):
    _validate_public_execution_preview_request(body)
    base_cfg = runner_impl._load_base_config(_bt_root())
    semantic_compile = runner_impl._compile_semantic_config_bundle(
        base_cfg=base_cfg,
        body=runner_impl.BacktestV2ExperimentRequest(),
        semantic_cfg=body.config_json,
        config_source="config_json",
        use_body_universe_fields=False,
    )
    resolution = {
        "config_source": "config_json",
        "resolved_config_mode": "semantic_config_preview",
        "resolved_config_id": None,
        "resolved_config_hash": semantic_compile.get("config_hash"),
        "resolved_config_meta": {
            "source_type": "frontend_semantic",
            "owner": "manual",
            "schema_version": semantic_compile.get("schema_version"),
            "config_source": semantic_compile.get("config_source"),
            "config_hash": semantic_compile.get("config_hash"),
        },
        "config_conflict_policy": "config_json_preferred",
    }
    compiled_plan = semantic_compile.get("compiled_plan") if isinstance(semantic_compile.get("compiled_plan"), dict) else {}
    cfg_obj = dict(compiled_plan.get("runtime_config") or {})

    results_dir, manifest = _load_manifest_or_404(str(body.exp_id or "").strip())

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
        if gf.get("reason_codes"):
            reason_path = (results_dir / str(gf.get("reason_codes") or "")).resolve()
        else:
            reason_path = _resolve_reason_codes_path(group_dir)
        counters, _historical_counter_hits = _normalized_run_meta_counters(run_meta)
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
                "triggers": dict(counters),
            }
        )
    scored_groups.sort(key=lambda x: (-float(x.get("score") or 0.0), str(x.get("group_id") or "")))
    top_n = max(1, int(body.top_n or 10))
    picked = scored_groups[:top_n]

    source = "manifest_groups"
    symbols_cfg = list((cfg_obj.get("universe") or {}).get("symbols") or cfg_obj.get("symbols") or [])
    candidates: list[dict[str, Any]] = []
    if symbols_cfg:
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
        "experiment_id": str(body.exp_id or "").strip(),
        "exp_id": str(body.exp_id or "").strip(),
        "as_of_date_used": as_of,
        "source": source,
        "config_source": str(resolution.get("config_source") or "none"),
        "resolved_config_mode": str(resolution.get("resolved_config_mode") or "none"),
        "resolved_config_id": resolution.get("resolved_config_id"),
        "resolved_config_hash": resolution.get("resolved_config_hash"),
        "resolved_config_meta": resolution.get("resolved_config_meta"),
        "resolved_config_source_type": str(((resolution.get("resolved_config_meta") or {}) if isinstance(resolution.get("resolved_config_meta"), dict) else {}).get("source_type") or ""),
        "resolved_config_owner": str(((resolution.get("resolved_config_meta") or {}) if isinstance(resolution.get("resolved_config_meta"), dict) else {}).get("owner") or ""),
        "config_conflict_policy": str(resolution.get("config_conflict_policy") or "none"),
        "candidates": candidates,
        "target_positions": target_positions,
    }
    if isinstance(semantic_compile, dict):
        out_obj["config_compiler"] = {
            "schema_version": str(semantic_compile.get("schema_version") or ""),
            "config_hash": str(semantic_compile.get("config_hash") or ""),
            "config_source": str(semantic_compile.get("config_source") or ""),
        }
    cfg_hash = _hash_json(cfg_obj) if cfg_obj else "na"
    key = hashlib.sha1(f"{results_dir}|{as_of}|{top_n}|{cfg_hash}".encode("utf-8")).hexdigest()[:12]
    out_path = _execution_root() / f"execution_list_{key}.json"
    out_path.write_text(json.dumps(sanitize_json(out_obj), ensure_ascii=False, indent=2), encoding="utf-8")
    out_obj["files"] = {"execution_list_json_path": str(out_path)}
    return _sanitize_for_json(out_obj)


@router.get("/api/backtest_v2/experiments/{exp_id}/manifest")
def get_backtest_v2_manifest(exp_id: str):
    _, manifest = _load_manifest_or_404(exp_id)
    return _sanitize_for_json(manifest)


@router.get("/api/backtest_v2/experiments/{exp_id}/artifacts/{rel_path:path}")
def get_backtest_v2_artifact(exp_id: str, rel_path: str):
    results_dir, manifest = _load_manifest_or_404(exp_id)
    rel = str(rel_path or "").strip().replace("\\", "/").lstrip("/")
    if not rel:
        raise HTTPException(status_code=400, detail="rel_path is required")
    return _read_declared_artifact_payload(results_dir, manifest, rel)


@router.post("/api/backtest_v2/artifacts/read")
def read_backtest_v2_artifact(body: BacktestV2ArtifactReadRequest):
    results_dir, manifest = _load_manifest_or_404(str(body.exp_id or "").strip())
    rel = str(body.rel_path or "").strip().replace("\\", "/").lstrip("/")
    if not rel:
        raise HTTPException(status_code=400, detail="rel_path is required")
    return _read_declared_artifact_payload(results_dir, manifest, rel)
