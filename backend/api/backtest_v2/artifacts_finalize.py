from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from backend.api.backtest_v2.artifacts_diagnostics import (
    _build_alpha_funnel,
    _build_candidate_signals,
    _build_recent_cash_blocked_buys,
    _build_counters,
    _build_score_diagnostics,
    _resolve_stock_names,
    _resolve_trade_st_flags,
    _sanitize_historical_stock_names,
)
from backend.api.backtest_v2.artifacts_io import (
    _safe_float,
    _safe_int,
    _safe_read_json,
    _to_rel,
    _write_canonical_csv,
)
from backend.api.backtest_v2.artifacts_manifest import _generate_experiment_label
from backend.api.backtest_v2.artifacts_stage_summary import (
    _extract_stage_pipeline_summary,
    _extract_stage_summary,
)
from backend.api.backtest_v2.protocol import ARTIFACT_FILENAMES, MISSING_FIELD_KEYS
from backend.api.shared.json_utils import sanitize_json
from backend.core.analytics.symbol_performance import build_symbol_performance
from backend.core.audit.experiment_audit import merge_experiment_audit
from backend.core.audit.regime_audit import write_regime_audit_artifacts
from backend.core.audit.research_audit import build_research_audit
from backend.core.config.asset_profiles import build_asset_context
from backend.core.config.models import DataSourceConfig
from backend.core.stage_pipeline.adapters.lineage import LINEAGE_LEDGER_COLUMNS

logger = logging.getLogger(__name__)


def _write_nav_csv(results_dir: Path, result: dict[str, Any]) -> Path:
    out = results_dir / "nav.csv"
    if out.exists():
        return out
    effective_start = str(result.get("effective_execution_start_date") or "").strip()
    for src in (results_dir / "portfolio_daily.csv", results_dir / "equity_curve.csv"):
        if not src.exists():
            continue
        try:
            df = pd.read_csv(src)
            date_col = "date" if "date" in df.columns else ("dt" if "dt" in df.columns else None)
            nav_col = next((c for c in ["nav", "strategy_nav", "equity", "equity_curve", "portfolio_value"] if c in df.columns), None)
            if nav_col is None:
                continue
            dates = (
                pd.to_datetime(df.index, errors="coerce").strftime("%Y-%m-%d")
                if date_col is None
                else pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y-%m-%d")
            )
            nav = pd.to_numeric(df[nav_col], errors="coerce")
            out_df = pd.DataFrame({"date": dates, "nav": nav}).dropna(subset=["date", "nav"])
            if effective_start and not out_df.empty:
                date_ts = pd.to_datetime(out_df["date"], errors="coerce").dt.normalize()
                out_df = out_df.loc[date_ts >= pd.Timestamp(effective_start).normalize()].copy()
                if not out_df.empty:
                    nav0 = float(pd.to_numeric(out_df["nav"], errors="coerce").iloc[0])
                    if nav0 > 0:
                        out_df["nav"] = pd.to_numeric(out_df["nav"], errors="coerce") / nav0
            if not out_df.empty:
                out_df.to_csv(out, index=False)
                return out
        except Exception:
            pass

    start = str(result.get("start_date") or "")
    end = str(result.get("end_date") or "")
    total_ret = float(_safe_float(result.get("total_return")) or 0.0)
    rows = [{"date": start, "nav": 1.0}, {"date": end, "nav": 1.0 + total_ret}] if start and end else []
    pd.DataFrame(rows, columns=["date", "nav"]).to_csv(out, index=False)
    return out


def _resolve_backtest_range(base_cfg: dict[str, Any], overrides: dict[str, Any]) -> tuple[str, str]:
    uni = dict(base_cfg.get("universe") or {})
    return (
        str(overrides.get("start_date") or uni.get("start") or "").strip(),
        str(overrides.get("end_date") or uni.get("end") or "").strip(),
    )


