from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import logging
import pandas as pd

from backend.core.analytics.symbol_performance import build_symbol_performance
from .backtest_v2_protocol import ARTIFACT_FILENAMES, MISSING_FIELD_KEYS
from ._utils import sanitize_json
from ._paths import _repo_root, _results_root

logger = logging.getLogger(__name__)


def _safe_float(v: Any) -> float | None:
    if v in (None, ""):
        return None
    try:
        n = float(v)
    except Exception:
        return None
    if math.isnan(n) or math.isinf(n):
        return None
    return n


def _safe_int(v: Any) -> int | None:
    if v in (None, ""):
        return None
    try:
        return int(float(v))
    except Exception:
        return None


def _to_rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _resolve_runtime_path(raw: str | None, bt_root: Path) -> Path | None:
    if not raw:
        return None
    p = Path(str(raw))
    if p.exists():
        return p.resolve()
    text = str(raw).strip()
    if text.startswith("/app/backend/core"):
        mapped = bt_root / text[len("/app/backend/core") :].lstrip("/\\")
        if mapped.exists():
            return mapped.resolve()
    return None


def _resolve_stock_names(symbols: list[str]) -> dict[str, str]:
    """Query DB for Chinese stock names. Returns {symbol: name} mapping."""
    if not symbols:
        return {}
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
            cur.execute(
                "SELECT symbol, name FROM pit_security_master WHERE symbol = ANY(%s) AND name IS NOT NULL AND name != ''",
                (list(symbols),),
            )
            names = {row[0]: row[1] for row in cur.fetchall()}
        conn.close()
        return names
    except Exception as exc:
        logger.warning("resolve_stock_names failed: %s", exc)
        return {}


_ST_NAME_PAT = re.compile(r"(^\*?ST)|(^ST)|退", re.IGNORECASE)


def _resolve_trade_st_flags(trades_df: pd.DataFrame, stock_names: dict[str, str]) -> dict[str, str]:
    """Build per-trade ST status keyed by 'YYYY-MM-DD|symbol'."""
    if trades_df.empty or "date" not in trades_df.columns or "symbol" not in trades_df.columns:
        return {}
    tdf = trades_df.copy()
    tdf["date"] = pd.to_datetime(tdf["date"], errors="coerce").dt.date
    tdf["symbol"] = tdf["symbol"].astype(str).str.lower()
    tdf = tdf.dropna(subset=["date", "symbol"])
    if tdf.empty:
        return {}

    out: dict[str, str] = {}
    for r in tdf.itertuples(index=False):
        k = f"{r.date.isoformat()}|{str(r.symbol).lower()}"
        out[k] = "-"

    symbols = sorted(set(tdf["symbol"].astype(str).tolist()))
    min_d = tdf["date"].min()
    max_d = tdf["date"].max()
    st_periods: dict[str, list[tuple[Any, Any]]] = {}
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
            cur.execute(
                """
                SELECT ts_code, start_date, end_date
                FROM pit_st_history
                WHERE ts_code = ANY(%s)
                  AND start_date <= %s
                  AND (end_date IS NULL OR end_date >= %s)
                """,
                (symbols, max_d, min_d),
            )
            for sym, sdt, edt in cur.fetchall():
                ss = str(sym).lower()
                st_periods.setdefault(ss, []).append((sdt, edt))
        conn.close()
    except Exception as exc:
        logger.warning("resolve_trade_st_flags pit_st_history failed: %s", exc)

    for r in tdf.itertuples(index=False):
        sym = str(r.symbol).lower()
        d = r.date
        k = f"{d.isoformat()}|{sym}"
        tagged = False
        for sdt, edt in st_periods.get(sym, []):
            s = pd.to_datetime(sdt, errors="coerce").date() if sdt is not None else None
            e = pd.to_datetime(edt, errors="coerce").date() if edt is not None else None
            if s is None:
                continue
            if d >= s and (e is None or d <= e):
                out[k] = "PIT_ST"
                tagged = True
                break
        if tagged:
            continue
        nm = str(stock_names.get(sym, ""))
        if nm and _ST_NAME_PAT.search(nm):
            out[k] = "NAME_ST_FALLBACK"
    return out


