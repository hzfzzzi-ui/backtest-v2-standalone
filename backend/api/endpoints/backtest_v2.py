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
from pandas.errors import EmptyDataError
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from .backtest_v2_protocol import (
    normalize_counters as protocol_normalize_counters,
    resolve_artifact_path,
)
from ._utils import (
    sanitize_json,
    _coerce_number,
    _load_json_file,
    _hash_json,
    _sanitize_for_json,
)
from ._paths import (
    _repo_root,
    _bt_root,
    _results_root,
    _configs_root,
    _execution_root,
)
from . import _config_store
from . import _experiment_runner_api
from . import _experiment_history

router = APIRouter(tags=["backtest_v2"])
router.include_router(_config_store.router)
router.include_router(_experiment_runner_api.router)
router.include_router(_experiment_history.router)

logger = logging.getLogger(__name__)


def _inject_db_env(cfg_obj: Any) -> None:
    """Override DB credentials from environment variables (Docker runtime)."""
    db = cfg_obj.db
    if not db.password:
        db.password = os.environ.get("PGPASSWORD", os.environ.get("PAMS_PG_PASSWORD", ""))
    if os.environ.get("PGHOST"):
        db.host = os.environ["PGHOST"]
    if os.environ.get("PGPORT"):
        db.port = int(os.environ["PGPORT"])
    if os.environ.get("PGUSER"):
        db.user = os.environ["PGUSER"]
    if os.environ.get("PGDATABASE"):
        db.dbname = os.environ["PGDATABASE"]


# ── Pydantic models (main-file-only) ───────────────────────────────────────


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


# ── Helper functions (main-file-only) ──────────────────────────────────────


def _resolve_reason_codes_path(group_dir: Path) -> tuple[Path, bool]:
    path, legacy = resolve_artifact_path(group_dir, "reason_codes")
    return path, legacy


def _normalized_run_meta_counters(run_meta: dict[str, Any]) -> tuple[dict[str, Any], int]:
    counters = run_meta.get("counters") if isinstance(run_meta, dict) else {}
    normalized, legacy_hits = protocol_normalize_counters(counters if isinstance(counters, dict) else {})
    return normalized, legacy_hits


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
    path, legacy = _resolve_reason_codes_path(group_dir)
    if not path.exists():
        return {}
    if legacy:
        logger.info("legacy artifact alias hit: reason_code_counts.csv -> reason_codes.csv (%s)", str(group_dir))
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
    _inject_db_env(cfg_obj)

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

    from backend.core.config.loader import load_config
    from backend.core.data.pg_provider import PostgresDataProvider
    from backend.core.data.errors import DatabaseConnectionError
    from backend.core.data.mapping import normalize_stock_symbol

    target_symbol = str(symbol or "").strip()
    if not target_symbol:
        raise HTTPException(status_code=422, detail="symbol is required")

    try:
        norm_symbol = normalize_stock_symbol(target_symbol)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"invalid symbol: {exc}")

    bt_root = _bt_root()
    cfg_path = bt_root / "configs" / "pams_cn_pg.json"
    if not cfg_path.exists():
        cfg_path = bt_root.parent / "configs" / "pams_cn_pg.json"
        if not cfg_path.exists():
            raise HTTPException(status_code=500, detail=f"config not found: {cfg_path}")
    cfg_obj, _ = load_config(str(cfg_path))
    _inject_db_env(cfg_obj)

    provider = PostgresDataProvider(
        db=cfg_obj.db,
        runtime=cfg_obj.db_runtime,
        data_source=cfg_obj.data_source,
        schema_mapping=cfg_obj.schema_mapping,
        rules_path=cfg_path.parent / "instrument_rules_cn.csv",
    )

    try:
        df = provider.load_ohlcv_daily([norm_symbol], start_d, end_d, source="stocks")
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
        cal = provider.load_trading_calendar_cn(start_d, end_d)
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
        _c = round(float(row["close"]) / fc, 6)
        p = {
            "date": str(row["date"])[:10],
            "nav": _c,
            "close": _c,
            "suspended": bool(row.get("suspended", False)),
        }
        if has_ohlc:
            p["open"] = round(float(row["open"]) / fc, 6)
            p["high"] = round(float(row["high"]) / fc, 6)
            p["low"] = round(float(row["low"]) / fc, 6)
        else:
            p["open"] = _c
            p["high"] = _c
            p["low"] = _c
        points.append(p)
    return _sanitize_for_json({"points": points, "source": "api", "symbol": norm_symbol})


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


# ── Results / execution preview / artifact read routes ─────────────────────


@router.get("/api/backtest_v2/results/{run_id}")
def get_backtest_v2_result(run_id: str):
    out_dir = _results_root() / run_id
    if not out_dir.exists():
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    payload = _sanitize_for_json(_read_result(out_dir))
    payload["run_id"] = run_id
    return payload


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
    legacy_hits = {"reason_codes_filename": 0, "counters_field_alias": 0}
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
            reason_legacy = reason_path.name == "reason_code_counts.csv"
        else:
            reason_path, reason_legacy = _resolve_reason_codes_path(group_dir)
        counters, counter_legacy_hits = _normalized_run_meta_counters(run_meta)
        legacy_hits["reason_codes_filename"] += int(reason_legacy)
        legacy_hits["counters_field_alias"] += int(counter_legacy_hits)
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
        "as_of_date_used": as_of,
        "source": source,
        "results_dir": str(results_dir),
        "candidates": candidates,
        "target_positions": target_positions,
        "legacy_hits": legacy_hits,
    }
    cfg_hash = _hash_json(cfg_obj) if cfg_obj else "na"
    key = hashlib.sha1(f"{results_dir}|{as_of}|{top_n}|{cfg_hash}".encode("utf-8")).hexdigest()[:12]
    out_path = _execution_root() / f"execution_list_{key}.json"
    out_path.write_text(json.dumps(sanitize_json(out_obj), ensure_ascii=False, indent=2), encoding="utf-8")
    out_obj["files"] = {"execution_list_json_path": str(out_path)}
    return _sanitize_for_json(out_obj)


@router.post("/api/backtest_v2/artifacts/read")
def read_backtest_v2_artifact(body: BacktestV2ArtifactReadRequest):
    raw_dir = str(body.results_dir or "")
    p = Path(raw_dir)
    if not p.is_absolute():
        p = (_results_root() / raw_dir).resolve()
    else:
        p = p.resolve()
    results_dir = p
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