def _resolve_regime_meta(base_cfg: dict[str, Any], runtime_cfg: dict[str, Any]) -> dict[str, Any]:
    base_regime = dict(base_cfg.get("regime_engine") or {}) if isinstance(base_cfg.get("regime_engine"), dict) else {}
    runtime_regime = dict(runtime_cfg.get("regime_engine") or {}) if isinstance(runtime_cfg.get("regime_engine"), dict) else {}
    merged = sanitize_json({**base_regime, **runtime_regime})
    fallback = dict(merged.get("fallback") or {})
    engine = str(merged.get("engine") or "ma200_legacy").strip() or "ma200_legacy"
    if engine == "ma200_legacy":
        regime_semantics = "legacy_price_filter"
    elif engine == "weekly_five_state":
        regime_semantics = "weekly_five_state_regime"
    else:
        regime_semantics = "formal_multi_factor_regime"
    required_blocks = fallback.get("required_blocks")
    if not isinstance(required_blocks, list):
        required_blocks = []
    on_feature_unavailable = str(
        fallback.get("on_feature_unavailable") or ("ma200_legacy" if engine in {"market_regime_framework", "weekly_five_state"} else "disabled")
    ).strip()
    emit_feature_availability = bool(
        fallback.get("emit_feature_availability", engine in {"market_regime_framework", "weekly_five_state"})
    )
    return sanitize_json(
        {
            **dict(merged),
            "engine": engine,
            "regime_semantics": regime_semantics,
            "feature_availability_contract": {
                "required_blocks": [str(item) for item in required_blocks if str(item or "").strip()],
                "on_feature_unavailable": on_feature_unavailable,
                "emit_feature_availability": emit_feature_availability,
            },
        }
    )


def _load_runtime_universe(results_dir: Path) -> dict[str, Any]:
    path = results_dir / "run_config.json"
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    universe = obj.get("universe")
    return dict(universe) if isinstance(universe, dict) else {}


def _load_runtime_config(results_dir: Path) -> dict[str, Any]:
    path = results_dir / "run_config.json"
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return dict(obj) if isinstance(obj, dict) else {}


def _empty_close_history_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["symbol", "trade_date", "close"])