def _generate_experiment_label(base_cfg: dict[str, Any], overrides: dict[str, Any]) -> str:
    """Generate a human-readable label like 'SMA_CROSS 5/20 | CUSTOM 2只 | HFQ | 2024-01~06'."""
    wc = overrides.get("workbench_config") or {}

    strategy = str(wc.get("strategy") or base_cfg.get("signal", {}).get("strategy") or "UNKNOWN").upper()

    # Extract MA params — use ema config for EMA strategy, sma otherwise
    sig_gen = wc.get("signal_generation") or {}
    ma_key = "ema" if "EMA" in strategy else "sma"
    ma_cfg = sig_gen.get(ma_key) or wc.get(ma_key) or base_cfg.get("signal", {}).get(ma_key) or {}
    fast = ma_cfg.get("fast_ma") or ma_cfg.get("fast_period") or ""
    slow = ma_cfg.get("slow_ma") or ma_cfg.get("slow_period") or ""
    param_str = f" {fast}/{slow}" if fast and slow else ""

    # Universe mode + count
    u_mode = str(overrides.get("universe_mode") or wc.get("universe_mode") or "CUSTOM").upper()
    symbols = overrides.get("symbols") or []
    count_str = f" {len(symbols)}只" if symbols else ""

    # Price adj
    price_adj = str(overrides.get("price_adj") or wc.get("price_adj") or "hfq").upper()

    # Date range
    start = str(overrides.get("start_date") or base_cfg.get("universe", {}).get("start") or "")
    end = str(overrides.get("end_date") or base_cfg.get("universe", {}).get("end") or "")
    start_short = start[:7] if len(start) >= 7 else start
    end_short = end[5:7] if len(end) >= 7 else end
    date_str = f"{start_short}~{end_short}" if start and end else ""

    parts = [f"{strategy}{param_str}", f"{u_mode}{count_str}", price_adj]
    if date_str:
        parts.append(date_str)
    return " | ".join(parts)


def _write_nav_csv(results_dir: Path, result: dict[str, Any]) -> Path:
    out = results_dir / "nav.csv"
    if out.exists():
        return out

    candidates = [results_dir / "portfolio_daily.csv", results_dir / "equity_curve.csv"]
    for src in candidates:
        if not src.exists():
            continue
        try:
            df = pd.read_csv(src)
            date_col = "date" if "date" in df.columns else ("dt" if "dt" in df.columns else None)
            nav_col = None
            for c in ["nav", "strategy_nav", "equity", "equity_curve", "portfolio_value"]:
                if c in df.columns:
                    nav_col = c
                    break
            if nav_col is None:
                continue
            if date_col is None:
                dates = pd.to_datetime(df.index, errors="coerce").strftime("%Y-%m-%d")
            else:
                dates = pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y-%m-%d")
            nav = pd.to_numeric(df[nav_col], errors="coerce")
            out_df = pd.DataFrame({"date": dates, "nav": nav}).dropna(subset=["date", "nav"])
            if not out_df.empty:
                out_df.to_csv(out, index=False)
                return out
        except Exception:
            pass

    start = str(result.get("start_date") or "")
    end = str(result.get("end_date") or "")
    total_ret = float(_safe_float(result.get("total_return")) or 0.0)
    if start and end:
        pd.DataFrame([
            {"date": start, "nav": 1.0},
            {"date": end, "nav": 1.0 + total_ret},
        ]).to_csv(out, index=False)
    else:
        pd.DataFrame(columns=["date", "nav"]).to_csv(out, index=False)
    return out


def _build_counters(
    result: dict[str, Any],
    results_dir: Path,
    funnel_obj: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """从 result dict 和 results_dir 下的产物文件中提取完整 counters。"""
    counters: dict[str, Any] = {}

    # --- 引擎 metrics 直接透传的字段 ---
    counters["avg_positions"] = float(result.get("avg_positions", 0.0) or 0.0)
    counters["max_positions"] = int(result.get("max_positions", 10) or 10)
    counters["trend_slope_block_count"] = int(result.get("trend_slope_block_count", 0) or 0)
    counters["mf_rank_applied_rate"] = float(result.get("mf_rank_applied_rate", 0.0) or 0.0)
    counters["gate_on_rate"] = float(result.get("mf_gate_on_rate", result.get("gate_on_rate", 0.0)) or 0.0)
    _f = dict(funnel_obj or {})
    counters["raw_signal"] = int(_f.get("raw_signal", result.get("raw_signal", 0)) or 0)
    counters["blocked"] = int(_f.get("blocked", result.get("blocked", 0)) or 0)
    counters["orders"] = int(_f.get("orders", result.get("orders", 0)) or 0)
    counters["skipped"] = int(_f.get("skipped", result.get("skipped", 0)) or 0)
    counters["closed_trades"] = int(_f.get("closed_trades", result.get("closed_trades", 0)) or 0)

    # --- 从 portfolio_trades.csv 派生 exit 计数器 ---
    trades_path = results_dir / ARTIFACT_FILENAMES["trades"]
    atr_stop = 0
    atr_trail = 0
    atr_trail_update = 0
    reversal = 0
    time_exit = 0
    take_profit = 0
    fixed_stop_loss = 0
    if trades_path.exists():
        try:
            tdf = pd.read_csv(trades_path)
            if not tdf.empty and "reason_code" in tdf.columns:
                rc = tdf["reason_code"].astype(str).str.upper()
                atr_stop = int(rc.eq("ATR_STOP_LOSS").sum())
                atr_trail = int(rc.eq("ATR_TRAIL_EXIT").sum())
                reversal = int(rc.isin(["SIGNAL_REVERSE", "SMA_CROSS_DOWN", "EMA_CROSS_DOWN"]).sum())
                time_exit = int(rc.eq("TIME_EXIT").sum())
                take_profit = int(rc.eq("TAKE_PROFIT").sum())
                fixed_stop_loss = int(rc.eq("FIXED_STOP_LOSS").sum())
            # atr_trail_update_count: 从 triggered_rule 列推导
            if not tdf.empty and "triggered_rule" in tdf.columns:
                tr = tdf["triggered_rule"].astype(str).str.upper()
                atr_trail_update = int(
                    (
                        tr.str.contains("TRAIL", na=False)
                        & tr.str.contains("UPDATE|RAISE|ADJUST", regex=True, na=False)
                        & (~tr.str.contains("EXIT", na=False))
                    ).sum()
                )
        except Exception:
            pass
    counters["atr_stop_exit_count"] = atr_stop
    counters["atr_trail_exit_count"] = atr_trail
    counters["atr_trail_update_count"] = int(result.get("atr_trail_update_count", 0) or 0) or atr_trail_update
    counters["reversal_exit_count"] = reversal
    counters["time_exit_count"] = time_exit
    counters["take_profit_exit_count"] = int(result.get("take_profit_exit_count", 0) or 0) or take_profit
    counters["fixed_stop_loss_exit_count"] = int(result.get("fixed_stop_loss_exit_count", 0) or 0) or fixed_stop_loss
    counters["dd_reduced_count"] = int(result.get("dd_reduced_count", 0) or 0)

    # --- 从 candidate_diag_reason_counts 派生 constraint 计数器 ---
    diag = dict(result.get("candidate_diag_reason_counts") or {})
    counters["cash_skip_count"] = int(diag.get("SKIP_CASH_INSUFFICIENT", 0) or 0)
    counters["lot_skip_count"] = int(diag.get("SKIP_LOT_TOO_SMALL", 0) or 0)
    counters["cap_hit_single"] = int(diag.get("BLOCK_SINGLE_CAP", 0) or 0)
    counters["cap_hit_industry"] = int(diag.get("BLOCK_INDUSTRY_CAP", 0) or 0)
    counters["min_hold_block_count"] = int(diag.get("BLOCK_MIN_HOLD", 0) or 0)
    counters["cooldown_block_count"] = int(diag.get("BLOCK_COOLDOWN", 0) or 0)
    counters["entry_above_slow_ma_block_count"] = int(result.get("entry_above_slow_ma_block_count", 0) or 0)
    counters["entry_slope_block_count"] = int(result.get("entry_slope_block_count", 0) or 0)

    # --- regime router 计数器 ---
    counters["regime_trend_days"] = int(result.get("regime_trend_days", 0) or 0)
    counters["regime_mr_days"] = int(result.get("regime_mr_days", 0) or 0)
    counters["mr_rsi_oversold_buy_count"] = int(result.get("mr_rsi_oversold_buy_count", 0) or 0)
    counters["mr_rsi_overbought_sell_count"] = int(result.get("mr_rsi_overbought_sell_count", 0) or 0)
    counters["mr_stop_loss_count"] = int(result.get("mr_stop_loss_count", 0) or 0)
    counters["mr_time_exit_count"] = int(result.get("mr_time_exit_count", 0) or 0)
    counters["regime_filter_diagnostics"] = dict(result.get("regime_filter_diagnostics") or {})

    # --- MA200 市场过滤器计数器 ---
    counters["market_state_bull_days"] = int(result.get("market_state_bull_days", 0) or 0)
    counters["market_state_bear_days"] = int(result.get("market_state_bear_days", 0) or 0)
    counters["market_state_trans_down_days"] = int(result.get("market_state_trans_down_days", 0) or 0)
    counters["market_state_trans_up_days"] = int(result.get("market_state_trans_up_days", 0) or 0)
    counters["trade_mode_main_days"] = int(result.get("trade_mode_main_days", 0) or 0)
    counters["trade_mode_light_days"] = int(result.get("trade_mode_light_days", 0) or 0)
    counters["trade_mode_notrade_days"] = int(result.get("trade_mode_notrade_days", 0) or 0)

    # --- 派生字段 ---
    avg_pos = counters["avg_positions"]
    max_pos = counters["max_positions"]
    counters["slots_left"] = round(float(max_pos) - float(avg_pos), 1)

    return sanitize_json(counters)


def _resolve_backtest_range(base_cfg: dict[str, Any], overrides: dict[str, Any]) -> tuple[str, str]:
    uni = dict(base_cfg.get("universe") or {})
    start = str(overrides.get("start_date") or uni.get("start") or "").strip()
    end = str(overrides.get("end_date") or uni.get("end") or "").strip()
    return start, end


def _load_runtime_universe(results_dir: Path) -> dict[str, Any]:
    """Load compiled runtime universe from run_config.json when available."""
    p = results_dir / "run_config.json"
    if not p.exists():
        return {}
    try:
        obj = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    u = obj.get("universe")
    return dict(u) if isinstance(u, dict) else {}


def _load_last_close_map(
    *,
    symbols: list[str],
    start_date: str,
    end_date: str,
    base_cfg: dict[str, Any],
) -> dict[str, float]:
    if not symbols or not start_date or not end_date:
        return {}
    try:
        import psycopg
        from backend.core.data.mapping import safe_ident

        ds = dict(base_cfg.get("data_source") or {})
        sm = dict(base_cfg.get("schema_mapping") or {})
        stocks_table = str(ds.get("stocks_table") or "pams_ohlcv_daily")
        mp = dict(sm.get(stocks_table) or {})
        date_col = str(mp.get("date") or "trade_date")
        symbol_col = str(mp.get("symbol") or "symbol")
        close_col = str(mp.get("close") or "close")

        q = (
            f"SELECT {safe_ident(symbol_col)} AS symbol, {safe_ident(date_col)} AS trade_date, {safe_ident(close_col)} AS close "
            f"FROM {safe_ident(stocks_table)} "
            f"WHERE {safe_ident(date_col)} >= %s AND {safe_ident(date_col)} <= %s "
            f"AND {safe_ident(symbol_col)} = ANY(%s) "
            f"ORDER BY {safe_ident(date_col)} ASC"
        )
        conn = psycopg.connect(
            host=os.environ.get("PGHOST", os.environ.get("PAMS_PG_HOST", "pams-postgres")),
            port=int(os.environ.get("PGPORT", os.environ.get("PAMS_PG_PORT", "5432"))),
            dbname=os.environ.get("PGDATABASE", os.environ.get("PAMS_PG_DBNAME", "pams")),
            user=os.environ.get("PGUSER", os.environ.get("PAMS_PG_USER", "pams")),
            password=os.environ.get("PGPASSWORD", os.environ.get("PAMS_PG_PASSWORD", "")),
            autocommit=True,
        )
        with conn.cursor() as cur:
            cur.execute(q, (start_date, end_date, list({str(s).lower() for s in symbols})))
            rows = cur.fetchall()
        conn.close()
        if not rows:
            return {}
        df = pd.DataFrame(rows, columns=["symbol", "trade_date", "close"])
        df["symbol"] = df["symbol"].astype(str).str.lower()
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["trade_date", "close"]).sort_values(["symbol", "trade_date"])
        last_close = df.groupby("symbol", as_index=False).tail(1)
        return {str(r.symbol): float(r.close) for r in last_close.itertuples(index=False)}
    except Exception as exc:
        logger.warning("load_last_close_map failed: %s", exc)
        return {}