def _load_close_history_df(
    *,
    symbols: list[str],
    start_date: str,
    end_date: str,
    base_cfg: dict[str, Any],
) -> pd.DataFrame:
    if not symbols or not start_date or not end_date:
        return _empty_close_history_frame()
    try:
        import psycopg
        from backend.core.data.mapping import safe_ident

        ds = dict(base_cfg.get("data_source") or {})
        sm = dict(base_cfg.get("schema_mapping") or {})
        ds_cfg = DataSourceConfig(**ds)
        stocks_table = ds_cfg.resolved_stocks_table()
        mapping_table = ds_cfg.resolved_stocks_mapping_table()
        mp = dict(sm.get(mapping_table) or {})
        date_col = str(mp.get("date") or "trade_date")
        symbol_col = str(mp.get("symbol") or "symbol")
        close_col = str(mp.get("close") or "close")

        query = (
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
            cur.execute(query, (start_date, end_date, list({str(s).lower() for s in symbols})))
            rows = cur.fetchall()
        conn.close()
        if not rows:
            return _empty_close_history_frame()
        df = pd.DataFrame(rows, columns=["symbol", "trade_date", "close"])
        df["symbol"] = df["symbol"].astype(str).str.lower()
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        return df.dropna(subset=["trade_date", "close"]).sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    except Exception as exc:
        logger.warning("load_close_history_df failed: %s", exc)
        return _empty_close_history_frame()


def _last_close_map_from_history(df: pd.DataFrame | None) -> dict[str, float]:
    if df is None or df.empty:
        return {}
    last_close = df.groupby("symbol", as_index=False).tail(1)
    return {str(row.symbol): float(row.close) for row in last_close.itertuples(index=False)}


def _empty_symbol_performance_frame() -> pd.DataFrame:
    return build_symbol_performance(trades_df=pd.DataFrame(), last_close_map={}, last_date=None)


def _resolve_validation_audit_ref(
    *,
    explicit_ref: dict[str, Any] | None,
    result: dict[str, Any],
    overrides: dict[str, Any],
) -> dict[str, Any] | None:
    for candidate in (explicit_ref, result.get("validation_audit_ref"), overrides.get("validation_audit_ref")):
        if isinstance(candidate, dict) and candidate:
            return sanitize_json(dict(candidate))
    return None


def _finalize_research_audit(
    *,
    bt_root: Path,
    results_dir: Path,
    result: dict[str, Any],
    base_cfg: dict[str, Any],
    overrides: dict[str, Any],
    validation_audit_ref: dict[str, Any] | None,
) -> dict[str, Any] | None:
    audit_path = results_dir / "audit.json"
    audit_payload = _safe_read_json(audit_path)
    stage_summary_obj = _extract_stage_summary(result)
    stage_pipeline_obj = _extract_stage_pipeline_summary(result, stage_summary_obj)
    if not isinstance(audit_payload, dict):
        base_audit = (result.get("metrics") or {}).get("audit")
        if not isinstance(base_audit, dict):
            base_audit = {}
        audit_payload = merge_experiment_audit(
            base_audit,
            stage_pipeline=stage_pipeline_obj if isinstance(stage_pipeline_obj, dict) else None,
            stage_summary=stage_summary_obj if isinstance(stage_summary_obj, dict) else None,
            exp_id=str(result.get("exp_id") or ""),
        )
    if not isinstance(audit_payload, dict):
        audit_payload = {}

    research_audit = build_research_audit(
        results_dir=results_dir,
        result=result,
        manifest=result.get("manifest") if isinstance(result.get("manifest"), dict) else None,
        stage_summary=stage_summary_obj if isinstance(stage_summary_obj, dict) else None,
        stage_pipeline=stage_pipeline_obj if isinstance(stage_pipeline_obj, dict) else None,
        validation_audit_ref=_resolve_validation_audit_ref(
            explicit_ref=validation_audit_ref,
            result=result,
            overrides=overrides,
        ),
        bt_root=bt_root,
        artifact_presence={
            "run_meta": (results_dir / "run_meta.json").exists(),
            "manifest": (results_dir / "manifest.json").exists(),
            "audit": True,
        },
    )
    audit_payload["research_audit"] = sanitize_json(research_audit)
    audit_path.write_text(json.dumps(sanitize_json(audit_payload), ensure_ascii=False, indent=2), encoding="utf-8")
    return audit_payload


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
        "candidate_ready_date": str(result.get("candidate_ready_date") or ""),
        "effective_signal_start_date": str(result.get("effective_signal_start_date") or ""),
        "effective_execution_start_date": str(result.get("effective_execution_start_date") or ""),
        "metrics_from_effective_start": bool(result.get("metrics_from_effective_start", False)),
        "effective_observation_days": _safe_int(result.get("effective_observation_days")),
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
            if not tdf.empty and "reason_code" in tdf.columns:
                reason_rows = [
                    {"reason_code": str(code), "count": int(count)}
                    for code, count in tdf["reason_code"].astype(str).value_counts().items()
                    if str(code).strip()
                ]
        except Exception:
            pass

    funnel_obj = {"raw_signal": raw_signal, "blocked": blocked, "orders": orders, "skipped": skipped, "closed_trades": closed_trades}
    funnel_path = results_dir / ARTIFACT_FILENAMES["funnel"]
    pd.DataFrame([funnel_obj]).to_csv(funnel_path, index=False)
    if not any(result.get(k) is not None for k in ("raw_signal", "blocked", "orders", "skipped", "closed_trades")):
        missing_fields.append(MISSING_FIELD_KEYS["funnel"])

    reason_path = results_dir / ARTIFACT_FILENAMES["reason_codes"]
    pd.DataFrame(reason_rows or [], columns=["reason_code", "count"]).to_csv(reason_path, index=False)
    if not reason_rows:
        missing_fields.append(MISSING_FIELD_KEYS["reason_codes"])

    stock_names_path = results_dir / "stock_names.json"
    trade_st_flags_path = results_dir / "trade_st_flags.json"
    stock_names: dict[str, str] = {}
    trade_st_flags: dict[str, str] = {}
    if trades_path.exists():
        try:
            tdf_trades = pd.read_csv(trades_path)
            if not tdf_trades.empty and "symbol" in tdf_trades.columns:
                raw_stock_names = _resolve_stock_names(list(tdf_trades["symbol"].dropna().unique()))
                trade_st_flags = _resolve_trade_st_flags(tdf_trades, raw_stock_names)
                stock_names = _sanitize_historical_stock_names(tdf_trades, raw_stock_names, trade_st_flags)
        except Exception as exc:
            logger.warning("build stock_names/trade_st_flags failed: %s", exc)
    stock_names_path.write_text(json.dumps(stock_names, ensure_ascii=False, indent=2), encoding="utf-8")
    trade_st_flags_path.write_text(json.dumps(trade_st_flags, ensure_ascii=False, indent=2), encoding="utf-8")

    orders_path = _write_canonical_csv(
        trades_path,
        results_dir / ARTIFACT_FILENAMES["orders"],
        empty_columns=["date", "symbol", "side", "price", "qty", "reason_code", "exit_owner", "entry_alpha_id", "entry_sleeve_id", "entry_reason_code", "entry_date"],
    )
    candidate_signals_path, candidate_signals_df = _build_candidate_signals(results_dir)
    cash_blocked_recent_path = _build_recent_cash_blocked_buys(results_dir, candidate_signals_df)
    alpha_funnel_path = _build_alpha_funnel(results_dir, candidate_signals_df)
    score_diagnostics_path = _build_score_diagnostics(results_dir, candidate_signals_df)

    symbol_perf_csv_path = results_dir / ARTIFACT_FILENAMES["symbol_performance"]
    symbol_perf_json_path = results_dir / "symbol_performance.json"
    try:
        if trades_path.exists():
            tdf_sp = pd.read_csv(trades_path)
            if not tdf_sp.empty and "symbol" in tdf_sp.columns:
                symbols = [str(x).lower() for x in tdf_sp["symbol"].dropna().unique().tolist()]
                last_date = None
                try:
                    nav_df = pd.read_csv(nav_path)
                    if not nav_df.empty and "date" in nav_df.columns:
                        ts = pd.to_datetime(nav_df["date"], errors="coerce").dropna().max()
                        last_date = ts.date() if pd.notna(ts) else None
                except Exception:
                    pass
                history_start, history_end = _resolve_backtest_range(base_cfg, overrides)
                trade_date_col = "date" if "date" in tdf_sp.columns else ("trade_date" if "trade_date" in tdf_sp.columns else None)
                if trade_date_col is not None:
                    trade_dates = pd.to_datetime(tdf_sp[trade_date_col], errors="coerce").dropna()
                    if not trade_dates.empty:
                        history_start = trade_dates.min().date().isoformat()
                        history_end_date = trade_dates.max().date()
                        if last_date is not None:
                            history_end_date = max(history_end_date, last_date)
                        history_end = history_end_date.isoformat()
                close_history_df = _load_close_history_df(symbols=symbols, start_date=history_start, end_date=history_end, base_cfg=base_cfg)
                sp_df = build_symbol_performance(
                    trades_df=tdf_sp,
                    last_close_map=_last_close_map_from_history(close_history_df),
                    last_date=last_date,
                    daily_close_df=close_history_df,
                )
            else:
                sp_df = pd.DataFrame()
        else:
            sp_df = _empty_symbol_performance_frame()
        if sp_df.empty and not list(sp_df.columns):
            sp_df = _empty_symbol_performance_frame()
        sp_df.to_csv(symbol_perf_csv_path, index=False)
        if sp_df.empty:
            missing_fields.append(MISSING_FIELD_KEYS["symbol_performance"])
        symbol_perf_json_path.write_text(json.dumps({"rows": sanitize_json(sp_df.to_dict(orient="records"))}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("build symbol_performance failed: %s", exc)
        _empty_symbol_performance_frame().to_csv(symbol_perf_csv_path, index=False)
        symbol_perf_json_path.write_text(json.dumps({"rows": []}, ensure_ascii=False, indent=2), encoding="utf-8")
        missing_fields.append(MISSING_FIELD_KEYS["symbol_performance"])

    config_path = results_dir / ARTIFACT_FILENAMES["config"]
    config_path.write_text(json.dumps(sanitize_json({"base_config": base_cfg, "overrides": overrides}), ensure_ascii=False, indent=2), encoding="utf-8")

    runtime_cfg = _load_runtime_config(results_dir)
    runtime_uni = _load_runtime_universe(results_dir)
    regime_meta = _resolve_regime_meta(base_cfg, runtime_cfg)
    original_wb = dict((overrides.get("original_workbench_config") or {})) if isinstance(overrides.get("original_workbench_config"), dict) else {}
    wb_uni = dict(original_wb.get("universe") or {}) if isinstance(original_wb.get("universe"), dict) else {}
    base_uni = dict(base_cfg.get("universe") or {})
    runtime_ds = dict(runtime_cfg.get("data_source") or {}) if isinstance(runtime_cfg.get("data_source"), dict) else {}
    base_ds = dict(base_cfg.get("data_source") or {}) if isinstance(base_cfg.get("data_source"), dict) else {}
    ds_cfg = DataSourceConfig(**{**base_ds, **runtime_ds})
    resolved_data_role = str(runtime_ds.get("data_role") or overrides.get("data_role") or base_ds.get("data_role") or ds_cfg.resolved_data_role())
    resolved_stocks_table = ds_cfg.resolved_stocks_table()
    resolved_stocks_mapping_table = ds_cfg.resolved_stocks_mapping_table()

    def _pick_with_source(candidates: list[tuple[Any, str]]) -> tuple[Any, str]:
        for value, source in candidates:
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            return value, source
        return None, "missing"

    start_v, start_src = _pick_with_source([(runtime_uni.get("start"), "run_config.universe.start"), (wb_uni.get("start"), "original_workbench_config.universe.start"), (overrides.get("start_date"), "overrides.start_date"), (base_uni.get("start"), "base_config.universe.start")])
    end_v, end_src = _pick_with_source([(runtime_uni.get("end"), "run_config.universe.end"), (wb_uni.get("end"), "original_workbench_config.universe.end"), (overrides.get("end_date"), "overrides.end_date"), (base_uni.get("end"), "base_config.universe.end")])
    benchmark_v, benchmark_src = _pick_with_source([(runtime_uni.get("benchmark"), "run_config.universe.benchmark"), (wb_uni.get("benchmark"), "original_workbench_config.universe.benchmark"), (overrides.get("benchmark"), "overrides.benchmark"), (base_uni.get("benchmark"), "base_config.universe.benchmark")])

    resolved_config_mode = str(overrides.get("resolved_config_mode") or result.get("resolved_config_mode") or "none")
    resolved_config_id = overrides.get("resolved_config_id") or result.get("resolved_config_id")
    resolved_config_hash = str(overrides.get("resolved_config_hash") or result.get("resolved_config_hash") or "").strip()
    resolved_config_meta_raw = overrides.get("resolved_config_meta")
    if not isinstance(resolved_config_meta_raw, dict):
        resolved_config_meta_raw = result.get("resolved_config_meta")
    resolved_config_meta = sanitize_json(dict(resolved_config_meta_raw)) if isinstance(resolved_config_meta_raw, dict) else None
    resolved_universe_mode = str((resolved_config_meta or {}).get("universe_mode") or runtime_uni.get("universe_mode") or wb_uni.get("universe_mode") or overrides.get("universe_mode") or (result.get("universe_meta") or {}).get("universe_mode") or "").strip()
    if resolved_config_meta is not None and resolved_universe_mode and not resolved_config_meta.get("universe_mode"):
        resolved_config_meta = dict(resolved_config_meta)
        resolved_config_meta["universe_mode"] = resolved_universe_mode
    if resolved_config_meta is not None and resolved_data_role and not resolved_config_meta.get("data_role"):
        resolved_config_meta = dict(resolved_config_meta)
        resolved_config_meta["data_role"] = resolved_data_role
    asset_context = sanitize_json(
        build_asset_context(
            overrides.get("asset_scope"),
            config_json=base_cfg,
            metadata_scope=(resolved_config_meta or {}).get("asset_scope"),
        )
    )

    stage_summary_obj = _extract_stage_summary(result)
    stage_pipeline_obj = _extract_stage_pipeline_summary(result, stage_summary_obj)
    stage_summary_rel = None
    if isinstance(stage_summary_obj, dict) and stage_summary_obj:
        stage_summary_path = results_dir / ARTIFACT_FILENAMES["stage_summary"]
        stage_summary_path.write_text(json.dumps(sanitize_json(stage_summary_obj), ensure_ascii=False, indent=2), encoding="utf-8")
        stage_summary_rel = _to_rel(stage_summary_path, results_dir)

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
            "asset_scope": str(asset_context.get("asset_scope") or "cn_a_equity"),
            "data_role": resolved_data_role,
            "stocks_table": resolved_stocks_table,
            "stocks_mapping_table": resolved_stocks_mapping_table,
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
        "warmup": sanitize_json(result.get("warmup_analysis") or {}),
        "asset_context": asset_context,
        "regime": regime_meta,
        "report_consistency": {
            "sources": {"start": start_src, "end": end_src, "benchmark": benchmark_src, "funnel": "funnel.csv"},
            "config_source": str(overrides.get("config_source") or "unknown"),
            "config_conflict_policy": str(overrides.get("config_conflict_policy") or ""),
            "resolved_config_mode": resolved_config_mode,
            "resolved_config_id": str(resolved_config_id or "") or None,
            "resolved_config_hash": resolved_config_hash or None,
            "data_role": resolved_data_role,
            "stocks_table": resolved_stocks_table,
            "stocks_mapping_table": resolved_stocks_mapping_table,
            "resolved_config_source_type": str((resolved_config_meta or {}).get("source_type") or ""),
            "resolved_config_owner": str((resolved_config_meta or {}).get("owner") or ""),
            "resolved_config_schema_version": str((resolved_config_meta or {}).get("schema_version") or ""),
            "resolved_config_source": str((resolved_config_meta or {}).get("config_source") or overrides.get("config_source") or ""),
            "resolved_config_compiler_hash": str((resolved_config_meta or {}).get("config_hash") or resolved_config_hash or ""),
            "resolved_config_meta": resolved_config_meta,
            "regime_engine": str(regime_meta.get("engine") or "ma200_legacy"),
            "regime_semantics": str(regime_meta.get("regime_semantics") or "legacy_price_filter"),
        },
    }
    if isinstance(result.get("universe_meta"), dict):
        run_meta_obj["universe"] = sanitize_json(result["universe_meta"])
        run_meta_obj["data"]["universe_mode"] = str(result["universe_meta"].get("universe_mode") or "CUSTOM")
    if isinstance(result.get("data_bundle"), dict):
        run_meta_obj["data_bundle"] = sanitize_json(result["data_bundle"])
    if isinstance(overrides.get("candidate_context"), dict) and overrides.get("candidate_context"):
        run_meta_obj["candidate"] = sanitize_json(overrides["candidate_context"])
    if isinstance(stage_pipeline_obj, dict) and stage_pipeline_obj:
        run_meta_obj["stage_pipeline"] = sanitize_json(stage_pipeline_obj)
    run_meta_path = results_dir / ARTIFACT_FILENAMES["run_meta"]
    run_meta_path.write_text(json.dumps(sanitize_json(run_meta_obj), ensure_ascii=False, indent=2), encoding="utf-8")

    regime_audit_rel = None
    regime_transition_debug_rel = None
    regime_audit_report_rel = None
    regime_audit_summary_obj: dict[str, Any] | None = None
    daily_path = results_dir / ARTIFACT_FILENAMES["daily"]
    if daily_path.exists():
        try:
            daily_df_for_regime = pd.read_csv(daily_path)
        except Exception:
            daily_df_for_regime = pd.DataFrame()
        if not daily_df_for_regime.empty:
            try:
                regime_artifacts = write_regime_audit_artifacts(
                    results_dir=results_dir,
                    daily_df=daily_df_for_regime,
                    run_meta=run_meta_obj,
                )
            except Exception as exc:
                logger.warning("build regime audit artifacts failed: %s", exc)
                regime_artifacts = None
            if isinstance(regime_artifacts, dict):
                regime_audit_summary_obj = sanitize_json(regime_artifacts.get("summary") or {})
                summary_path = regime_artifacts.get("summary_path")
                debug_path = regime_artifacts.get("transition_debug_path")
                report_path = regime_artifacts.get("report_path")
                if isinstance(summary_path, Path) and summary_path.exists():
                    regime_audit_rel = _to_rel(summary_path, results_dir)
                if isinstance(debug_path, Path) and debug_path.exists():
                    regime_transition_debug_rel = _to_rel(debug_path, results_dir)
                if isinstance(report_path, Path) and report_path.exists():
                    regime_audit_report_rel = _to_rel(report_path, results_dir)

    lineage_rel = None
    lineage_rows_raw = (
        ((result.get("metrics") or {}) if isinstance(result.get("metrics"), dict) else {}).get("execution_lineage_ledger")
    )
    if isinstance(lineage_rows_raw, list):
        lineage_path = results_dir / ARTIFACT_FILENAMES["execution_lineage_ledger"]
        lineage_df = pd.DataFrame(lineage_rows_raw)
        for column in LINEAGE_LEDGER_COLUMNS:
            if column not in lineage_df.columns:
                lineage_df[column] = None
        lineage_df = lineage_df.loc[:, list(LINEAGE_LEDGER_COLUMNS)] if not lineage_df.empty else pd.DataFrame(columns=list(LINEAGE_LEDGER_COLUMNS))
        lineage_df.to_csv(lineage_path, index=False)
        lineage_rel = _to_rel(lineage_path, results_dir)

    audit_data = (result.get("metrics") or {}).get("audit")
    if not isinstance(audit_data, dict):
        audit_data = {}
    execution_lineage_audit = audit_data.get("execution_lineage")
    if isinstance(execution_lineage_audit, dict) and lineage_rel:
        execution_lineage_audit = dict(execution_lineage_audit)
        execution_lineage_audit["ledger_ref"] = lineage_rel
        audit_data["execution_lineage"] = execution_lineage_audit
    audit_data = merge_experiment_audit(audit_data, stage_pipeline=stage_pipeline_obj if isinstance(stage_pipeline_obj, dict) else None, stage_summary=stage_summary_obj if isinstance(stage_summary_obj, dict) else None, exp_id=str(result.get("exp_id") or ""))
    audit_rel = None
    if isinstance(audit_data, dict) and audit_data:
        if regime_audit_summary_obj:
            audit_data["regime_audit"] = regime_audit_summary_obj
        try:
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
        "orders": _to_rel(orders_path, results_dir),
        "candidate_signals": _to_rel(candidate_signals_path, results_dir),
        "cash_blocked_buys_recent": _to_rel(cash_blocked_recent_path, results_dir),
        "alpha_funnel": _to_rel(alpha_funnel_path, results_dir),
        "score_diagnostics": _to_rel(score_diagnostics_path, results_dir),
        "execution_lineage_ledger": lineage_rel,
        "audit": audit_rel,
        "stage_summary": stage_summary_rel,
        "regime_audit_summary": regime_audit_rel,
        "regime_transition_debug": regime_transition_debug_rel,
        "regime_audit_report": regime_audit_report_rel,
    }
    if trades_path.exists():
        artifacts["trades"] = _to_rel(trades_path, results_dir)
    if daily_path.exists():
        artifacts["daily"] = _to_rel(daily_path, results_dir)
    for extra_name in ("input_config.json", "resolved_config.json", "compiled_plan.json", "baseline_compare.json"):
        extra_path = results_dir / extra_name
        if extra_path.exists():
            artifacts[extra_name.replace(".json", "")] = _to_rel(extra_path, results_dir)

    out = dict(result)
    out["status"] = str(out.get("status") or "OK")
    out["artifacts"] = artifacts
    out["asset_context"] = asset_context
    return sanitize_json(out)


def _append_to_experiment_index(results_dir: Path, result: dict[str, Any], base_cfg: dict[str, Any], overrides: dict[str, Any]) -> None:
    index_path = results_dir.parent / "index.json"
    entries: list[dict[str, Any]] = []
    if index_path.exists():
        try:
            entries = json.loads(index_path.read_text(encoding="utf-8"))
            if not isinstance(entries, list):
                entries = []
        except Exception:
            entries = []

    exp_id = str(result.get("exp_id") or "")
    entry = {
        "exp_id": exp_id,
        "label": _generate_experiment_label(base_cfg, overrides),
        "created_at": datetime.now().isoformat(),
        "status": str(result.get("status") or "OK"),
        "total_return": _safe_float(result.get("total_return")),
        "max_drawdown": _safe_float(result.get("max_drawdown")),
        "sharpe": _safe_float(result.get("sharpe")),
        "trades": _safe_int(result.get("trades")),
        "has_manifest": (results_dir / "manifest.json").exists(),
        "asset_scope": str((result.get("asset_context") or {}).get("asset_scope") or base_cfg.get("asset_scope") or "cn_a_equity"),
        "asset_profile_id": str((result.get("asset_context") or {}).get("asset_profile_id") or ""),
        "market_profile_id": str((result.get("asset_context") or {}).get("market_profile_id") or ""),
    }
    entries = [e for e in entries if e.get("exp_id") != exp_id]
    entries.append(sanitize_json(entry))
    index_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


__all__ = [
    "_append_to_experiment_index",
    "_finalize_research_audit",
    "ensure_standard_artifacts",
]