def ensure_standard_artifacts(
    *,
    results_dir: Path,
    result: dict[str, Any],
    base_cfg: dict[str, Any],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    results_dir.mkdir(parents=True, exist_ok=True)
    missing_fields: list[str] = []

    perf_obj = {
        "total_return": _safe_float(result.get("total_return")),
        "max_drawdown": _safe_float(result.get("max_drawdown")),
        "cagr": _safe_float(result.get("cagr")),
        "sharpe": _safe_float(result.get("sharpe")),
        "calmar": _safe_float(result.get("calmar")),
        "top10_profit_concentration": _safe_float(result.get("top10_profit_concentration")),
        "tier": str(result.get("tier") or ""),
        "trades": _safe_int(result.get("trades")),
        "turnover": _safe_float(result.get("turnover")),
    }
    perf_path = results_dir / ARTIFACT_FILENAMES["perf"]
    perf_path.write_text(json.dumps(sanitize_json(perf_obj), ensure_ascii=False, indent=2), encoding="utf-8")

    nav_path = _write_nav_csv(results_dir, result)
    try:
        nav_df = pd.read_csv(nav_path)
    except Exception:
        nav_df = pd.DataFrame()
    if nav_df.empty:
        missing_fields.append(MISSING_FIELD_KEYS["nav"])

    # 从 result dict 取 funnel 数据；若为 0 则尝试从 portfolio_trades.csv 派生
    raw_signal = int(_safe_int(result.get("raw_signal")) or 0)
    blocked = int(_safe_int(result.get("blocked")) or 0)
    orders = int(_safe_int(result.get("orders")) or 0)
    skipped = int(_safe_int(result.get("skipped")) or 0)
    closed_trades = int(_safe_int(result.get("closed_trades")) or 0)

    trades_path = results_dir / "portfolio_trades.csv"
    reason_rows: list[dict[str, Any]] = []
    if trades_path.exists():
        try:
            tdf = pd.read_csv(trades_path)
            if not tdf.empty and "side" in tdf.columns:
                buy_df = tdf[tdf["side"].astype(str).str.upper() == "BUY"]
                sell_df = tdf[tdf["side"].astype(str).str.upper() == "SELL"]
                if raw_signal == 0:
                    raw_signal = int(len(buy_df))
                if orders == 0:
                    orders = int(len(tdf))
                if closed_trades == 0:
                    closed_trades = int(len(sell_df))
            # 从 trades 构建 reason_code 汇总
            if not tdf.empty and "reason_code" in tdf.columns:
                rc_counts = tdf["reason_code"].astype(str).value_counts()
                reason_rows = [
                    {"reason_code": str(code), "count": int(cnt)}
                    for code, cnt in rc_counts.items()
                    if str(code).strip()
                ]
        except Exception:
            pass

    funnel_obj = {
        "raw_signal": raw_signal,
        "blocked": blocked,
        "orders": orders,
        "skipped": skipped,
        "closed_trades": closed_trades,
    }
    funnel_path = results_dir / ARTIFACT_FILENAMES["funnel"]
    pd.DataFrame([funnel_obj]).to_csv(funnel_path, index=False)
    if not any(result.get(k) is not None for k in ("raw_signal", "blocked", "orders", "skipped", "closed_trades")):
        missing_fields.append(MISSING_FIELD_KEYS["funnel"])

    reason_path = results_dir / ARTIFACT_FILENAMES["reason_codes"]
    if reason_rows:
        pd.DataFrame(reason_rows).to_csv(reason_path, index=False)
    else:
        pd.DataFrame(columns=["reason_code", "count"]).to_csv(reason_path, index=False)
        missing_fields.append(MISSING_FIELD_KEYS["reason_codes"])

    # stock_names.json — 从 trades 提取 symbols，查 DB 获取中文名
    stock_names: dict[str, str] = {}
    if trades_path.exists():
        try:
            tdf_sn = pd.read_csv(trades_path)
            if not tdf_sn.empty and "symbol" in tdf_sn.columns:
                unique_symbols = list(tdf_sn["symbol"].dropna().unique())
                stock_names = _resolve_stock_names(unique_symbols)
        except Exception:
            pass
    stock_names_path = results_dir / "stock_names.json"
    stock_names_path.write_text(json.dumps(stock_names, ensure_ascii=False, indent=2), encoding="utf-8")
    trade_st_flags_path = results_dir / "trade_st_flags.json"
    trade_st_flags: dict[str, str] = {}
    if trades_path.exists():
        try:
            tdf_st = pd.read_csv(trades_path)
            trade_st_flags = _resolve_trade_st_flags(tdf_st, stock_names)
        except Exception as exc:
            logger.warning("build trade_st_flags failed: %s", exc)
            trade_st_flags = {}
    trade_st_flags_path.write_text(json.dumps(trade_st_flags, ensure_ascii=False, indent=2), encoding="utf-8")

    symbol_perf_csv_path = results_dir / ARTIFACT_FILENAMES["symbol_performance"]
    symbol_perf_json_path = results_dir / "symbol_performance.json"
    try:
        if trades_path.exists():
            tdf_sp = pd.read_csv(trades_path)
            if not tdf_sp.empty and "symbol" in tdf_sp.columns:
                symbols = [str(x).lower() for x in tdf_sp["symbol"].dropna().unique().tolist()]
                start_s, end_s = _resolve_backtest_range(base_cfg, overrides)
                last_close_map = _load_last_close_map(
                    symbols=symbols,
                    start_date=start_s,
                    end_date=end_s,
                    base_cfg=base_cfg,
                )
                last_date = None
                try:
                    nav_df = pd.read_csv(nav_path)
                    if not nav_df.empty and "date" in nav_df.columns:
                        ts = pd.to_datetime(nav_df["date"], errors="coerce").dropna().max()
                        last_date = ts.date() if pd.notna(ts) else None
                except Exception:
                    last_date = None
                sp_df = build_symbol_performance(
                    trades_df=tdf_sp,
                    last_close_map=last_close_map,
                    last_date=last_date,
                )
            else:
                sp_df = pd.DataFrame()
        else:
            sp_df = pd.DataFrame()
        sp_df.to_csv(symbol_perf_csv_path, index=False)
        if sp_df.empty:
            missing_fields.append(MISSING_FIELD_KEYS["symbol_performance"])
        symbol_perf_json_path.write_text(
            json.dumps({"rows": sanitize_json(sp_df.to_dict(orient="records"))}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("build symbol_performance failed: %s", exc)
        pd.DataFrame().to_csv(symbol_perf_csv_path, index=False)
        symbol_perf_json_path.write_text(json.dumps({"rows": []}, ensure_ascii=False, indent=2), encoding="utf-8")
        missing_fields.append(MISSING_FIELD_KEYS["symbol_performance"])

    config_path = results_dir / ARTIFACT_FILENAMES["config"]
    config_path.write_text(
        json.dumps(
            sanitize_json({"base_config": base_cfg, "overrides": overrides}),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    runtime_uni = _load_runtime_universe(results_dir)
    original_wb = dict((overrides.get("original_workbench_config") or {})) if isinstance(overrides.get("original_workbench_config"), dict) else {}
    wb_uni = dict(original_wb.get("universe") or {}) if isinstance(original_wb.get("universe"), dict) else {}
    base_uni = dict(base_cfg.get("universe") or {})

    def _pick_with_source(candidates: list[tuple[Any, str]]) -> tuple[Any, str, bool]:
        if not candidates:
            return None, "missing", True
        primary = candidates[0][1]
        for value, source in candidates:
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            return value, source, source != primary
        return None, "missing", True

    start_v, start_src, start_fallback = _pick_with_source([
        (runtime_uni.get("start"), "run_config.universe.start"),
        (wb_uni.get("start"), "original_workbench_config.universe.start"),
        (overrides.get("start_date"), "overrides.start_date"),
        (base_uni.get("start"), "base_config.universe.start"),
    ])
    end_v, end_src, end_fallback = _pick_with_source([
        (runtime_uni.get("end"), "run_config.universe.end"),
        (wb_uni.get("end"), "original_workbench_config.universe.end"),
        (overrides.get("end_date"), "overrides.end_date"),
        (base_uni.get("end"), "base_config.universe.end"),
    ])
    benchmark_v, benchmark_src, benchmark_fallback = _pick_with_source([
        (runtime_uni.get("benchmark"), "run_config.universe.benchmark"),
        (wb_uni.get("benchmark"), "original_workbench_config.universe.benchmark"),
        (overrides.get("benchmark"), "overrides.benchmark"),
        (base_uni.get("benchmark"), "base_config.universe.benchmark"),
    ])

    run_meta_obj = {
        "exp_id": str(result.get("exp_id") or ""),
        "tier": str(result.get("tier") or "T0"),
        "status": str(result.get("status") or "OK"),
        "created_at": datetime.now().isoformat(),
        "data": {
            "start": start_v,
            "end": end_v,
            "benchmark": benchmark_v,
            "compare_symbol": overrides.get("compare_symbol") or base_cfg.get("universe", {}).get("benchmark_compare_symbol"),
            "universe_limit": _safe_int(overrides.get("universe_limit")),
        },
        "code": {
            "engine_mode": str(overrides.get("engine_mode") or "VECTOR_FAST_STRICT"),
            "execution_profile": str(overrides.get("execution_profile") or "tradable"),
            "fast_mode": bool(overrides.get("fast_mode", True)),
        },
        "counters": _build_counters(result, results_dir, funnel_obj),
        "price_adj_mode": str(result.get("price_adj_mode") or "hfq"),
        "adj_factor_stats": sanitize_json(result.get("adj_factor_stats") or {}),
        "missing_fields": sorted(set(missing_fields)),
        "legacy_hits": {"reason_codes_filename": 0, "counters_field_alias": 0},
        "report_consistency": {
            "sources": {
                "start": start_src,
                "end": end_src,
                "benchmark": benchmark_src,
                "funnel": "funnel.csv",
            },
            "fallbacks": {
                "start": bool(start_fallback),
                "end": bool(end_fallback),
                "benchmark": bool(benchmark_fallback),
            },
            "config_source": str(overrides.get("config_source") or "unknown"),
            "config_conflict_policy": str(overrides.get("config_conflict_policy") or ""),
        },
    }
    # 注入 universe resolver 元数据（来自 experiment_runner）
    u_meta = result.get("universe_meta")
    if isinstance(u_meta, dict):
        run_meta_obj["universe"] = sanitize_json(u_meta)
        run_meta_obj["data"]["universe_mode"] = str(u_meta.get("universe_mode") or "CUSTOM")
    run_meta_path = results_dir / ARTIFACT_FILENAMES["run_meta"]
    run_meta_path.write_text(json.dumps(sanitize_json(run_meta_obj), ensure_ascii=False, indent=2), encoding="utf-8")

    # 写入 audit.json（审计检查点数据）
    audit_data = (result.get("metrics") or {}).get("audit")
    audit_rel = None
    if isinstance(audit_data, dict):
        try:
            # 补充 exp_id（引擎阶段尚不知道）
            audit_data["exp_id"] = str(result.get("exp_id") or "")
            audit_path = results_dir / "audit.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False, indent=2), encoding="utf-8")
            audit_rel = _to_rel(audit_path, results_dir)
        except Exception as exc:
            logger.warning("Failed to write audit.json: %s", exc)

    artifacts = {
        "perf": _to_rel(perf_path, results_dir),
        "nav": _to_rel(nav_path, results_dir),
        "funnel": _to_rel(funnel_path, results_dir),
        "reason_codes": _to_rel(reason_path, results_dir),
        "config": _to_rel(config_path, results_dir),
        "run_meta": _to_rel(run_meta_path, results_dir),
        "stock_names": _to_rel(stock_names_path, results_dir),
        "trade_st_flags": _to_rel(trade_st_flags_path, results_dir),
        "symbol_performance": _to_rel(symbol_perf_csv_path, results_dir),
        "audit": audit_rel,
    }
    # 如果引擎已写出 trades CSV，也加入 artifacts 映射
    if trades_path.exists():
        artifacts["trades"] = _to_rel(trades_path, results_dir)
    # 如果引擎已写出 daily CSV，也加入 artifacts 映射（供报告生成使用）
    daily_path = results_dir / ARTIFACT_FILENAMES["daily"]
    if daily_path.exists():
        artifacts["daily"] = _to_rel(daily_path, results_dir)

    out = dict(result)
    out["status"] = str(out.get("status") or "OK")
    out["artifacts"] = artifacts
    return sanitize_json(out)


def write_manifest(results_dir: Path, result: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    manifest = {
        "exp_id": str(result.get("exp_id") or ""),
        "status": str(result.get("status") or "OK"),
        "created_at": datetime.now().isoformat(),
        "artifacts": dict(result.get("artifacts") or {}),
        "metrics": {
            "total_return": _safe_float(result.get("total_return")),
            "max_drawdown": _safe_float(result.get("max_drawdown")),
            "cagr": _safe_float(result.get("cagr")),
            "sharpe": _safe_float(result.get("sharpe")),
            "trades": _safe_int(result.get("trades")),
            "turnover": _safe_float(result.get("turnover")),
        },
    }
    path = results_dir / "manifest.json"
    path.write_text(json.dumps(sanitize_json(manifest), ensure_ascii=False, indent=2), encoding="utf-8")
    return path, manifest


def _append_to_experiment_index(
    results_dir: Path,
    result: dict[str, Any],
    base_cfg: dict[str, Any],
    overrides: dict[str, Any],
) -> None:
    """Append an experiment summary to outputs/experiments/index.json."""
    experiments_root = results_dir.parent
    index_path = experiments_root / "index.json"

    # Read existing index
    entries: list[dict[str, Any]] = []
    if index_path.exists():
        try:
            entries = json.loads(index_path.read_text(encoding="utf-8"))
            if not isinstance(entries, list):
                entries = []
        except Exception:
            entries = []

    exp_id = str(result.get("exp_id") or "")
    label = _generate_experiment_label(base_cfg, overrides)
    has_report = (results_dir / "report.html").exists()

    entry = {
        "exp_id": exp_id,
        "label": label,
        "created_at": datetime.now().isoformat(),
        "status": str(result.get("status") or "OK"),
        "total_return": _safe_float(result.get("total_return")),
        "max_drawdown": _safe_float(result.get("max_drawdown")),
        "sharpe": _safe_float(result.get("sharpe")),
        "trades": _safe_int(result.get("trades")),
        "has_report": has_report,
    }

    # Remove existing entry for same exp_id (re-run)
    entries = [e for e in entries if e.get("exp_id") != exp_id]
    entries.append(sanitize_json(entry))

    index_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def stabilize_experiment_result(
    *,
    bt_root: Path,
    result: dict[str, Any],
    base_cfg: dict[str, Any],
    overrides: dict[str, Any],
    run_profile_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    out = dict(result or {})

    results_dir = _resolve_runtime_path(str(out.get("results_dir") or ""), bt_root)
    if results_dir is None:
        results_dir = (_results_root() / "experiments" / str(out.get("exp_id") or "exp_unknown")).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    out["exp_id"] = str(out.get("exp_id") or "")
    out["results_dir"] = str(results_dir)
    out["status"] = str(out.get("status") or "OK")

    out = ensure_standard_artifacts(
        results_dir=results_dir,
        result=out,
        base_cfg=base_cfg,
        overrides=overrides,
    )
    # Generate report.html (failure does not block)
    report_ok = False
    try:
        from backend.core.report.report_generator import generate_report
        generate_report(str(results_dir))
        report_ok = True
    except Exception as exc:
        logger.warning("Report generation failed: %s", exc)

    # Update artifacts with report path
    artifacts = dict(out.get("artifacts") or {})
    if report_ok:
        artifacts["report"] = "report.html"
    else:
        artifacts["report"] = None
    out["artifacts"] = artifacts

    manifest_path, manifest_obj = write_manifest(results_dir, out)

    files = dict(out.get("files") or {})
    files["manifest"] = _to_rel(manifest_path, results_dir)
    out["files"] = files
    out["manifest"] = manifest_obj

    if run_profile_summary:
        out["run_profile_summary"] = run_profile_summary

    # Append to experiment index
    try:
        _append_to_experiment_index(results_dir, out, base_cfg, overrides)
    except Exception as exc:
        logger.warning("Failed to update experiment index: %s", exc)

    return sanitize_json(out)
