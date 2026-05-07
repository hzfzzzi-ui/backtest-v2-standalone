from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from backend.core.data.price_limits import round_price_to_tick
from backend.core.config.etf_beta_contract import (
    _is_formal_stabilizer_role,
    build_etf_beta_formal_view,
    build_etf_beta_phase1_summary as build_cn_etf_beta_phase1_summary,
    build_etf_beta_research_view,
)
from backend.core.data.provider_factory import build_scoped_postgres_provider
from backend.core.tools.runtime_data_access import load_runtime_data_access
from backend.core.universe.lineage import get_universe_lineage, normalize_universe_mode
from backend.api.backtest_v2.protocol import ARTIFACT_FILENAMES

RESEARCH_AUDIT_CONTRACT_VERSION = "research_audit@1"
RESEARCH_AUDIT_STATUSES = ("PASS", "WARN", "FAIL", "UNKNOWN")
UNIVERSE_LINEAGE_MODES = ("PIT_DYNAMIC", "DIRECT_SYMBOLS", "START_SNAPSHOT", "CURRENT_SNAPSHOT", "UNKNOWN")
_PRICE_ONLY_STRATEGIES = ("BREAKOUT_TREND", "BREAKOUT", "SMA_CROSS", "EMA_CROSS", "RSI_REVERSAL")
_NEXT_DAY_MATCHING_MODES = ("NEXT_OPEN", "NEXT_DAY", "NEXT_TRADING_DAY", "NEXT_BAR_OPEN")
_ADJ_FACTOR_STALE_WARN_THRESHOLD = 5
_ADJ_FACTOR_STALE_FAIL_THRESHOLD = 20

_LIMIT_LOCK_FAIL_RATIO = 0.01
_CONCENTRATION_WARN_THRESHOLD = 0.8
_REQUIRED_SNAPSHOTS = ("input_config", "resolved_config", "compiled_plan")


def _likely_cn_etf_symbol(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if len(text) != 8:
        return False
    return text.startswith(("sh5", "sz1"))


def _load_etf_bar_supplement(
    *,
    access: Any,
    symbols: list[str],
    start: Any,
    end: Any,
) -> tuple[pd.DataFrame, int]:
    etf_symbols = sorted({str(symbol).strip().lower() for symbol in symbols if _likely_cn_etf_symbol(symbol)})
    if not etf_symbols:
        return pd.DataFrame(), 0
    etf_provider = build_scoped_postgres_provider(
        access.cfg_obj,
        access.cfg_path.parent / "instrument_rules_cn.csv",
        stocks_table="pams_cn_etf_daily",
    )
    extra = etf_provider.load_ohlcv_daily(
        etf_symbols,
        start,
        end,
        source="research_audit_execution_realism_etf",
    )
    query_count = len(getattr(etf_provider, "query_audit", []) or [])
    return extra, query_count


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        out = float(value)
    except Exception:
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return out


def _safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def _normalize_status(value: Any) -> str:
    text = str(value or "UNKNOWN").strip().upper()
    if text not in RESEARCH_AUDIT_STATUSES:
        return "UNKNOWN"
    return text


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return False
    if isinstance(value, (int, float)):
        try:
            return not math.isnan(float(value)) and float(value) != 0.0
        except Exception:
            return False
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off", "nan", "none", "null", ""}:
        return False
    return bool(text)


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, None
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return None, f"{path.name}: {exc}"
    if not isinstance(payload, dict):
        return None, f"{path.name}: expected object payload"
    return payload, None


def _read_csv(path: Path) -> tuple[pd.DataFrame, str | None]:
    if not path.exists():
        return pd.DataFrame(), None
    try:
        return pd.read_csv(path), None
    except Exception as exc:
        return pd.DataFrame(), f"{path.name}: {exc}"


def _clean_ref(path: Path, *, root: Path) -> str | None:
    if not path.exists():
        return None
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _load_combo_component_records(
    *,
    run_meta: Mapping[str, Any] | None,
    results_dir: str | Path | None,
) -> dict[str, dict[str, Any]]:
    run_meta_obj = dict(run_meta or {})
    sleeves = dict(run_meta_obj.get("sleeves") or {})
    root = Path(results_dir).resolve() if results_dir is not None else None
    records: dict[str, dict[str, Any]] = {}
    for sleeve_name, sleeve_payload in sleeves.items():
        if not isinstance(sleeve_payload, Mapping):
            continue
        sleeve_obj = dict(sleeve_payload)
        sleeve_root = None
        raw_results_dir = str(sleeve_obj.get("results_dir") or "").strip()
        if raw_results_dir:
            sleeve_root = Path(raw_results_dir).resolve()
        else:
            exp_id = str(sleeve_obj.get("exp_id") or "").strip()
            if exp_id and root is not None:
                sleeve_root = (root.parent / exp_id).resolve()
        component_run_meta = None
        read_error = None
        if sleeve_root is not None:
            component_run_meta, read_error = _read_json(sleeve_root / "run_meta.json")
        records[str(sleeve_name)] = {
            "exp_id": str(sleeve_obj.get("exp_id") or "").strip() or None,
            "results_dir": sleeve_root,
            "run_meta": component_run_meta if isinstance(component_run_meta, Mapping) else None,
            "read_error": read_error,
        }
    return records


def _normalize_trade_df(trades_df: pd.DataFrame) -> pd.DataFrame:
    if trades_df.empty:
        return pd.DataFrame()
    out = trades_df.copy()
    if "date" not in out.columns or "symbol" not in out.columns:
        return pd.DataFrame()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.date
    out["symbol"] = out["symbol"].astype(str).str.lower().str.strip()
    out["side"] = out.get("side", pd.Series(index=out.index, dtype=str)).astype(str).str.upper().str.strip()
    out["price"] = pd.to_numeric(out.get("price"), errors="coerce")
    out["fill_price"] = pd.to_numeric(out.get("fill_price"), errors="coerce")
    out = out.dropna(subset=["date", "symbol"])
    out = out[out["symbol"] != ""]
    return out.reset_index(drop=True)


def _normalize_bar_df(bars_df: pd.DataFrame) -> pd.DataFrame:
    if bars_df.empty:
        return pd.DataFrame()
    out = bars_df.copy()
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.date
    elif "trade_date" in out.columns:
        out["date"] = pd.to_datetime(out["trade_date"], errors="coerce").dt.date
    else:
        return pd.DataFrame()
    if "symbol" not in out.columns:
        return pd.DataFrame()
    out["symbol"] = out["symbol"].astype(str).str.lower().str.strip()
    for col in ("open", "high", "low", "close", "volume", "amount", "turnover", "limit_up", "limit_down"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    if "is_suspended" in out.columns:
        out["is_suspended"] = out["is_suspended"].fillna(False).astype(bool)
    out = out.dropna(subset=["date", "symbol"])
    out = out.drop_duplicates(subset=["symbol", "date"], keep="last")
    return out.reset_index(drop=True)


def _sample_issue_rows(df: pd.DataFrame, mask: pd.Series, *, extra_cols: list[str] | None = None) -> list[dict[str, Any]]:
    if df.empty or mask.empty or not bool(mask.any()):
        return []
    cols = ["date", "symbol", "side", "price", "fill_price", "limit_up", "limit_down", "volume", "amount", "is_suspended"]
    cols.extend(extra_cols or [])
    keep_cols = [col for col in cols if col in df.columns]
    sample = df.loc[mask, keep_cols].head(5).copy()
    if sample.empty:
        return []
    if "date" in sample.columns:
        sample["date"] = sample["date"].map(lambda d: d.isoformat() if hasattr(d, "isoformat") else str(d))
    return sample.to_dict(orient="records")


def _coerce_concentration(value: Any) -> float | None:
    conc = _safe_float(value)
    if conc is None:
        return None
    if conc > 1.0 and conc <= 100.0:
        return conc / 100.0
    return conc


def _series_numeric(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(float("nan"), index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce")


def _series_text(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series("", index=df.index, dtype=object)
    return df[column].astype(str)


def _normalize_limit_series(df: pd.DataFrame, column: str) -> pd.Series:
    raw = _series_numeric(df, column)
    symbols = _series_text(df, "symbol").str.lower()
    values = [round_price_to_tick(value, symbol) for value, symbol in zip(raw.tolist(), symbols.tolist(), strict=False)]
    return pd.to_numeric(pd.Series(values, index=df.index), errors="coerce")


def _series_bool(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(False, index=df.index, dtype=bool)
    return df[column].fillna(False).astype(bool)


def _normalize_etf_symbol_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if text.startswith(("sh", "sz", "bj")) and len(text) > 2:
        return text
    if "." in text:
        code, suffix = text.split(".", 1)
        exchange = suffix.strip().lower()
        prefix = {"sh": "sh", "ss": "sh", "sz": "sz", "bj": "bj"}.get(exchange[:2], "")
        if prefix and code.strip():
            return f"{prefix}{code.strip().lower()}"
    return text


def _extract_cn_etf_buy_order_meta(orders_df: pd.DataFrame) -> pd.DataFrame:
    if orders_df.empty or "meta_json" not in orders_df.columns:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for _, row in orders_df.iterrows():
        side = str(row.get("side") or "").strip().upper()
        if side and side != "BUY":
            continue
        raw_meta = row.get("meta_json")
        if not isinstance(raw_meta, str) or not raw_meta.strip():
            continue
        try:
            meta = dict(json.loads(raw_meta) or {})
        except Exception:
            continue
        if str(meta.get("sleeve_id") or meta.get("alpha_id") or "").strip() != "cn_etf_beta":
            continue
        rows.append(
            {
                "date": str(row.get("date") or "").strip(),
                "symbol": str(row.get("symbol") or "").strip(),
                "reason_code": str(row.get("reason_code") or "").strip(),
                "state_5": str(meta.get("state_5") or "").strip(),
                "execution_path": str(meta.get("execution_path") or "").strip(),
                "target_weight": _safe_float(meta.get("target_weight")),
                "requested_target_weight": _safe_float(meta.get("requested_target_weight")),
                "final_target_weight": _safe_float(meta.get("final_target_weight")),
                "target_weight_basis": str(meta.get("target_weight_basis") or "").strip(),
                "target_exposure": _safe_float(meta.get("target_exposure")),
                "decision_date": str(meta.get("signal_date") or row.get("signal_date") or "").strip(),
            }
        )
    return pd.DataFrame(rows)


def _parse_runtime_diagnostics_payload(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        payload = dict(json.loads(raw) or {})
    except Exception:
        return {}
    diagnostics = payload.get("diagnostics")
    return dict(diagnostics or payload) if isinstance(diagnostics or payload, dict) else {}


def _extract_etf_diagnostics_views(raw: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    diagnostics = _parse_runtime_diagnostics_payload(raw)
    formal_view = dict(diagnostics.get("etf_beta_formal_view") or {})
    research_view = dict(diagnostics.get("etf_beta_research_view") or {})
    return diagnostics, formal_view, research_view


def _build_etf_diagnostics_view_frame(portfolio_daily: pd.DataFrame) -> pd.DataFrame:
    if portfolio_daily.empty:
        return pd.DataFrame(index=portfolio_daily.index)
    records: list[dict[str, Any]] = []
    for _, row in portfolio_daily.iterrows():
        diagnostics, formal_view, research_view = _extract_etf_diagnostics_views(row.get("diagnostics_input_json"))
        records.append(
            {
                "diagnostics_target_exposure": _safe_float(
                    formal_view.get("target_exposure", diagnostics.get("etf_beta_target_exposure"))
                ),
                "strategic_floor_target": _safe_float(research_view.get("strategic_floor_cap")),
                "tactical_overlay_target": _safe_float(research_view.get("tactical_overlay_cap")),
                "limited_defense_target": _safe_float(research_view.get("limited_defense_cap")),
                "deployment_pace": _safe_float(research_view.get("deployment_pace")),
                "pace_policy_gap": _safe_float(research_view.get("pace_policy_gap")),
                "rebalance_timing_gap": _safe_float(research_view.get("rebalance_timing_gap")),
                "execution_residual_gap": _safe_float(research_view.get("execution_residual_gap")),
                "deployability_gap": _safe_float(research_view.get("deployability_gap")),
                "execution_path": str(research_view.get("execution_path") or diagnostics.get("etf_beta_execution_path") or "").strip(),
                "bull_partial_overlay_pace_ratio": _safe_float(research_view.get("bull_partial_overlay_pace_ratio")),
                "bull_pace_mode": str(research_view.get("bull_pace_mode") or "").strip(),
                "layering_band": str(research_view.get("layering_band") or "").strip(),
                "layering_reason_codes": list(research_view.get("layering_reason_codes") or []),
                "under_deploy_reason_codes": list(research_view.get("under_deploy_reason_codes") or []),
                "hard_block_flags": list(research_view.get("hard_block_flags") or []),
                "trans_up_contract_mode": str(research_view.get("trans_up_contract_mode") or "").strip(),
                "trans_up_single_seat_core_recovery": bool(research_view.get("trans_up_single_seat_core_recovery", False)),
                "trans_up_redeploy_active": bool(research_view.get("trans_up_redeploy_active", False)),
                "trans_up_redeploy_reason_code": str(research_view.get("trans_up_redeploy_reason_code") or "").strip(),
                "trans_up_redeploy_reject_reason": str(research_view.get("trans_up_redeploy_reject_reason") or "").strip(),
                "trans_up_redeploy_floor_gap": _safe_float(research_view.get("trans_up_redeploy_floor_gap")),
                "trans_up_redeploy_edge_from_state": str(research_view.get("trans_up_redeploy_edge_from_state") or "").strip(),
                "requested_budget": _safe_float(research_view.get("requested_budget")),
                "applied_budget": _safe_float(research_view.get("applied_budget")),
                "fallback_allowed_source": str(formal_view.get("fallback_allowed_source") or "").strip(),
                "target_selected_count_source": str(formal_view.get("target_selected_count_source") or "").strip(),
                "exposure_policy_family": str(formal_view.get("exposure_policy_family") or "").strip(),
                "policy_scope": str(formal_view.get("policy_scope") or "").strip(),
                "broad_based_only": bool(formal_view.get("broad_based_only", False)),
                "absolute_filter_reject_count": int(_safe_float(research_view.get("absolute_filter_reject_count")) or 0),
                "absolute_filter_reject_reason_counts": dict(research_view.get("absolute_filter_reject_reason_counts") or {}),
                "candidate_pool_reject_reason_counts": dict(research_view.get("candidate_pool_reject_reason_counts") or {}),
                "selection_chain_winner_counts": dict(research_view.get("selection_chain_winner_counts") or {}),
                "selection_chain_reject_reason_counts": dict(research_view.get("selection_chain_reject_reason_counts") or {}),
            }
        )
    return pd.DataFrame(records, index=portfolio_daily.index)


def _summarize_etf_bull_trans_up_bottleneck(portfolio_daily: pd.DataFrame, orders_df: pd.DataFrame) -> dict[str, Any]:
    if portfolio_daily.empty:
        return {}
    diagnostics_view_df = _build_etf_diagnostics_view_frame(portfolio_daily)
    state_series = _series_text(portfolio_daily, "effective_state_5").replace("nan", "")
    if state_series.str.strip().eq("").all():
        state_series = _series_text(portfolio_daily, "market_state_5").replace("nan", "")
    order_meta_df = _extract_cn_etf_buy_order_meta(orders_df)
    summary: dict[str, Any] = {}
    for state in ("BULL", "TRANS_UP"):
        mask = state_series.eq(state)
        if not bool(mask.any()):
            summary[state] = {
                "day_count": 0,
                "avg_target_exposure": None,
                "avg_actual_exposure": None,
                "avg_strategic_floor_target": None,
                "avg_tactical_overlay_target": None,
                "avg_deployment_pace": None,
                "bull_partial_overlay_pace_ratio": None,
                "bull_pace_mode": None,
                "avg_pace_policy_gap": None,
                "avg_rebalance_timing_gap": None,
                "avg_execution_residual_gap": None,
                "positive_target_zero_actual_days": 0,
                "avg_effective_max_positions": None,
                "execution_path_day_counts": {},
                "buy_count": 0,
                "buy_reason_code_counts": {},
                "buy_execution_path_counts": {},
            }
            continue
        state_daily = portfolio_daily.loc[mask].copy()
        state_view = diagnostics_view_df.loc[mask].copy() if not diagnostics_view_df.empty else pd.DataFrame(index=state_daily.index)
        execution_paths = (
            state_view.get("execution_path", pd.Series("", index=state_daily.index, dtype=object))
            .fillna("")
            .astype(str)
            .replace("nan", "")
            .str.strip()
        )
        bull_pace_modes = (
            state_view.get("bull_pace_mode", pd.Series("", index=state_daily.index, dtype=object))
            .fillna("")
            .astype(str)
        )
        bull_pace_modes = bull_pace_modes.str.strip()
        bull_pace_modes = bull_pace_modes.mask(
            bull_pace_modes.str.lower().isin({"nan", "none", "<na>"}),
            "",
        )
        state_orders = (
            order_meta_df.loc[order_meta_df["state_5"].astype(str).str.strip().eq(state)].copy()
            if not order_meta_df.empty and "state_5" in order_meta_df.columns
            else pd.DataFrame()
        )
        target_series = _series_numeric(state_daily, "etf_target_exposure")
        actual_series = _series_numeric(state_daily, "etf_actual_exposure")
        strategic_floor_series = pd.to_numeric(state_view.get("strategic_floor_target"), errors="coerce")
        tactical_overlay_series = pd.to_numeric(state_view.get("tactical_overlay_target"), errors="coerce")
        deployment_pace_series = pd.to_numeric(state_view.get("deployment_pace"), errors="coerce")
        bull_partial_overlay_pace_ratio_series = pd.to_numeric(
            state_view.get("bull_partial_overlay_pace_ratio"), errors="coerce"
        )
        pace_policy_gap_series = pd.to_numeric(state_view.get("pace_policy_gap"), errors="coerce")
        rebalance_timing_gap_series = pd.to_numeric(state_view.get("rebalance_timing_gap"), errors="coerce")
        execution_residual_gap_series = pd.to_numeric(state_view.get("execution_residual_gap"), errors="coerce")
        summary[state] = {
            "day_count": int(len(state_daily.index)),
            "avg_target_exposure": float(target_series.dropna().mean()) if not target_series.dropna().empty else None,
            "avg_actual_exposure": float(actual_series.dropna().mean()) if not actual_series.dropna().empty else None,
            "avg_strategic_floor_target": (
                float(strategic_floor_series.dropna().mean())
                if not strategic_floor_series.dropna().empty
                else None
            ),
            "avg_tactical_overlay_target": (
                float(tactical_overlay_series.dropna().mean())
                if not tactical_overlay_series.dropna().empty
                else None
            ),
            "avg_deployment_pace": (
                float(deployment_pace_series.dropna().mean())
                if not deployment_pace_series.dropna().empty
                else None
            ),
            "bull_partial_overlay_pace_ratio": (
                float(bull_partial_overlay_pace_ratio_series.dropna().mean())
                if not bull_partial_overlay_pace_ratio_series.dropna().empty
                else None
            ),
            "bull_pace_mode": (
                str(bull_pace_modes[bull_pace_modes.ne("")].iloc[0])
                if not bull_pace_modes[bull_pace_modes.ne("")].empty
                else None
            ),
            "avg_pace_policy_gap": (
                float(pace_policy_gap_series.dropna().mean())
                if not pace_policy_gap_series.dropna().empty
                else None
            ),
            "avg_rebalance_timing_gap": (
                float(rebalance_timing_gap_series.dropna().mean())
                if not rebalance_timing_gap_series.dropna().empty
                else None
            ),
            "avg_execution_residual_gap": (
                float(execution_residual_gap_series.dropna().mean())
                if not execution_residual_gap_series.dropna().empty
                else None
            ),
            "positive_target_zero_actual_days": int(
                ((target_series.fillna(0.0) > 1e-12) & (actual_series.fillna(0.0) <= 1e-12)).sum()
            ),
            "avg_effective_max_positions": (
                float(_series_numeric(state_daily, "effective_max_positions").dropna().mean())
                if not _series_numeric(state_daily, "effective_max_positions").dropna().empty
                else None
            ),
            "execution_path_day_counts": {
                str(key): int(value)
                for key, value in execution_paths[execution_paths.ne("")].value_counts().to_dict().items()
            },
            "buy_count": int(len(state_orders.index)),
            "buy_reason_code_counts": (
                {str(key): int(value) for key, value in state_orders["reason_code"].value_counts().to_dict().items()}
                if not state_orders.empty and "reason_code" in state_orders.columns
                else {}
            ),
            "buy_execution_path_counts": (
                {str(key): int(value) for key, value in state_orders["execution_path"].value_counts().to_dict().items()}
                if not state_orders.empty and "execution_path" in state_orders.columns
                else {}
            ),
        }
    return summary


def summarize_validation_audit_ref(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping):
        return None
    warnings = raw.get("warnings")
    warning_codes: list[str] = []
    if isinstance(raw.get("warning_codes"), list):
        warning_codes = [str(code).strip() for code in raw.get("warning_codes") or () if str(code).strip()]
    elif isinstance(warnings, list):
        warning_codes = [
            str(item.get("code") or "").strip()
            for item in warnings
            if isinstance(item, Mapping) and str(item.get("code") or "").strip()
        ]
    request_id = str(raw.get("request_id") or "").strip() or None
    path = str(raw.get("path") or "").strip() or None
    passed = raw.get("pass")
    return {
        "request_id": request_id,
        "path": path,
        "pass": bool(passed) if passed is not None else None,
        "warning_codes": warning_codes,
    }


def _extract_accounting_integrity_audit(
    *,
    result: Mapping[str, Any] | None,
    run_meta: Mapping[str, Any] | None,
    results_dir: Path | None,
) -> tuple[dict[str, Any] | None, str | None]:
    result_obj = dict(result or {})
    run_meta_obj = dict(run_meta or {})
    candidates = (
        result_obj.get("accounting_integrity"),
        (result_obj.get("metrics") or {}).get("audit", {}).get("accounting_integrity")
        if isinstance((result_obj.get("metrics") or {}).get("audit"), Mapping)
        else None,
        run_meta_obj.get("accounting_integrity"),
    )
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            return dict(candidate), "result"
    if results_dir is not None:
        audit_obj, _ = _read_json(results_dir / "audit.json")
        if isinstance(audit_obj, Mapping) and isinstance(audit_obj.get("accounting_integrity"), Mapping):
            return dict(audit_obj.get("accounting_integrity") or {}), "audit.json"
    return None, None


def aggregate_overall_status(gates: Mapping[str, Mapping[str, Any]] | None) -> str:
    statuses = [_normalize_status((gate or {}).get("status")) for gate in (gates or {}).values()]
    if any(status == "FAIL" for status in statuses):
        return "FAIL"
    if any(status == "WARN" for status in statuses):
        return "WARN"
    if any(status == "UNKNOWN" for status in statuses):
        return "UNKNOWN"
    return "PASS"

def _merge_timing_meta(primary: Mapping[str, Any] | None, fallback: Mapping[str, Any] | None) -> dict[str, Any]:
    out = dict(fallback or {})
    for key, value in dict(primary or {}).items():
        if value in (None, "", [], {}):
            continue
        out[key] = value
    return out


def _infer_timing_meta_from_artifacts(
    *,
    results_dir: Path | None,
    stage_summary: Mapping[str, Any] | None,
    stage_pipeline: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if results_dir is None:
        return {}
    root = Path(results_dir).resolve()
    compiled_plan_obj, _ = _read_json(root / "compiled_plan.json")
    input_config_obj, _ = _read_json(root / "input_config.json")
    if not isinstance(compiled_plan_obj, Mapping) and not isinstance(input_config_obj, Mapping):
        return {}

    runtime_config = {}
    if isinstance(compiled_plan_obj, Mapping):
        runtime_config = dict(compiled_plan_obj.get("runtime_config") or {})
        if not runtime_config:
            runtime_config = dict(compiled_plan_obj)
    execution_cfg = dict(runtime_config.get("execution") or {})
    strategy_cfg = dict(runtime_config.get("strategy") or {})
    strategy_params = dict(strategy_cfg.get("params") or {})
    input_cfg = dict(input_config_obj or {})
    signal_cfg = dict(input_cfg.get("signal_generation") or {})
    sector_gate_cfg = dict(input_cfg.get("sector_gate") or {})
    position_risk_cfg = dict(input_cfg.get("position_risk") or {})
    cost_model_cfg = dict(position_risk_cfg.get("cost_model") or {})
    daily_loop_mode = str(
        (stage_summary or {}).get("daily_loop_mode")
        or (stage_pipeline or {}).get("daily_loop_mode")
        or ""
    ).strip()
    execution_shell = str(
        (stage_summary or {}).get("execution_shell")
        or (stage_pipeline or {}).get("execution_shell")
        or ""
    ).strip()
    route_id = str(
        (stage_summary or {}).get("route_id")
        or (stage_pipeline or {}).get("route_id")
        or ""
    ).strip()
    strategy_name = str(
        input_cfg.get("strategy_pack")
        or signal_cfg.get("strategy")
        or strategy_cfg.get("name")
        or ""
    ).strip().upper()
    matching_mode = str(
        cost_model_cfg.get("matching")
        or execution_cfg.get("matching")
        or ""
    ).strip().upper()
    t_plus_one = _coerce_bool(execution_cfg.get("t_plus_one"))
    next_day_shell = bool(execution_shell) and daily_loop_mode == "single_day_loop"
    if not matching_mode and execution_shell == "stage_pipeline_shell_bridge" and next_day_shell and t_plus_one:
        matching_mode = "NEXT_OPEN"
    contract_proved = next_day_shell and t_plus_one and matching_mode in _NEXT_DAY_MATCHING_MODES

    uses_fundamental_data = any(
        str(key).strip().lower() in {"fundamental", "fundamentals", "financial", "valuation", "quality_factor"}
        for key in input_cfg.keys()
    ) or any(
        str(key).strip().lower() in {"fundamental", "fundamentals", "financial", "valuation", "quality_factor"}
        for key in runtime_config.keys()
    )
    uses_membership_signal = _coerce_bool(sector_gate_cfg.get("enabled")) or _coerce_bool(
        strategy_params.get("enable_sector_gate")
    )
    price_only_strategy = strategy_name in _PRICE_ONLY_STRATEGIES
    pit_safe = contract_proved and price_only_strategy and (not uses_fundamental_data) and (not uses_membership_signal)

    if not contract_proved and not price_only_strategy:
        return {}

    return {
        "status": "PASS" if pit_safe else "UNKNOWN",
        "contract_proved": contract_proved,
        "pit_safe": pit_safe,
        "same_day_close_fill": False if contract_proved else None,
        "future_input_detected": False if pit_safe else None,
        "signal_observation_bar": "t_close" if contract_proved else None,
        "execution_bar": "t_plus_1_open" if contract_proved else None,
        "input_family": "price_only_daily" if price_only_strategy else "unknown",
        "uses_fundamental_data": uses_fundamental_data,
        "uses_membership_signal": uses_membership_signal,
        "strategy_name": strategy_name or None,
        "matching_mode": matching_mode or None,
        "proof_source": ["compiled_plan.json", "input_config.json"],
        "reason": (
            "Derived from compiled_plan/input_config: next-day execution contract with price-only daily inputs."
            if pit_safe
            else "Next-day execution contract is provable, but PIT-safe input coverage is still incomplete."
        ),
        "route_id": route_id or None,
    }


def _infer_timing_meta_from_lineage(
    *,
    results_dir: Path | None,
    result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    result_obj = dict(result or {})
    lineage_rows_raw = (
        (result_obj.get("metrics") or {}).get("execution_lineage_ledger")
        if isinstance(result_obj.get("metrics"), Mapping)
        else None
    )
    if isinstance(lineage_rows_raw, list):
        lineage_rows = pd.DataFrame(lineage_rows_raw)
    elif results_dir is not None:
        lineage_rows, _ = _read_csv(results_dir / ARTIFACT_FILENAMES["execution_lineage_ledger"])
    else:
        lineage_rows = pd.DataFrame()
    if lineage_rows.empty:
        return {}
    required_cols = {"signal_date", "scheduled_date", "terminal_status"}
    if not required_cols.issubset(set(lineage_rows.columns)):
        return {}

    frame = lineage_rows.copy()
    frame["signal_date"] = pd.to_datetime(frame["signal_date"], errors="coerce").dt.date
    frame["scheduled_date"] = pd.to_datetime(frame["scheduled_date"], errors="coerce").dt.date
    if "fill_date" in frame.columns:
        frame["fill_date"] = pd.to_datetime(frame["fill_date"], errors="coerce").dt.date
    else:
        frame["fill_date"] = pd.NaT
    frame["terminal_status"] = frame["terminal_status"].astype(str).str.lower().str.strip()
    frame = frame.dropna(subset=["signal_date", "scheduled_date"])
    if frame.empty:
        return {}

    same_day_fill_mask = (
        frame["terminal_status"].eq("filled")
        & frame["fill_date"].notna()
        & (frame["fill_date"] <= frame["signal_date"])
    )
    schedule_drift_mask = frame["scheduled_date"] <= frame["signal_date"]
    filled_count = int(frame["terminal_status"].eq("filled").sum())
    if bool(same_day_fill_mask.any()):
        return {
            "status": "FAIL",
            "contract_proved": False,
            "pit_safe": None,
            "same_day_close_fill": True,
            "signal_observation_bar": "t_close",
            "execution_bar": "same_day_or_earlier",
            "proof_source": [ARTIFACT_FILENAMES["execution_lineage_ledger"]],
            "reason": "Execution lineage ledger contains same-day or earlier fills.",
            "lineage_metrics": {
                "rows": int(len(frame.index)),
                "filled_count": int(filled_count),
                "same_day_fill_count": int(same_day_fill_mask.sum()),
                "schedule_drift_count": int(schedule_drift_mask.sum()),
            },
        }
    if bool(schedule_drift_mask.any()):
        return {
            "status": "FAIL",
            "contract_proved": False,
            "pit_safe": None,
            "same_day_close_fill": False,
            "signal_observation_bar": "t_close",
            "execution_bar": "same_day_or_earlier",
            "proof_source": [ARTIFACT_FILENAMES["execution_lineage_ledger"]],
            "reason": "Execution lineage ledger contains same-day scheduling drift.",
            "lineage_metrics": {
                "rows": int(len(frame.index)),
                "filled_count": int(filled_count),
                "same_day_fill_count": 0,
                "schedule_drift_count": int(schedule_drift_mask.sum()),
            },
        }
    return {
        "status": "PASS",
        "contract_proved": True,
        "pit_safe": None,
        "same_day_close_fill": False,
        "signal_observation_bar": "t_close",
        "execution_bar": "t_plus_1_open",
        "proof_source": [ARTIFACT_FILENAMES["execution_lineage_ledger"]],
        "reason": "Derived from explicit signal/order/fill lineage evidence.",
        "lineage_metrics": {
            "rows": int(len(frame.index)),
            "filled_count": int(filled_count),
            "same_day_fill_count": 0,
            "schedule_drift_count": 0,
        },
    }


def evaluate_timing_alignment(
    *,
    stage_summary: Mapping[str, Any] | None,
    stage_pipeline: Mapping[str, Any] | None,
    result: Mapping[str, Any] | None = None,
    run_meta: Mapping[str, Any] | None = None,
    results_dir: str | Path | None = None,
) -> dict[str, Any]:
    result_obj = dict(result or {})
    run_meta_obj = dict(run_meta or {})
    explicit_timing_meta = {}
    for candidate in (
        result_obj.get("timing_audit"),
        result_obj.get("timing_alignment"),
        (result_obj.get("metrics") or {}).get("timing_audit") if isinstance(result_obj.get("metrics"), Mapping) else None,
        (result_obj.get("metrics") or {}).get("audit", {}).get("timing_alignment")
        if isinstance((result_obj.get("metrics") or {}).get("audit"), Mapping)
        else None,
        run_meta_obj.get("timing_audit"),
    ):
        if isinstance(candidate, Mapping):
            explicit_timing_meta = dict(candidate)
            break
    derived_timing_meta = _infer_timing_meta_from_artifacts(
        results_dir=Path(results_dir) if results_dir is not None else None,
        stage_summary=stage_summary,
        stage_pipeline=stage_pipeline,
    )
    lineage_timing_meta = _infer_timing_meta_from_lineage(
        results_dir=Path(results_dir) if results_dir is not None else None,
        result=result_obj,
    )
    timing_meta = _merge_timing_meta(explicit_timing_meta, _merge_timing_meta(lineage_timing_meta, derived_timing_meta))

    mismatch_fields: list[str] = []
    summary_obj = dict(stage_summary or {})
    pipeline_obj = dict(stage_pipeline or {})
    asset_role = str(((run_meta_obj.get("data") or {}).get("asset_role")) or "").strip().lower()
    execution_shell = str(summary_obj.get("execution_shell") or pipeline_obj.get("execution_shell") or "").strip().lower()
    daily_loop_mode = str(summary_obj.get("daily_loop_mode") or pipeline_obj.get("daily_loop_mode") or "").strip().lower()
    is_combo_runtime = asset_role == "unified_multi_sleeve_combo" or execution_shell == "unified_combo_phase1" or daily_loop_mode == "unified_combo_phase1"
    component_timing_gates: dict[str, dict[str, Any]] = {}
    if is_combo_runtime:
        for sleeve_name, component in _load_combo_component_records(run_meta=run_meta_obj, results_dir=results_dir).items():
            component_run_meta = component.get("run_meta")
            component_root = component.get("results_dir")
            if not isinstance(component_run_meta, Mapping):
                component_timing_gates[sleeve_name] = {
                    "status": "UNKNOWN",
                    "reason": str(component.get("read_error") or "component run_meta unavailable"),
                }
                continue
            component_timing_gates[sleeve_name] = evaluate_timing_alignment(
                stage_summary=None,
                stage_pipeline=(component_run_meta or {}).get("stage_pipeline"),
                result=None,
                run_meta=component_run_meta,
                results_dir=component_root,
            )
    for field in ("schema_version", "execution_shell", "daily_loop_mode", "route_id", "stage_order", "enabled_stages"):
        left = summary_obj.get(field)
        right = pipeline_obj.get(field)
        if left in (None, "", [], {}) or right in (None, "", [], {}):
            continue
        if left != right:
            mismatch_fields.append(field)

    component_statuses = {
        name: _normalize_status((gate or {}).get("status"))
        for name, gate in component_timing_gates.items()
        if isinstance(gate, Mapping)
    }
    component_counts = Counter(component_statuses.values())
    all_component_pass = bool(component_statuses) and all(status == "PASS" for status in component_statuses.values())
    any_component_fail = any(status == "FAIL" for status in component_statuses.values())
    any_component_warn = any(status == "WARN" for status in component_statuses.values())
    contract_proved = bool(timing_meta.get("contract_proved")) or (is_combo_runtime and execution_shell == "unified_combo_phase1" and all_component_pass)
    pit_safe = bool(timing_meta.get("pit_safe")) or (is_combo_runtime and all_component_pass)

    if bool(timing_meta.get("same_day_close_fill")) or bool(timing_meta.get("future_input_detected")):
        status = "FAIL"
        reason = "Detected explicit same-day fill or future-input risk."
    elif any_component_fail:
        status = "FAIL"
        reason = "Unified combo delegates to at least one sleeve with FAIL timing alignment."
    elif _normalize_status(timing_meta.get("status")) == "FAIL":
        status = "FAIL"
        reason = str(timing_meta.get("reason") or "Timing audit reported FAIL explicitly.")
    elif mismatch_fields:
        status = "WARN"
        reason = f"Stage execution metadata mismatch: {', ' .join(mismatch_fields)}"
    elif is_combo_runtime and execution_shell == "unified_combo_phase1" and all_component_pass:
        status = "PASS"
        reason = "Unified combo shell delegates to sleeve runs that all prove a next-day timing contract."
    elif any_component_warn:
        status = "WARN"
        reason = "Unified combo delegates to at least one sleeve with WARN timing alignment."
    elif contract_proved and pit_safe:
        status = "PASS"
        reason = str(timing_meta.get("reason") or "Signal inputs and execution timing satisfy a next-day contract.")
    elif summary_obj or pipeline_obj:
        status = "UNKNOWN"
        reason = "Execution shell proves a timing contract, but PIT-safe input coverage is not yet provable."
    else:
        status = "UNKNOWN"
        reason = "Insufficient stage/timing evidence."

    evidence = {
        "execution_shell": str(summary_obj.get("execution_shell") or pipeline_obj.get("execution_shell") or ""),
        "daily_loop_mode": str(summary_obj.get("daily_loop_mode") or pipeline_obj.get("daily_loop_mode") or ""),
        "route_id": str(summary_obj.get("route_id") or pipeline_obj.get("route_id") or ""),
        "mismatch_fields": mismatch_fields,
        "component_timing_statuses": component_statuses,
        "matching_mode": timing_meta.get("matching_mode"),
        "strategy_name": timing_meta.get("strategy_name"),
        "signal_observation_bar": timing_meta.get("signal_observation_bar"),
        "execution_bar": timing_meta.get("execution_bar"),
        "proof_source": list(timing_meta.get("proof_source") or ()),
    }
    metrics = {
        "stage_summary_present": bool(summary_obj),
        "stage_pipeline_present": bool(pipeline_obj),
        "explicit_timing_meta_present": bool(explicit_timing_meta),
        "derived_timing_meta_present": bool(derived_timing_meta),
        "component_count": int(len(component_statuses)),
        "component_pass_count": int(component_counts.get("PASS", 0)),
        "component_warn_count": int(component_counts.get("WARN", 0)),
        "component_fail_count": int(component_counts.get("FAIL", 0)),
        "contract_proved": contract_proved,
        "pit_safe": pit_safe,
        "uses_fundamental_data": bool(timing_meta.get("uses_fundamental_data")),
        "uses_membership_signal": bool(timing_meta.get("uses_membership_signal")),
        "lineage_rows": _safe_int((timing_meta.get("lineage_metrics") or {}).get("rows")),
        "lineage_filled_count": _safe_int((timing_meta.get("lineage_metrics") or {}).get("filled_count")),
        "lineage_same_day_fill_count": _safe_int((timing_meta.get("lineage_metrics") or {}).get("same_day_fill_count")),
        "lineage_schedule_drift_count": _safe_int((timing_meta.get("lineage_metrics") or {}).get("schedule_drift_count")),
    }
    return {"status": status, "reason": reason, "evidence": evidence, "metrics": metrics}


def evaluate_universe_lineage(
    *,
    run_meta: Mapping[str, Any] | None,
    results_dir: str | Path | None = None,
) -> dict[str, Any]:
    run_meta_obj = dict(run_meta or {})
    universe_meta = dict(run_meta_obj.get("universe") or {})
    data_meta = dict(run_meta_obj.get("data") or {})
    stage_pipeline = dict(run_meta_obj.get("stage_pipeline") or {})
    asset_scope = str(
        universe_meta.get("asset_scope")
        or data_meta.get("asset_scope")
        or ""
    ).strip().lower()
    asset_role = str(data_meta.get("asset_role") or "").strip().lower()
    execution_shell = str(stage_pipeline.get("execution_shell") or "").strip().lower()
    if asset_role == "unified_multi_sleeve_combo" or execution_shell == "unified_combo_phase1":
        component_gates: dict[str, dict[str, Any]] = {}
        component_modes: dict[str, str] = {}
        for sleeve_name, component in _load_combo_component_records(run_meta=run_meta_obj, results_dir=results_dir).items():
            component_run_meta = component.get("run_meta")
            if not isinstance(component_run_meta, Mapping):
                component_gates[sleeve_name] = {
                    "status": "UNKNOWN",
                    "reason": str(component.get("read_error") or "component run_meta unavailable"),
                }
                component_modes[sleeve_name] = "UNKNOWN"
                continue
            gate = evaluate_universe_lineage(run_meta=component_run_meta, results_dir=component.get("results_dir"))
            component_gates[sleeve_name] = gate
            component_modes[sleeve_name] = str(gate.get("lineage_mode") or "UNKNOWN")
        component_statuses = {
            name: _normalize_status((gate or {}).get("status"))
            for name, gate in component_gates.items()
            if isinstance(gate, Mapping)
        }
        counts = Counter(component_statuses.values())
        if component_statuses and all(status == "PASS" for status in component_statuses.values()):
            status = "PASS"
            reason = "Unified combo aggregates only sleeve universes that already pass lineage audit."
        elif any(status == "FAIL" for status in component_statuses.values()):
            status = "FAIL"
            reason = "Unified combo aggregates at least one sleeve with FAIL universe lineage."
        elif any(status == "WARN" for status in component_statuses.values()):
            status = "WARN"
            reason = "Unified combo aggregates at least one sleeve with WARN universe lineage."
        else:
            status = "UNKNOWN"
            reason = "Unified combo lacks sufficient sleeve lineage evidence."
        return {
            "status": status,
            "lineage_mode": "COMPONENT_AGGREGATED",
            "reason": reason,
            "evidence": {
                "execution_shell": execution_shell or None,
                "component_statuses": component_statuses,
                "component_lineage_modes": component_modes,
            },
            "metrics": {
                "component_count": int(len(component_statuses)),
                "component_pass_count": int(counts.get("PASS", 0)),
                "component_warn_count": int(counts.get("WARN", 0)),
                "component_fail_count": int(counts.get("FAIL", 0)),
            },
        }
    raw_mode = universe_meta.get("universe_mode") or data_meta.get("universe_mode")
    mode = normalize_universe_mode(raw_mode)
    explicit_mode = str(universe_meta.get("lineage_mode") or universe_meta.get("membership_history_mode") or "").strip().upper()

    lineage_mode = "UNKNOWN"
    if explicit_mode in UNIVERSE_LINEAGE_MODES:
        lineage_mode = explicit_mode
    elif bool(universe_meta.get("pit_dynamic")) or bool(universe_meta.get("historical_membership_dynamic")):
        lineage_mode = "PIT_DYNAMIC"
    elif asset_scope == "cn_etf":
        lineage_mode = "DIRECT_SYMBOLS"
    elif mode == "CUSTOM":
        lineage_mode = "UNKNOWN"
    else:
        try:
            lineage = get_universe_lineage(mode)
        except Exception:
            lineage = None
        if lineage is not None and lineage.resolve_asof_policy == "end_date":
            lineage_mode = "CURRENT_SNAPSHOT"
        elif lineage is not None and lineage.resolve_asof_policy == "start_date":
            lineage_mode = "START_SNAPSHOT"
        elif lineage is not None and bool(universe_meta.get("dynamic_membership")):
            lineage_mode = "PIT_DYNAMIC"

    membership_quality = str(universe_meta.get("membership_data_quality") or "").strip().lower()
    membership_audit_status = str(universe_meta.get("audit_status") or "").strip().lower()
    audit_reason = str(universe_meta.get("audit_reason") or "").strip() or None

    if lineage_mode == "DIRECT_SYMBOLS":
        if asset_scope != "cn_etf":
            status = "UNKNOWN"
            reason = "DIRECT_SYMBOLS lineage is only defined for explicit ETF research entry."
        elif membership_quality in {"whitelist_verified", "catalog_verified"} and membership_audit_status in {"", "pass", "ok"}:
            status = "PASS"
            reason = "ETF research entry uses an explicit catalog whitelist instead of stock PIT membership history."
        elif membership_quality in {"missing", ""}:
            status = "FAIL"
            reason = "ETF research entry is missing catalog whitelist evidence."
        else:
            status = "WARN"
            reason = (
                "ETF research entry uses direct symbols, but whitelist evidence is incomplete "
                f"(audit_reason={audit_reason or 'unknown'})."
            )
    elif lineage_mode == "PIT_DYNAMIC":
        if membership_quality == "static_fallback" or membership_audit_status == "blocked":
            status = "FAIL"
            reason = (
                "PIT_DYNAMIC membership history was classified as static_fallback "
                f"(audit_reason={audit_reason or 'unknown'})."
            )
        elif membership_quality == "approximate" or membership_audit_status == "warn":
            status = "WARN"
            reason = (
                "PIT_DYNAMIC membership history is only approximate "
                f"(audit_reason={audit_reason or 'unknown'})."
            )
        elif membership_quality == "pit_verified" and membership_audit_status in {"", "ok"}:
            status = "PASS"
            reason = "PIT_DYNAMIC membership history carries PIT-like shape and calendar lineage evidence."
        elif membership_quality == "missing" or membership_audit_status == "error":
            status = "FAIL"
            reason = "PIT_DYNAMIC membership history is missing or unreadable."
        else:
            status = "UNKNOWN"
            reason = "Universe lineage is PIT_DYNAMIC, but membership audit evidence is incomplete."
    else:
        status_map = {
            "START_SNAPSHOT": "WARN",
            "CURRENT_SNAPSHOT": "FAIL",
            "UNKNOWN": "UNKNOWN",
        }
        reason_map = {
            "START_SNAPSHOT": "股票池仅在回测起始日解析一次，存在幸存者偏差风险。",
            "CURRENT_SNAPSHOT": "股票池使用当前或结束时点快照回看历史，存在明显幸存者偏差。",
            "UNKNOWN": "现有元信息不足以判断股票池历史口径。",
        }
        status = status_map.get(lineage_mode, "UNKNOWN")
        reason = reason_map.get(lineage_mode, "现有元信息不足以判断股票池历史口径。")

    evidence = {
        "universe_mode": mode,
        "symbols_source": universe_meta.get("symbols_source"),
        "load_table": universe_meta.get("load_table"),
        "resolve_asof": universe_meta.get("resolve_asof"),
        "dynamic_all_a_entry": universe_meta.get("dynamic_all_a_entry"),
        "filter_mode": universe_meta.get("filter_mode"),
        "membership_source": universe_meta.get("membership_source"),
        "membership_data_quality": universe_meta.get("membership_data_quality"),
        "audit_status": universe_meta.get("audit_status"),
        "audit_reason": universe_meta.get("audit_reason"),
        "covers_required_start": universe_meta.get("covers_required_start"),
        "covers_required_end": universe_meta.get("covers_required_end"),
        "provider_floor_date": universe_meta.get("provider_floor_date"),
        "rebalance_calendar_version": universe_meta.get("rebalance_calendar_version"),
        "rebalance_calendar_source": universe_meta.get("rebalance_calendar_source"),
        "rebalance_calendar_generated_at": universe_meta.get("rebalance_calendar_generated_at"),
        "etf_batch": universe_meta.get("etf_batch"),
        "etf_symbols": universe_meta.get("etf_symbols"),
        "coverage_start": universe_meta.get("coverage_start"),
        "coverage_end": universe_meta.get("coverage_end"),
        "price_series_semantics": universe_meta.get("price_series_semantics"),
    }
    metrics = {
        "membership_history_rows": _safe_int(universe_meta.get("membership_history_rows")),
        "raw_count": _safe_int(universe_meta.get("raw_count")),
        "tradable_symbols": _safe_int(universe_meta.get("tradable_symbols")),
        "after_filters_symbols": _safe_int(universe_meta.get("after_filters_symbols")),
        "distinct_start_dates": _safe_int(universe_meta.get("distinct_start_dates")),
        "open_rows": _safe_int(universe_meta.get("open_rows")),
        "closed_rows": _safe_int(universe_meta.get("closed_rows")),
        "refresh_event_count": _safe_int(universe_meta.get("refresh_event_count")),
        "zero_diff_refresh_event_count": _safe_int(universe_meta.get("zero_diff_refresh_event_count")),
    }
    return {
        "status": status,
        "lineage_mode": lineage_mode,
        "reason": reason,
        "evidence": evidence,
        "metrics": metrics,
    }


def evaluate_price_adjustment_integrity(
    *,
    run_meta: Mapping[str, Any] | None,
    results_dir: str | Path | None = None,
) -> dict[str, Any]:
    run_meta_obj = dict(run_meta or {})
    data_meta = dict(run_meta_obj.get("data") or {})
    universe_meta = dict(run_meta_obj.get("universe") or {})
    stage_pipeline = dict(run_meta_obj.get("stage_pipeline") or {})
    data_bundle_meta = dict(run_meta_obj.get("data_bundle") or {})
    asset_role = str(data_meta.get("asset_role") or "").strip().lower()
    execution_shell = str(stage_pipeline.get("execution_shell") or "").strip().lower()
    if asset_role == "unified_multi_sleeve_combo" or execution_shell == "unified_combo_phase1":
        component_gates: dict[str, dict[str, Any]] = {}
        for sleeve_name, component in _load_combo_component_records(run_meta=run_meta_obj, results_dir=results_dir).items():
            component_run_meta = component.get("run_meta")
            if not isinstance(component_run_meta, Mapping):
                component_gates[sleeve_name] = {
                    "status": "UNKNOWN",
                    "reason": str(component.get("read_error") or "component run_meta unavailable"),
                }
                continue
            component_gates[sleeve_name] = evaluate_price_adjustment_integrity(
                run_meta=component_run_meta,
                results_dir=component.get("results_dir"),
            )
        component_statuses = {
            name: _normalize_status((gate or {}).get("status"))
            for name, gate in component_gates.items()
            if isinstance(gate, Mapping)
        }
        counts = Counter(component_statuses.values())
        if component_statuses and all(status == "PASS" for status in component_statuses.values()):
            status = "PASS"
            reason = "Unified combo aggregates only sleeves with PASS price-adjustment integrity."
        elif any(status == "FAIL" for status in component_statuses.values()):
            status = "FAIL"
            reason = "Unified combo aggregates at least one sleeve with FAIL price-adjustment integrity."
        elif any(status == "WARN" for status in component_statuses.values()):
            status = "WARN"
            reason = "Unified combo aggregates at least one sleeve with WARN price-adjustment integrity."
        else:
            status = "UNKNOWN"
            reason = "Unified combo lacks sufficient sleeve price-adjustment evidence."
        return {
            "status": status,
            "reason": reason,
            "evidence": {"component_statuses": component_statuses},
            "metrics": {
                "component_count": int(len(component_statuses)),
                "component_pass_count": int(counts.get("PASS", 0)),
                "component_warn_count": int(counts.get("WARN", 0)),
                "component_fail_count": int(counts.get("FAIL", 0)),
            },
        }

    price_adj_mode = str(
        data_bundle_meta.get("price_adj_mode")
        or universe_meta.get("price_adj_mode")
        or run_meta_obj.get("price_adj_mode")
        or "none"
    ).strip().lower()
    adj_stats = dict(run_meta_obj.get("adj_factor_stats") or data_bundle_meta.get("adj_factor_stats") or {})
    if price_adj_mode == "none":
        status = "PASS"
        reason = "Price adjustment is disabled for this run."
    elif not adj_stats:
        status = "UNKNOWN"
        reason = "Price adjustment is enabled, but adj_factor stale statistics are missing."
    else:
        fail_count = int(adj_stats.get("symbols_exceeding_fail_count") or 0)
        warn_count = int(adj_stats.get("symbols_exceeding_warn_count") or 0)
        null_count = int(adj_stats.get("null_count") or 0)
        symbol_count = int(adj_stats.get("symbol_count") or 0)
        if symbol_count <= 0:
            status = "UNKNOWN"
            reason = "Price adjustment is enabled, but adj_factor statistics cover zero symbols."
        elif fail_count > 0:
            status = "FAIL"
            reason = "adj_factor contains stale spans beyond the fail threshold."
        elif warn_count > 0 or null_count > 0:
            status = "WARN"
            reason = "adj_factor contains missing or stale spans that require review."
        else:
            status = "PASS"
            reason = "adj_factor statistics do not show stale spans beyond warning thresholds."
    evidence = {
        "price_adj_mode": price_adj_mode,
        "worst_after_valid_symbol": adj_stats.get("worst_after_valid_symbol"),
        "worst_after_valid_end_date": adj_stats.get("worst_after_valid_end_date"),
    }
    metrics = {
        "symbol_count": int(adj_stats.get("symbol_count") or 0),
        "null_count": int(adj_stats.get("null_count") or 0),
        "symbols_with_missing_count": int(adj_stats.get("symbols_with_missing_count") or 0),
        "max_consecutive_missing_rows": int(adj_stats.get("max_consecutive_missing_rows") or 0),
        "max_consecutive_missing_after_valid_rows": int(adj_stats.get("max_consecutive_missing_after_valid_rows") or 0),
        "symbols_exceeding_warn_count": int(adj_stats.get("symbols_exceeding_warn_count") or 0),
        "symbols_exceeding_fail_count": int(adj_stats.get("symbols_exceeding_fail_count") or 0),
        "warn_threshold_rows": int(adj_stats.get("warn_threshold_rows") or _ADJ_FACTOR_STALE_WARN_THRESHOLD),
        "fail_threshold_rows": int(adj_stats.get("fail_threshold_rows") or _ADJ_FACTOR_STALE_FAIL_THRESHOLD),
    }
    return {"status": status, "reason": reason, "evidence": evidence, "metrics": metrics}


def evaluate_etf_beta_sleeve(
    *,
    run_meta: Mapping[str, Any] | None,
    results_dir: str | Path | None = None,
) -> dict[str, Any] | None:
    run_meta_obj = dict(run_meta or {})
    data_meta = dict(run_meta_obj.get("data") or {})
    universe_meta = dict(run_meta_obj.get("universe") or {})
    governed_meta = dict(run_meta_obj.get("governed_a_share") or {})
    asset_scope = str(
        data_meta.get("asset_scope")
        or universe_meta.get("asset_scope")
        or (run_meta_obj.get("asset_context") or {}).get("asset_scope")
        or ""
    ).strip().lower()
    etf_meta = dict(governed_meta.get("etf_beta") or {})
    summary = run_meta_obj.get("etf_beta")
    has_etf_summary = isinstance(summary, Mapping)
    combo_etf_budget_roles = dict(run_meta_obj.get("etf_budget_roles") or {})
    combo_sleeves = dict(run_meta_obj.get("sleeves") or {})
    has_combo_etf_evidence = bool(combo_etf_budget_roles) or isinstance(combo_sleeves.get("etf_beta"), Mapping)
    if asset_scope != "cn_etf" and not bool(etf_meta.get("enabled")) and not has_etf_summary and not has_combo_etf_evidence:
        return None
    if asset_scope not in {"cn_etf", "cn_a_equity", "cn_a_multi_sleeve"}:
        return None
    governed_snapshot = dict(run_meta_obj.get("governed_snapshot") or {})
    account_budget_runtime_reference = dict(
        run_meta_obj.get("account_budget_runtime_reference")
        or {}
    )
    etf_budget_roles = dict(
        governed_snapshot.get("etf_budget_roles")
        or account_budget_runtime_reference.get("etf_budget_roles")
        or {}
    )
    etf_budget_roles_target = dict(etf_budget_roles.get("target") or {})
    etf_budget_roles_actual = dict(etf_budget_roles.get("actual") or {})
    etf_budget_roles_deviation = dict(etf_budget_roles.get("deviation") or {})
    etf_budget_roles_contract_version = str(etf_budget_roles.get("contract_version") or "").strip() or None
    etf_budget_roles_effective_state_5 = str(etf_budget_roles.get("effective_state_5") or "").strip() or None

    if asset_scope != "cn_etf" and not isinstance(summary, Mapping):
        etf_component = dict(combo_sleeves.get("etf_beta") or {})
        component_exp_id = str(etf_component.get("exp_id") or "").strip()
        component_results_dir = str(etf_component.get("results_dir") or "").strip()
        component_root: Path | None = None
        if component_results_dir:
            candidate_root = Path(component_results_dir)
            if candidate_root.exists():
                component_root = candidate_root
        if component_root is None and component_exp_id and results_dir is not None:
            combo_root = Path(results_dir)
            candidate_root = combo_root.parent / component_exp_id
            if candidate_root.exists():
                component_root = candidate_root
        if component_root is not None:
            component_run_meta, _ = _read_json(component_root / "run_meta.json")
            if isinstance(component_run_meta, Mapping):
                component_gate = evaluate_etf_beta_sleeve(
                    run_meta=component_run_meta,
                    results_dir=component_root,
                )
                if isinstance(component_gate, dict):
                    component_evidence = dict(component_gate.get("evidence") or {})
                    component_metrics = dict(component_gate.get("metrics") or {})
                    component_evidence["combo_component_exp_id"] = component_exp_id or None
                    component_evidence["combo_component_results_dir"] = str(component_root)
                    component_evidence["etf_budget_roles_contract_version"] = etf_budget_roles_contract_version or None
                    component_evidence["etf_budget_roles_effective_state_5"] = etf_budget_roles_effective_state_5 or None
                    component_evidence["etf_budget_roles_target"] = etf_budget_roles_target
                    component_evidence["etf_budget_roles_actual"] = etf_budget_roles_actual
                    component_evidence["etf_budget_roles_deviation"] = etf_budget_roles_deviation
                    component_metrics["avg_target_defense_budget"] = _safe_float(etf_budget_roles_target.get("defense"))
                    component_metrics["avg_target_core_beta_budget"] = _safe_float(etf_budget_roles_target.get("core_beta"))
                    component_metrics["avg_target_alpha_budget"] = _safe_float(etf_budget_roles_target.get("alpha"))
                    component_metrics["avg_actual_defense_budget"] = _safe_float(etf_budget_roles_actual.get("defense"))
                    component_metrics["avg_actual_core_beta_budget"] = _safe_float(etf_budget_roles_actual.get("core_beta"))
                    component_metrics["avg_actual_alpha_budget"] = _safe_float(etf_budget_roles_actual.get("alpha"))
                    component_metrics["avg_defense_budget_gap"] = _safe_float(etf_budget_roles_deviation.get("defense_gap"))
                    component_metrics["avg_core_beta_budget_gap"] = _safe_float(etf_budget_roles_deviation.get("core_beta_gap"))
                    component_metrics["avg_alpha_budget_gap"] = _safe_float(etf_budget_roles_deviation.get("alpha_gap"))
                    return {
                        **component_gate,
                        "evidence": component_evidence,
                        "metrics": component_metrics,
                    }

    if not isinstance(summary, Mapping):
        summary = build_cn_etf_beta_phase1_summary(
            governed_contract=governed_meta,
            universe_meta=universe_meta,
            governor_snapshot=run_meta_obj.get("governed_snapshot") if isinstance(run_meta_obj.get("governed_snapshot"), Mapping) else None,
        )
    summary_obj = dict(summary or {})
    if not summary_obj:
        return {
            "status": "FAIL",
            "reason": "Missing cn_etf_beta Phase 1 summary.",
            "evidence": {"asset_scope": asset_scope},
            "metrics": {"input_count": 0, "eligible_count": 0, "selected_count": 0, "out_of_scope_count": 0},
        }
    if not str(summary_obj.get("formal_alignment_status") or "").strip():
        rebuilt_summary = build_cn_etf_beta_phase1_summary(
            governed_contract=governed_meta,
            universe_meta=universe_meta,
            governor_snapshot=run_meta_obj.get("governed_snapshot") if isinstance(run_meta_obj.get("governed_snapshot"), Mapping) else None,
        )
        if isinstance(rebuilt_summary, Mapping):
            rebuilt_obj = dict(rebuilt_summary)
            for key in (
                "formal_alignment_reference",
                "formal_alignment_status",
                "formal_mainline_compatible",
                "formal_alignment_reason_codes",
                "formal_alignment_evidence",
            ):
                if key not in summary_obj or summary_obj.get(key) in (None, "", [], {}):
                    summary_obj[key] = rebuilt_obj.get(key)

    formal_view = build_etf_beta_formal_view(summary_obj.get("formal_view") or summary_obj)
    research_view = build_etf_beta_research_view(summary_obj.get("research_view") or summary_obj)

    input_etfs = [str(item).strip().upper() for item in list(summary_obj.get("input_etfs") or ()) if str(item).strip()]
    eligible_etfs = [
        str(item).strip().upper()
        for item in list(summary_obj.get("eligible_etfs") or formal_view.get("eligible_etfs") or ())
        if str(item).strip()
    ]
    selected_etfs = [
        str(item).strip().upper()
        for item in list(summary_obj.get("selected_etfs") or formal_view.get("selected_etfs") or ())
        if str(item).strip()
    ]
    out_of_scope_etfs = [
        str(item).strip().upper()
        for item in list(summary_obj.get("out_of_scope_etfs") or formal_view.get("out_of_scope_etfs") or ())
        if str(item).strip()
    ]
    formal_scope = {
        str(item).strip().upper()
        for item in list(summary_obj.get("formal_core_beta_symbols") or formal_view.get("formal_core_beta_symbols") or ())
        + list(summary_obj.get("limited_defense_candidates") or formal_view.get("limited_defense_candidates") or ())
        if str(item).strip()
    }
    selection_reason_codes = {
        str(symbol).strip().upper(): [str(code).strip() for code in list(codes or ()) if str(code).strip()]
        for symbol, codes in dict(summary_obj.get("selection_reason_codes") or formal_view.get("selection_reason_codes") or {}).items()
        if str(symbol).strip()
    }
    out_of_scope_reason_codes = {
        str(symbol).strip().upper(): [str(code).strip() for code in list(codes or ()) if str(code).strip()]
        for symbol, codes in dict(summary_obj.get("out_of_scope_reason_codes") or formal_view.get("out_of_scope_reason_codes") or {}).items()
        if str(symbol).strip()
    }
    invalid_selected = [symbol for symbol in selected_etfs if symbol not in formal_scope]
    missing_selected_reasons = [symbol for symbol in selected_etfs if symbol not in selection_reason_codes]
    missing_out_of_scope_reasons = [symbol for symbol in out_of_scope_etfs if symbol not in out_of_scope_reason_codes]
    vol_target = dict(research_view.get("vol_target") or {})
    source_entry_type = str(summary_obj.get("source_entry_type") or "").strip()
    strategy_role = str(formal_view.get("strategy_role") or summary_obj.get("strategy_role") or "").strip()
    governor_boundary_mode = str(formal_view.get("governor_boundary_mode") or summary_obj.get("governor_boundary_mode") or "").strip()
    local_policy_mode = str(formal_view.get("local_policy_mode") or summary_obj.get("local_policy_mode") or "").strip()
    controlled_accumulation_mode = str(research_view.get("controlled_accumulation_mode") or summary_obj.get("controlled_accumulation_mode") or "").strip()
    governor_boundary = dict(formal_view.get("governor_boundary") or summary_obj.get("governor_boundary") or {})
    local_policy_decision = dict(formal_view.get("local_policy_decision") or summary_obj.get("local_policy_decision") or {})
    boundary_policy_mode = str(
        summary_obj.get("boundary_policy_mode")
        or governor_boundary.get("boundary_policy_mode")
        or local_policy_decision.get("boundary_policy_mode")
        or ""
    ).strip()
    formal_alignment_reference = str(summary_obj.get("formal_alignment_reference") or "").strip() or None
    formal_alignment_status = str(summary_obj.get("formal_alignment_status") or "").strip().lower()
    if formal_alignment_status not in {"formal_mainline", "research_only", "do_not_promote"}:
        formal_alignment_status = "research_only" if summary_obj.get("formal_alignment_status") else "unknown"
    formal_mainline_compatible = _coerce_bool(summary_obj.get("formal_mainline_compatible"))
    formal_alignment_reason_codes = [
        str(code).strip()
        for code in list(summary_obj.get("formal_alignment_reason_codes") or ())
        if str(code).strip()
    ]
    formal_alignment_evidence = dict(summary_obj.get("formal_alignment_evidence") or {})
    counters = dict(run_meta_obj.get("counters") or {})
    order_count = _safe_int(counters.get("orders"))
    trade_count = _safe_int(counters.get("closed_trades"))
    target_exposure = _safe_float(formal_view.get("target_exposure"))
    min_deployable_exposure = _safe_float(formal_view.get("min_deployable_exposure"))
    fallback_allowed = bool(formal_view.get("fallback_allowed", False))
    exposure_policy_family = str(formal_view.get("exposure_policy_family") or "").strip()
    policy_scope = str(formal_view.get("policy_scope") or "").strip()
    broad_based_only = bool(formal_view.get("broad_based_only", False))
    layering_policy = str(research_view.get("layering_policy") or "").strip()
    layering_band = str(research_view.get("layering_band") or "").strip()
    layering_active = bool(research_view.get("layering_active", False))
    layering_reason_codes = [
        str(code).strip()
        for code in list(research_view.get("layering_reason_codes") or ())
        if str(code).strip()
    ]
    target_selected_count_source = str(formal_view.get("target_selected_count_source") or "").strip()
    fallback_allowed_source = str(formal_view.get("fallback_allowed_source") or "").strip()
    trans_up_contract_mode = str(research_view.get("trans_up_contract_mode") or "").strip()
    trans_up_single_seat_core_recovery = bool(research_view.get("trans_up_single_seat_core_recovery", False))
    configured_under_deploy_reason_codes = [
        str(code).strip()
        for code in list(research_view.get("under_deploy_reason_codes") or ())
        if str(code).strip()
    ]
    governor_hard_blocked = bool(
        formal_view.get("governor_hard_blocked", governor_boundary.get("hard_blocked", False))
    )
    governor_hard_block_reason_codes = [
        str(code).strip()
        for code in list(
            formal_view.get("governor_hard_block_reason_codes")
            or governor_boundary.get("hard_block_reason_codes")
            or ()
        )
        if str(code).strip()
    ]
    local_boundary_state = str(
        formal_view.get("local_boundary_state")
        or local_policy_decision.get("boundary_state")
        or ""
    ).strip()
    local_boundary_reason_codes = [
        str(code).strip()
        for code in list(
            formal_view.get("local_boundary_reason_codes")
            or local_policy_decision.get("boundary_reason_codes")
            or ()
        )
        if str(code).strip()
    ]
    avg_target_defense_budget = None
    avg_target_core_beta_budget = None
    avg_target_alpha_budget = None
    avg_actual_defense_budget = None
    avg_actual_core_beta_budget = None
    avg_actual_alpha_budget = None
    avg_defense_budget_gap = None
    avg_core_beta_budget_gap = None
    avg_alpha_budget_gap = None

    deployment_metrics: dict[str, Any] = {
        "observed_day_count": 0,
        "invested_day_count": 0,
        "invested_day_ratio": None,
        "avg_target_exposure": None,
        "avg_actual_exposure": None,
        "median_actual_exposure": None,
        "avg_actual_exposure_on_invested_days": None,
        "avg_actual_risk_exposure": None,
        "avg_actual_fallback_exposure": None,
        "avg_actual_other_exposure": None,
        "avg_actual_core_exposure": None,
        "avg_actual_satellite_exposure": None,
        "avg_actual_defense_exposure": None,
        "avg_target_defense_budget": None,
        "avg_target_core_beta_budget": None,
        "avg_target_alpha_budget": None,
        "avg_actual_defense_budget": None,
        "avg_actual_core_beta_budget": None,
        "avg_actual_alpha_budget": None,
        "avg_defense_budget_gap": None,
        "avg_core_beta_budget_gap": None,
        "avg_alpha_budget_gap": None,
        "avg_cash_share": None,
        "avg_risk_asset_share": None,
        "avg_defense_asset_share": None,
        "empty_day_ratio": None,
        "below_30_ratio": None,
        "below_50_ratio": None,
        "below_80_ratio": None,
        "avg_deployability_gap": None,
        "fallback_exposure_day_count": 0,
        "fallback_exposure_day_ratio": None,
        "fallback_exposure_longest_streak": 0,
        "controlled_accumulation_day_count": 0,
        "controlled_accumulation_day_ratio": None,
        "target_exposure": target_exposure,
        "min_deployable_exposure": min_deployable_exposure,
        "fallback_buy_count": 0,
        "fallback_buy_day_count": 0,
        "under_deploy_reason_counts": {},
        "layering_band_counts": {},
        "absolute_filter_reject_day_count": 0,
        "absolute_filter_reject_reason_counts": {},
        "candidate_pool_reject_reason_counts": {},
        "selection_chain_winner_counts": {},
        "selection_chain_reject_reason_counts": {},
        "signal_count": 0,
        "buy_signal_count": 0,
        "sell_signal_count": 0,
        "unfilled_order_count": 0,
        "primary_bottleneck_layer": None,
        "deployment_assessment": "UNKNOWN",
        "has_governor_boundary_split": bool(governor_boundary),
        "has_local_policy_split": bool(local_policy_decision),
        "boundary_policy_mode": boundary_policy_mode or None,
        "governor_hard_blocked": governor_hard_blocked,
        "zero_deploy_owner": None,
        "reduced_allocation_owner": None,
        "target_contract_drift_detected": False,
        "target_contract_drift_day_count": 0,
        "strategic_floor_target": None,
        "tactical_overlay_target": None,
        "limited_defense_target": None,
        "deployment_pace": None,
        "avg_pace_policy_gap": None,
        "avg_rebalance_timing_gap": None,
        "avg_execution_residual_gap": None,
        "bull_trans_up_bottleneck_summary": {},
        "hard_block_flag_count": 0,
    }
    deployment_evidence: dict[str, Any] = {}
    root = Path(results_dir).resolve() if results_dir is not None else None
    if root is not None:
        portfolio_daily, _ = _read_csv(root / "portfolio_daily.csv")
        orders_df, _ = _read_csv(root / "orders.csv")
        if not portfolio_daily.empty:
            diagnostics_view_df = _build_etf_diagnostics_view_frame(portfolio_daily)
            gross_exposure = _series_numeric(portfolio_daily, "gross_exposure")
            actual_exposure_series = _series_numeric(portfolio_daily, "etf_actual_exposure")
            if actual_exposure_series.dropna().empty:
                actual_exposure_series = gross_exposure
            actual_risk_exposure_series = _series_numeric(portfolio_daily, "etf_actual_risk_exposure")
            actual_fallback_exposure_series = _series_numeric(portfolio_daily, "etf_actual_fallback_exposure")
            actual_other_exposure_series = _series_numeric(portfolio_daily, "etf_actual_other_exposure")
            actual_core_exposure_series = _series_numeric(portfolio_daily, "etf_actual_core_exposure")
            actual_satellite_exposure_series = _series_numeric(portfolio_daily, "etf_actual_satellite_exposure")
            actual_defense_exposure_series = _series_numeric(portfolio_daily, "etf_actual_defense_exposure")
            target_exposure_series = _series_numeric(portfolio_daily, "etf_target_exposure")
            strategic_floor_target_series = pd.to_numeric(diagnostics_view_df.get("strategic_floor_target"), errors="coerce")
            tactical_overlay_target_series = pd.to_numeric(diagnostics_view_df.get("tactical_overlay_target"), errors="coerce")
            limited_defense_target_series = pd.to_numeric(diagnostics_view_df.get("limited_defense_target"), errors="coerce")
            deployment_pace_series = pd.to_numeric(diagnostics_view_df.get("deployment_pace"), errors="coerce")
            pace_policy_gap_series = pd.to_numeric(diagnostics_view_df.get("pace_policy_gap"), errors="coerce")
            rebalance_timing_gap_series = pd.to_numeric(diagnostics_view_df.get("rebalance_timing_gap"), errors="coerce")
            execution_residual_gap_series = pd.to_numeric(diagnostics_view_df.get("execution_residual_gap"), errors="coerce")
            deployability_gap_series = pd.to_numeric(diagnostics_view_df.get("deployability_gap"), errors="coerce")
            cash_series = _series_numeric(portfolio_daily, "cash")
            nav_series = _series_numeric(portfolio_daily, "nav")
            valid_exposure = actual_exposure_series.dropna()
            invested_mask = actual_exposure_series.fillna(0.0) > 1e-9
            fallback_exposure_mask = actual_fallback_exposure_series.fillna(0.0) > 1e-9
            cash_share_series = cash_series.divide(nav_series.where(nav_series.abs() > 1e-12, float("nan")))
            observed_day_count = int(len(portfolio_daily.index))
            invested_day_count = int(invested_mask.sum())
            fallback_exposure_day_count = int(fallback_exposure_mask.sum())
            avg_actual_exposure = float(valid_exposure.mean()) if not valid_exposure.empty else None
            median_actual_exposure = float(valid_exposure.median()) if not valid_exposure.empty else None
            avg_actual_on_invested = (
                float(actual_exposure_series.loc[invested_mask].mean()) if bool(invested_mask.any()) else None
            )
            avg_target_exposure = (
                float(target_exposure_series.dropna().mean()) if not target_exposure_series.dropna().empty else None
            )
            avg_target_on_invested = (
                float(target_exposure_series.loc[invested_mask].mean())
                if bool(invested_mask.any()) and not target_exposure_series.loc[invested_mask].dropna().empty
                else None
            )
            avg_actual_risk_exposure = (
                float(actual_risk_exposure_series.dropna().mean())
                if not actual_risk_exposure_series.dropna().empty
                else None
            )
            avg_actual_fallback_exposure = (
                float(actual_fallback_exposure_series.dropna().mean())
                if not actual_fallback_exposure_series.dropna().empty
                else None
            )
            avg_actual_other_exposure = (
                float(actual_other_exposure_series.dropna().mean())
                if not actual_other_exposure_series.dropna().empty
                else None
            )
            avg_actual_core_exposure = (
                float(actual_core_exposure_series.dropna().mean())
                if not actual_core_exposure_series.dropna().empty
                else None
            )
            avg_actual_satellite_exposure = (
                float(actual_satellite_exposure_series.dropna().mean())
                if not actual_satellite_exposure_series.dropna().empty
                else None
            )
            avg_actual_defense_exposure = (
                float(actual_defense_exposure_series.dropna().mean())
                if not actual_defense_exposure_series.dropna().empty
                else None
            )
            strategic_floor_target = (
                float(strategic_floor_target_series.dropna().mean())
                if not strategic_floor_target_series.dropna().empty
                else None
            )
            tactical_overlay_target = (
                float(tactical_overlay_target_series.dropna().mean())
                if not tactical_overlay_target_series.dropna().empty
                else None
            )
            limited_defense_target = (
                float(limited_defense_target_series.dropna().mean())
                if not limited_defense_target_series.dropna().empty
                else None
            )
            avg_deployment_pace = (
                float(deployment_pace_series.dropna().mean())
                if not deployment_pace_series.dropna().empty
                else None
            )
            avg_pace_policy_gap = (
                float(pace_policy_gap_series.dropna().mean())
                if not pace_policy_gap_series.dropna().empty
                else None
            )
            avg_rebalance_timing_gap = (
                float(rebalance_timing_gap_series.dropna().mean())
                if not rebalance_timing_gap_series.dropna().empty
                else None
            )
            avg_execution_residual_gap = (
                float(execution_residual_gap_series.dropna().mean())
                if not execution_residual_gap_series.dropna().empty
                else None
            )
            avg_cash_share = float(cash_share_series.dropna().mean()) if not cash_share_series.dropna().empty else None
            avg_deployability_gap = (
                float(deployability_gap_series.dropna().mean())
                if not deployability_gap_series.dropna().empty
                else None
            )
            avg_target_defense_budget = _safe_float(etf_budget_roles_target.get("defense"))
            avg_target_core_beta_budget = _safe_float(etf_budget_roles_target.get("core_beta"))
            avg_target_alpha_budget = _safe_float(etf_budget_roles_target.get("alpha"))
            avg_actual_defense_budget = _safe_float(etf_budget_roles_actual.get("defense"))
            avg_actual_core_beta_budget = _safe_float(etf_budget_roles_actual.get("core_beta"))
            avg_actual_alpha_budget = _safe_float(etf_budget_roles_actual.get("alpha"))
            avg_defense_budget_gap = _safe_float(etf_budget_roles_deviation.get("defense_gap"))
            avg_core_beta_budget_gap = _safe_float(etf_budget_roles_deviation.get("core_beta_gap"))
            avg_alpha_budget_gap = _safe_float(etf_budget_roles_deviation.get("alpha_gap"))
            empty_day_ratio = float((actual_exposure_series.fillna(0.0) <= 1e-9).mean())
            below_30_ratio = float((actual_exposure_series.fillna(0.0) < 0.30).mean())
            below_50_ratio = float((actual_exposure_series.fillna(0.0) < 0.50).mean())
            below_80_ratio = float((actual_exposure_series.fillna(0.0) < 0.80).mean())
            under_deploy_counter: Counter[str] = Counter()
            layering_band_counter: Counter[str] = Counter()
            absolute_filter_reject_counter: Counter[str] = Counter()
            selection_chain_winner_counter: Counter[str] = Counter()
            selection_chain_reject_counter: Counter[str] = Counter()
            candidate_pool_reject_counter: Counter[str] = Counter()
            controlled_accumulation_day_count = 0
            absolute_filter_reject_day_count = 0
            current_fallback_streak = 0
            longest_fallback_streak = 0
            latest_governor_snapshot: dict[str, Any] | None = None
            latest_diagnostics_snapshot: dict[str, Any] | None = None
            portfolio_target_by_date: dict[str, float] = {}
            governor_target_by_date: dict[str, float] = {}
            diagnostics_target_by_date: dict[str, float] = {}
            diagnostics_target_weight_by_date: dict[str, float] = {}
            diagnostics_target_weight_by_date_symbol: dict[str, dict[str, float]] = {}
            hard_block_flag_counter: Counter[str] = Counter()
            for _idx, row in portfolio_daily.iterrows():
                governor_payload: dict[str, Any] = {}
                diagnostics_payload: dict[str, Any] = {}
                diagnostics_formal_view: dict[str, Any] = {}
                diagnostics_research_view: dict[str, Any] = {}
                row_date = str(row.get("date") or "").strip()
                raw_governor = row.get("governor_budget_json")
                raw_diagnostics = row.get("diagnostics_input_json")
                row_target_exposure = _safe_float(row.get("etf_target_exposure"))
                if row_date and row_target_exposure is not None:
                    portfolio_target_by_date[row_date] = float(row_target_exposure)
                if isinstance(raw_governor, str) and raw_governor.strip():
                    try:
                        governor_payload = dict(json.loads(raw_governor) or {})
                    except Exception:
                        governor_payload = {}
                diagnostics_payload, diagnostics_formal_view, diagnostics_research_view = _extract_etf_diagnostics_views(raw_diagnostics)
                if governor_payload:
                    latest_governor_snapshot = governor_payload
                    governor_target_exposure = _safe_float(governor_payload.get("target_exposure"))
                    if row_date and governor_target_exposure is not None:
                        governor_target_by_date[row_date] = float(governor_target_exposure)
                    for code in list(governor_payload.get("under_deploy_reason_codes") or ()):
                        text = str(code).strip()
                        if text:
                            under_deploy_counter[text] += 1
                    for code in list(governor_payload.get("hard_block_flags") or ()):
                        text = str(code).strip()
                        if text:
                            hard_block_flag_counter[text] += 1
                    governor_layering_band = str(governor_payload.get("layering_band") or "").strip()
                    if governor_layering_band:
                        layering_band_counter[governor_layering_band] += 1
                        if governor_layering_band in {"LIGHT_ACCUMULATE", "CONTROLLED_TRANS_DOWN"}:
                            controlled_accumulation_day_count += 1
                if diagnostics_payload:
                    latest_diagnostics_snapshot = {
                        **diagnostics_payload,
                        "formal_view": diagnostics_formal_view,
                        "research_view": diagnostics_research_view,
                    }
                    diagnostics_targets = {
                        str(symbol).strip().upper(): _safe_float(value)
                        for symbol, value in dict(diagnostics_formal_view.get("targets") or {}).items()
                        if str(symbol).strip()
                    }
                    diagnostics_target_exposure = _safe_float(
                        diagnostics_formal_view.get("target_exposure", diagnostics_payload.get("etf_beta_target_exposure"))
                    )
                    if row_date and diagnostics_target_exposure is not None:
                        diagnostics_target_by_date[row_date] = float(diagnostics_target_exposure)
                    diagnostics_target_weight = sum(
                        float(value)
                        for value in diagnostics_targets.values()
                        if value is not None
                    )
                    if row_date and diagnostics_targets:
                        diagnostics_target_weight_by_date[row_date] = float(diagnostics_target_weight)
                        diagnostics_target_weight_by_date_symbol[row_date] = {
                            _normalize_etf_symbol_key(symbol): float(value)
                            for symbol, value in diagnostics_targets.items()
                            if value is not None and _normalize_etf_symbol_key(symbol)
                        }
                    for code in list(diagnostics_research_view.get("under_deploy_reason_codes") or ()):
                        text = str(code).strip()
                        if text:
                            under_deploy_counter[text] += 1
                    for code in list(diagnostics_research_view.get("hard_block_flags") or ()):
                        text = str(code).strip()
                        if text:
                            hard_block_flag_counter[text] += 1
                    filter_reject_count = int(_safe_float(diagnostics_research_view.get("absolute_filter_reject_count")) or 0)
                    if filter_reject_count > 0:
                        absolute_filter_reject_day_count += 1
                    for code, count in dict(diagnostics_research_view.get("absolute_filter_reject_reason_counts") or {}).items():
                        text = str(code).strip()
                        value = int(_safe_float(count) or 0)
                        if text and value > 0:
                            absolute_filter_reject_counter[text] += value
                    for code, count in dict(diagnostics_research_view.get("candidate_pool_reject_reason_counts") or {}).items():
                        text = str(code).strip()
                        value = int(_safe_float(count) or 0)
                        if text and value > 0:
                            candidate_pool_reject_counter[text] = max(candidate_pool_reject_counter.get(text, 0), value)
                    for code, count in dict(diagnostics_research_view.get("selection_chain_winner_counts") or {}).items():
                        text = str(code).strip()
                        value = int(_safe_float(count) or 0)
                        if text and value > 0:
                            selection_chain_winner_counter[text] += value
                    for code, count in dict(diagnostics_research_view.get("selection_chain_reject_reason_counts") or {}).items():
                        text = str(code).strip()
                        value = int(_safe_float(count) or 0)
                        if text and value > 0:
                            selection_chain_reject_counter[text] += value
                    diagnostics_layering_band = str(diagnostics_research_view.get("layering_band") or "").strip()
                    if diagnostics_layering_band:
                        layering_band_counter[diagnostics_layering_band] += 1
                        if (
                            diagnostics_layering_band in {"LIGHT_ACCUMULATE", "CONTROLLED_TRANS_DOWN"}
                            and not governor_payload
                        ):
                            controlled_accumulation_day_count += 1
                if bool(fallback_exposure_mask.iloc[_idx]):
                    current_fallback_streak += 1
                    longest_fallback_streak = max(longest_fallback_streak, current_fallback_streak)
                else:
                    current_fallback_streak = 0

            if target_exposure is None and latest_governor_snapshot is not None:
                target_exposure = _safe_float(latest_governor_snapshot.get("target_exposure"))
            if min_deployable_exposure is None and latest_governor_snapshot is not None:
                min_deployable_exposure = _safe_float(latest_governor_snapshot.get("min_deployable_exposure"))
            if latest_governor_snapshot is not None:
                exposure_policy_family = exposure_policy_family or str(latest_governor_snapshot.get("exposure_policy_family") or "").strip()
                policy_scope = policy_scope or str(latest_governor_snapshot.get("policy_scope") or "").strip()
                broad_based_only = bool(latest_governor_snapshot.get("broad_based_only", broad_based_only))
                layering_policy = layering_policy or str(latest_governor_snapshot.get("layering_policy") or "").strip()
                layering_band = layering_band or str(latest_governor_snapshot.get("layering_band") or "").strip()
                layering_active = bool(latest_governor_snapshot.get("layering_active", layering_active))
                if not layering_reason_codes:
                    layering_reason_codes = [
                        str(code).strip()
                        for code in list(latest_governor_snapshot.get("layering_reason_codes") or ())
                        if str(code).strip()
                    ]
                fallback_allowed_source = fallback_allowed_source or str(latest_governor_snapshot.get("fallback_allowed_source") or "").strip()
                target_selected_count_source = target_selected_count_source or str(latest_governor_snapshot.get("target_selected_count_source") or "").strip()
                trans_up_contract_mode = trans_up_contract_mode or str(latest_governor_snapshot.get("trans_up_contract_mode") or "").strip()
                trans_up_single_seat_core_recovery = bool(
                    latest_governor_snapshot.get("trans_up_single_seat_core_recovery", trans_up_single_seat_core_recovery)
                )
                if strategic_floor_target is None:
                    strategic_floor_target = _safe_float(latest_governor_snapshot.get("strategic_floor_cap"))
                if tactical_overlay_target is None:
                    tactical_overlay_target = _safe_float(latest_governor_snapshot.get("tactical_overlay_cap"))
                if avg_deployment_pace is None:
                    avg_deployment_pace = _safe_float(latest_governor_snapshot.get("deployment_pace"))
            if avg_target_exposure is None:
                avg_target_exposure = target_exposure
            if latest_governor_snapshot is not None:
                fallback_allowed = bool(latest_governor_snapshot.get("fallback_allowed", fallback_allowed))
            if latest_diagnostics_snapshot is not None and not fallback_allowed:
                fallback_mode_text = str(latest_diagnostics_snapshot.get("etf_beta_fallback_mode") or "").strip().lower()
                fallback_allowed = fallback_mode_text in {"cash", "single_symbol"}
            if latest_diagnostics_snapshot is not None:
                latest_diagnostics_formal = dict(latest_diagnostics_snapshot.get("formal_view") or {})
                latest_diagnostics_research = dict(latest_diagnostics_snapshot.get("research_view") or {})
                exposure_policy_family = exposure_policy_family or str(latest_diagnostics_formal.get("exposure_policy_family") or "").strip()
                policy_scope = policy_scope or str(latest_diagnostics_formal.get("policy_scope") or "").strip()
                broad_based_only = bool(latest_diagnostics_formal.get("broad_based_only", broad_based_only))
                layering_policy = layering_policy or str(latest_diagnostics_research.get("layering_policy") or "").strip()
                layering_band = layering_band or str(latest_diagnostics_research.get("layering_band") or "").strip()
                layering_active = bool(latest_diagnostics_research.get("layering_active", layering_active))
                if not layering_reason_codes:
                    layering_reason_codes = [
                        str(code).strip()
                        for code in list(latest_diagnostics_research.get("layering_reason_codes") or ())
                        if str(code).strip()
                    ]
                fallback_allowed_source = fallback_allowed_source or str(latest_diagnostics_formal.get("fallback_allowed_source") or "").strip()
                target_selected_count_source = target_selected_count_source or str(latest_diagnostics_formal.get("target_selected_count_source") or "").strip()
                trans_up_contract_mode = trans_up_contract_mode or str(latest_diagnostics_research.get("trans_up_contract_mode") or "").strip()
                trans_up_single_seat_core_recovery = bool(
                    latest_diagnostics_research.get("trans_up_single_seat_core_recovery", trans_up_single_seat_core_recovery)
                )
                if strategic_floor_target is None:
                    strategic_floor_target = _safe_float(latest_diagnostics_research.get("strategic_floor_cap"))
                if tactical_overlay_target is None:
                    tactical_overlay_target = _safe_float(latest_diagnostics_research.get("tactical_overlay_cap"))
                if limited_defense_target is None:
                    limited_defense_target = _safe_float(latest_diagnostics_research.get("limited_defense_cap"))
                if avg_deployment_pace is None:
                    avg_deployment_pace = _safe_float(latest_diagnostics_research.get("deployment_pace"))

            deployment_assessment = "TRACEABLE"
            target_exposure_reference = avg_target_exposure if avg_target_exposure is not None else target_exposure
            actual_exposure_reference = avg_actual_exposure
            if _is_formal_stabilizer_role(strategy_role, local_policy_mode) and avg_actual_on_invested is not None:
                actual_exposure_reference = avg_actual_on_invested
                if avg_target_on_invested is not None:
                    target_exposure_reference = avg_target_on_invested
            if invested_day_count <= 0:
                deployment_assessment = "NO_DEPLOYMENT"
            elif (
                target_exposure_reference is not None
                and actual_exposure_reference is not None
                and actual_exposure_reference < float(target_exposure_reference) * 0.5
            ):
                deployment_assessment = "UNDERDEPLOYED"
            elif (
                min_deployable_exposure is not None
                and avg_actual_on_invested is not None
                and avg_actual_on_invested < float(min_deployable_exposure)
            ):
                deployment_assessment = "UNDERDEPLOYED"
            absolute_filter_total = int(sum(absolute_filter_reject_counter.values()))
            selection_chain_total = int(sum(selection_chain_reject_counter.values()))
            candidate_pool_total = int(sum(candidate_pool_reject_counter.values()))
            primary_bottleneck_layer: str | None = None
            if absolute_filter_total >= max(selection_chain_total, candidate_pool_total, 1):
                primary_bottleneck_layer = "absolute_filter"
            elif selection_chain_total >= max(candidate_pool_total, 1):
                primary_bottleneck_layer = "selection_chain"
            elif candidate_pool_total > 0:
                primary_bottleneck_layer = "candidate_pool"

            deployment_metrics.update(
                {
                    "observed_day_count": observed_day_count,
                    "invested_day_count": invested_day_count,
                    "invested_day_ratio": (float(invested_day_count) / float(observed_day_count)) if observed_day_count > 0 else None,
                    "avg_target_exposure": avg_target_exposure,
                    "avg_actual_exposure": avg_actual_exposure,
                    "median_actual_exposure": median_actual_exposure,
                    "avg_actual_exposure_on_invested_days": avg_actual_on_invested,
                    "avg_actual_risk_exposure": avg_actual_risk_exposure,
                    "avg_actual_fallback_exposure": avg_actual_fallback_exposure,
                    "avg_actual_other_exposure": avg_actual_other_exposure,
                    "avg_actual_core_exposure": avg_actual_core_exposure,
                    "avg_actual_satellite_exposure": avg_actual_satellite_exposure,
            "avg_actual_defense_exposure": avg_actual_defense_exposure,
            "avg_target_defense_budget": avg_target_defense_budget,
            "avg_target_core_beta_budget": avg_target_core_beta_budget,
            "avg_target_alpha_budget": avg_target_alpha_budget,
            "avg_actual_defense_budget": avg_actual_defense_budget,
            "avg_actual_core_beta_budget": avg_actual_core_beta_budget,
            "avg_actual_alpha_budget": avg_actual_alpha_budget,
            "avg_defense_budget_gap": avg_defense_budget_gap,
            "avg_core_beta_budget_gap": avg_core_beta_budget_gap,
            "avg_alpha_budget_gap": avg_alpha_budget_gap,
            "avg_cash_share": avg_cash_share,
                    "avg_risk_asset_share": avg_actual_risk_exposure,
                    "avg_defense_asset_share": avg_actual_fallback_exposure,
                    "empty_day_ratio": empty_day_ratio,
                    "below_30_ratio": below_30_ratio,
                    "below_50_ratio": below_50_ratio,
                    "below_80_ratio": below_80_ratio,
                    "avg_deployability_gap": avg_deployability_gap,
                    "fallback_exposure_day_count": fallback_exposure_day_count,
                    "fallback_exposure_day_ratio": (
                        float(fallback_exposure_day_count) / float(observed_day_count)
                        if observed_day_count > 0
                        else None
                    ),
                    "fallback_exposure_longest_streak": longest_fallback_streak,
                    "controlled_accumulation_day_count": controlled_accumulation_day_count,
                    "controlled_accumulation_day_ratio": (
                        float(controlled_accumulation_day_count) / float(observed_day_count)
                        if observed_day_count > 0
                        else None
                    ),
                    "target_exposure": target_exposure,
                    "strategic_floor_target": strategic_floor_target,
                    "tactical_overlay_target": tactical_overlay_target,
                    "limited_defense_target": limited_defense_target,
                    "deployment_pace": avg_deployment_pace,
                    "avg_pace_policy_gap": avg_pace_policy_gap,
                    "avg_rebalance_timing_gap": avg_rebalance_timing_gap,
                    "avg_execution_residual_gap": avg_execution_residual_gap,
                    "trans_up_contract_mode": trans_up_contract_mode or None,
                    "trans_up_single_seat_core_recovery": bool(trans_up_single_seat_core_recovery),
                    "hard_block_flag_count": int(sum(hard_block_flag_counter.values())),
                    "min_deployable_exposure": min_deployable_exposure,
                    "under_deploy_reason_counts": dict(sorted(under_deploy_counter.items())),
                    "hard_block_flag_counts": dict(sorted(hard_block_flag_counter.items())),
                    "layering_band_counts": dict(sorted(layering_band_counter.items())),
                    "absolute_filter_reject_day_count": absolute_filter_reject_day_count,
                    "absolute_filter_reject_reason_counts": dict(sorted(absolute_filter_reject_counter.items())),
                    "candidate_pool_reject_reason_counts": dict(sorted(candidate_pool_reject_counter.items())),
                    "selection_chain_winner_counts": dict(sorted(selection_chain_winner_counter.items())),
                    "selection_chain_reject_reason_counts": dict(sorted(selection_chain_reject_counter.items())),
                    "primary_bottleneck_layer": primary_bottleneck_layer,
                    "deployment_assessment": deployment_assessment,
                }
            )
            deployment_metrics["bull_trans_up_bottleneck_summary"] = _summarize_etf_bull_trans_up_bottleneck(
                portfolio_daily,
                orders_df,
            )
            deployment_evidence["latest_governor_snapshot"] = latest_governor_snapshot
            deployment_evidence["latest_diagnostics_snapshot"] = latest_diagnostics_snapshot
            deployment_evidence["bull_trans_up_bottleneck_summary"] = dict(
                deployment_metrics.get("bull_trans_up_bottleneck_summary") or {}
            )
            deployment_metrics["buy_signal_count"] = int(_series_numeric(portfolio_daily, "composed_buy_signal_count").fillna(0.0).sum())
            deployment_metrics["sell_signal_count"] = int(_series_numeric(portfolio_daily, "composed_sell_signal_count").fillna(0.0).sum())
            deployment_metrics["signal_count"] = int(deployment_metrics["buy_signal_count"]) + int(deployment_metrics["sell_signal_count"])
        if not orders_df.empty:
            order_reasons = orders_df.get("reason_code", pd.Series(index=orders_df.index, dtype=object)).astype(str).str.strip()
            fallback_mask = order_reasons.eq("ETF_BETA_FALLBACK_BUY")
            if bool(fallback_mask.any()):
                fallback_dates = (
                    pd.to_datetime(orders_df.loc[fallback_mask, "date"], errors="coerce").dt.date.dropna().astype(str)
                    if "date" in orders_df.columns
                    else pd.Series(dtype=object)
                )
                deployment_metrics["fallback_buy_count"] = int(fallback_mask.sum())
                deployment_metrics["fallback_buy_day_count"] = int(fallback_dates.nunique())
            else:
                deployment_metrics["fallback_buy_count"] = 0
                deployment_metrics["fallback_buy_day_count"] = 0
            target_contract_drift_examples: list[dict[str, Any]] = []
            if "meta_json" in orders_df.columns:
                aggregated_order_targets: dict[tuple[str, str], float] = {}
                aggregated_delta_targets: dict[tuple[str, str], float] = {}
                aggregated_order_dates: dict[tuple[str, str], str] = {}
                aggregated_order_context: dict[tuple[str, str], dict[str, bool]] = {}
                for _idx, row in orders_df.iterrows():
                    raw_meta = row.get("meta_json")
                    if not isinstance(raw_meta, str) or not raw_meta.strip():
                        continue
                    try:
                        meta = dict(json.loads(raw_meta) or {})
                    except Exception:
                        continue
                    if str(meta.get("sleeve_id") or meta.get("alpha_id") or "").strip() != "cn_etf_beta":
                        continue
                    order_date = str(row.get("date") or "").strip()
                    if not order_date:
                        continue
                    symbol = str(row.get("symbol") or "").strip().lower()
                    if not symbol:
                        continue
                    decision_date = str(
                        meta.get("signal_date")
                        or row.get("signal_date")
                        or ""
                    ).strip()
                    compare_date = decision_date or order_date
                    order_target_weight = _safe_float(meta.get("target_weight"))
                    final_target_weight = _safe_float(meta.get("final_target_weight"))
                    compare_target_weight = final_target_weight if final_target_weight is not None else order_target_weight
                    if compare_target_weight is None:
                        continue
                    compare_key = (compare_date, symbol)
                    aggregated_order_targets[compare_key] = float(aggregated_order_targets.get(compare_key, 0.0)) + float(compare_target_weight)
                    if order_target_weight is not None:
                        aggregated_delta_targets[compare_key] = float(aggregated_delta_targets.get(compare_key, 0.0)) + float(order_target_weight)
                    aggregated_order_dates.setdefault(compare_key, order_date)
                    selection_reason_codes = meta.get("selection_reason_codes")
                    if isinstance(selection_reason_codes, str):
                        selection_reason_codes = [selection_reason_codes]
                    normalized_selection_reason_codes = {
                        str(code or "").strip()
                        for code in (selection_reason_codes or [])
                        if str(code or "").strip()
                    }
                    context = aggregated_order_context.setdefault(
                        compare_key,
                        {
                            "has_final_target_weight": False,
                            "has_delta_deploy_gap": False,
                            "is_fallback_buy": False,
                            "is_fallback_single_symbol": False,
                        },
                    )
                    if final_target_weight is not None:
                        context["has_final_target_weight"] = True
                    if str(meta.get("target_weight_basis") or "").strip() == "delta_deploy_gap":
                        context["has_delta_deploy_gap"] = True
                    if str(row.get("reason_code") or "").strip() == "ETF_BETA_FALLBACK_BUY":
                        context["is_fallback_buy"] = True
                    if "ETF_BETA_FALLBACK_SINGLE_SYMBOL" in normalized_selection_reason_codes:
                        context["is_fallback_single_symbol"] = True
                for (compare_date, symbol), order_target_weight in aggregated_order_targets.items():
                    formal_targets_by_symbol = diagnostics_target_weight_by_date_symbol.get(compare_date) or {}
                    formal_target_weight = formal_targets_by_symbol.get(symbol)
                    compared_targets = {
                        "formal_target_weight": formal_target_weight,
                        "portfolio_daily_target_exposure": portfolio_target_by_date.get(compare_date),
                        "governor_target_exposure": governor_target_by_date.get(compare_date),
                        "diagnostics_target_exposure": diagnostics_target_by_date.get(compare_date),
                    }
                    order_context = aggregated_order_context.get((compare_date, symbol)) or {}
                    matches_live_target = any(
                        value is not None and abs(float(order_target_weight) - float(value)) <= 1e-9
                        for key, value in compared_targets.items()
                        if key != "formal_target_weight"
                    )
                    allow_fallback_full_replacement = (
                        formal_target_weight is None
                        and bool(formal_targets_by_symbol)
                        and bool(order_context.get("has_final_target_weight"))
                        and bool(order_context.get("has_delta_deploy_gap"))
                        and bool(order_context.get("is_fallback_buy"))
                        and bool(order_context.get("is_fallback_single_symbol"))
                        and matches_live_target
                    )
                    if formal_target_weight is not None:
                        mismatch = abs(float(order_target_weight) - float(formal_target_weight)) > 1e-9
                    elif formal_targets_by_symbol:
                        mismatch = (not allow_fallback_full_replacement) and abs(float(order_target_weight)) > 1e-9
                    else:
                        mismatch = any(
                            value is not None and abs(float(order_target_weight) - float(value)) > 1e-9
                            for key, value in compared_targets.items()
                            if key != "formal_target_weight"
                        )
                    if not mismatch:
                        continue
                    target_contract_drift_examples.append(
                        {
                            "date": aggregated_order_dates.get((compare_date, symbol)) or compare_date,
                            "decision_date": compare_date,
                            "compare_date": compare_date,
                            "symbols": [symbol],
                            "order_target_weight": order_target_weight,
                            "order_delta_target_weight": aggregated_delta_targets.get((compare_date, symbol)),
                            **compared_targets,
                        }
                    )
                    if len(target_contract_drift_examples) >= 5:
                        break
            deployment_metrics["target_contract_drift_detected"] = bool(target_contract_drift_examples)
            deployment_metrics["target_contract_drift_day_count"] = len(
                {str(item.get("date") or "").strip() for item in target_contract_drift_examples if str(item.get("date") or "").strip()}
            )
            if target_contract_drift_examples:
                deployment_evidence["target_contract_drift_examples"] = target_contract_drift_examples
        deployment_metrics["unfilled_order_count"] = max(int(order_count or 0) - int(trade_count or 0), 0)

    requested_budget = _safe_float(research_view.get("requested_budget"))
    applied_budget = _safe_float(research_view.get("applied_budget"))
    cash_weight = _safe_float(research_view.get("cash_weight"))
    defense_weight = _safe_float(research_view.get("defense_weight"))
    equity_core_bucket = _safe_float(research_view.get("equity_core_bucket"))
    defense_tilt_bucket = _safe_float(research_view.get("defense_tilt_bucket"))
    cash_buffer_bucket = _safe_float(research_view.get("cash_buffer_bucket"))
    etf_budget_roles = dict(
        formal_view.get("etf_budget_roles")
        or research_view.get("etf_budget_roles")
        or summary_obj.get("etf_budget_roles")
        or {}
    )
    etf_budget_roles_target = dict(etf_budget_roles.get("target") or {})
    etf_budget_roles_actual = dict(etf_budget_roles.get("actual") or {})
    etf_budget_roles_deviation = dict(etf_budget_roles.get("deviation") or {})
    etf_budget_roles_contract_version = str(etf_budget_roles.get("contract_version") or "").strip()
    etf_budget_roles_effective_state_5 = str(etf_budget_roles.get("effective_state_5") or "").strip()
    target_defense_budget = _safe_float(etf_budget_roles_target.get("defense"))
    target_core_beta_budget = _safe_float(etf_budget_roles_target.get("core_beta"))
    target_alpha_budget = _safe_float(etf_budget_roles_target.get("alpha"))
    actual_defense_budget = _safe_float(etf_budget_roles_actual.get("defense"))
    actual_core_beta_budget = _safe_float(etf_budget_roles_actual.get("core_beta"))
    actual_alpha_budget = _safe_float(etf_budget_roles_actual.get("alpha"))
    defense_budget_gap = _safe_float(etf_budget_roles_deviation.get("defense_gap"))
    core_beta_budget_gap = _safe_float(etf_budget_roles_deviation.get("core_beta_gap"))
    alpha_budget_gap = _safe_float(etf_budget_roles_deviation.get("alpha_gap"))
    deployment_metrics["avg_target_defense_budget"] = target_defense_budget
    deployment_metrics["avg_target_core_beta_budget"] = target_core_beta_budget
    deployment_metrics["avg_target_alpha_budget"] = target_alpha_budget
    deployment_metrics["avg_actual_defense_budget"] = actual_defense_budget
    deployment_metrics["avg_actual_core_beta_budget"] = actual_core_beta_budget
    deployment_metrics["avg_actual_alpha_budget"] = actual_alpha_budget
    deployment_metrics["avg_defense_budget_gap"] = defense_budget_gap
    deployment_metrics["avg_core_beta_budget_gap"] = core_beta_budget_gap
    deployment_metrics["avg_alpha_budget_gap"] = alpha_budget_gap
    target_map = {
        str(symbol).strip().upper(): _safe_float(value)
        for symbol, value in dict(formal_view.get("targets") or {}).items()
        if str(symbol).strip()
    }
    zero_deploy_owner: str | None = None
    reduced_allocation_owner: str | None = None
    if governor_hard_blocked or (requested_budget is not None and requested_budget <= 1e-12):
        zero_deploy_owner = "governor_boundary"
    elif requested_budget is not None and requested_budget > 1e-12 and not target_map:
        zero_deploy_owner = "local_boundary_decision"
    if requested_budget is not None and requested_budget > 1e-12 and local_boundary_state == "REDUCED_ALLOCATION":
        reduced_allocation_owner = "local_boundary_decision"
    elif governor_hard_blocked:
        reduced_allocation_owner = "governor_boundary"
    boundary_attribution = {
        "zero_deploy_owner": zero_deploy_owner,
        "reduced_allocation_owner": reduced_allocation_owner,
        "governor_hard_blocked": governor_hard_blocked,
        "governor_hard_block_reason_codes": list(governor_hard_block_reason_codes),
        "local_boundary_state": local_boundary_state or None,
        "local_boundary_reason_codes": list(local_boundary_reason_codes),
    }

    standalone_entry_types = {
        "cn_etf_research_entry",
        "cn_etf_broad_based_standalone_mainline_entry",
        "cn_etf_phase1_allocation_entry",
    }
    has_governor_boundary_split = bool(governor_boundary)
    has_local_policy_split = bool(local_policy_decision)
    deployment_metrics["has_governor_boundary_split"] = has_governor_boundary_split
    deployment_metrics["has_local_policy_split"] = has_local_policy_split
    deployment_metrics["zero_deploy_owner"] = zero_deploy_owner
    deployment_metrics["reduced_allocation_owner"] = reduced_allocation_owner

    if source_entry_type not in standalone_entry_types:
        status = "FAIL"
        reason = "ETF beta sleeve source entry type is not a supported cn_etf research entry."
    elif formal_alignment_status == "do_not_promote":
        status = "FAIL"
        reason = "ETF beta sleeve is explicitly classified as do_not_promote against the formal Phase 1 mainline."
    elif formal_alignment_status == "research_only":
        status = "WARN"
        reason = "ETF beta sleeve is a research-only branch and must not be promoted as the formal Phase 1 mainline."
    elif (
        strategy_role == "governed_broad_based_standalone_mainline"
        and source_entry_type != "cn_etf_broad_based_standalone_mainline_entry"
    ):
        status = "FAIL"
        reason = "Governed broad-based standalone mainline must use the standalone mainline source entry type."
    elif _is_formal_stabilizer_role(strategy_role, local_policy_mode) and source_entry_type != "cn_etf_phase1_allocation_entry":
        status = "FAIL"
        reason = "Formal ETF stabilizer must use the formal cn_etf_phase1_allocation_entry source entry type."
    elif _is_formal_stabilizer_role(strategy_role, local_policy_mode) and (not has_governor_boundary_split or not has_local_policy_split):
        status = "FAIL"
        reason = "Formal ETF stabilizer is missing the Governor boundary/local policy split."
    elif strategy_role == "governed_broad_based_standalone_mainline" and (not has_governor_boundary_split or not has_local_policy_split):
        status = "FAIL"
        reason = "Standalone broad-based ETF mainline is missing the Governor boundary/local policy split."
    elif invalid_selected:
        status = "FAIL"
        reason = "ETF beta sleeve selected symbols outside Phase 1 formal scope."
    elif (order_count or 0) <= 0 or (trade_count or 0) <= 0:
        status = "FAIL"
        reason = "ETF beta sleeve path is wired, but the smoke window still has zero orders or trades."
    elif deployment_metrics.get("target_contract_drift_detected"):
        status = "FAIL"
        reason = "ETF beta sleeve target exposure contract drift detected across orders and audit artifacts."
    elif missing_selected_reasons or missing_out_of_scope_reasons:
        status = "WARN"
        reason = "ETF beta sleeve selection markers are present, but reason codes are incomplete."
    elif not research_view:
        status = "WARN"
        reason = "ETF beta sleeve formal summary is present, but ETF research view is missing."
    elif deployment_metrics.get("deployment_assessment") == "UNDERDEPLOYED":
        status = "WARN"
        reason = "ETF beta sleeve path is wired and traceable, but actual deployment still remains below stabilizer intent."
    else:
        status = "PASS"
        reason = "ETF beta sleeve formal summary and research explanation are traceable."

    evidence = {
        "strategy_role": strategy_role or None,
        "governor_boundary_mode": governor_boundary_mode or None,
        "local_policy_mode": local_policy_mode or None,
        "controlled_accumulation_mode": controlled_accumulation_mode or None,
        "boundary_policy_mode": boundary_policy_mode or None,
        "source_entry_type": source_entry_type,
        "source_preset_id": summary_obj.get("source_preset_id"),
        "source_batch_id": summary_obj.get("source_batch_id"),
        "template_id": summary_obj.get("template_id"),
        "template_asset_pool_version": summary_obj.get("template_asset_pool_version"),
        "template_role_map": dict(summary_obj.get("template_role_map") or {}),
        "template_proxy_map": dict(summary_obj.get("template_proxy_map") or {}),
        "template_target_formal_symbols": list(summary_obj.get("template_target_formal_symbols") or []),
        "proxy_replacement_mode": summary_obj.get("proxy_replacement_mode"),
        "formal_replacement_pairs": dict(summary_obj.get("formal_replacement_pairs") or {}),
        "core_slot_symbols": list(summary_obj.get("core_slot_symbols") or []),
        "growth_slot_symbols": list(summary_obj.get("growth_slot_symbols") or []),
        "growth_seat_symbol": summary_obj.get("growth_seat_symbol"),
        "core_slot_selected_symbol": summary_obj.get("core_slot_selected_symbol"),
        "growth_slot_selected_symbol": summary_obj.get("growth_slot_selected_symbol"),
        "slot_selection_reason_codes": dict(summary_obj.get("slot_selection_reason_codes") or {}),
        "slot_under_deploy_reason_codes": dict(summary_obj.get("slot_under_deploy_reason_codes") or {}),
        "core_slot_target_exposure": summary_obj.get("core_slot_target_exposure"),
        "growth_slot_target_exposure": summary_obj.get("growth_slot_target_exposure"),
        "core_slot_target_actual_exposure": summary_obj.get("core_slot_target_actual_exposure"),
        "growth_slot_target_actual_exposure": summary_obj.get("growth_slot_target_actual_exposure"),
        "formal_core_beta_symbols": list(summary_obj.get("formal_core_beta_symbols") or []),
        "core_accumulator_symbols": list(summary_obj.get("core_accumulator_symbols") or []),
        "tactical_satellite_symbols": list(summary_obj.get("tactical_satellite_symbols") or []),
        "limited_defense_candidates": list(summary_obj.get("limited_defense_candidates") or []),
        "symbol_role_map": dict(summary_obj.get("symbol_role_map") or {}),
        "formal_alignment_reference": formal_alignment_reference,
        "formal_alignment_status": formal_alignment_status,
        "formal_mainline_compatible": formal_mainline_compatible,
        "formal_alignment_reason_codes": list(formal_alignment_reason_codes),
        "formal_alignment_evidence": formal_alignment_evidence,
        "etf_budget_roles_contract_version": etf_budget_roles_contract_version,
        "etf_budget_roles_effective_state_5": etf_budget_roles_effective_state_5,
        "etf_budget_roles_target": etf_budget_roles_target,
        "etf_budget_roles_actual": etf_budget_roles_actual,
        "etf_budget_roles_deviation": etf_budget_roles_deviation,
        "eligible_etfs": eligible_etfs,
        "selected_etfs": selected_etfs,
        "selection_reason_codes": selection_reason_codes,
        "out_of_scope_etfs": out_of_scope_etfs,
        "out_of_scope_reason_codes": out_of_scope_reason_codes,
        "coverage_summary": dict(formal_view.get("coverage_summary") or summary_obj.get("coverage_summary") or {}),
        "requested_budget": requested_budget,
        "applied_budget": applied_budget,
        "targets": target_map,
        "strategic_floor_cap": research_view.get("strategic_floor_cap"),
        "tactical_overlay_cap": research_view.get("tactical_overlay_cap"),
        "limited_defense_cap": research_view.get("limited_defense_cap"),
        "deployment_pace": research_view.get("deployment_pace"),
        "hard_block_flags": list(research_view.get("hard_block_flags") or []),
        "cash_weight": cash_weight,
        "defense_weight": defense_weight,
        "equity_core_bucket": equity_core_bucket,
        "defense_tilt_bucket": defense_tilt_bucket,
        "cash_buffer_bucket": cash_buffer_bucket,
        "vol_target": vol_target,
        "relative_strength_windows": {
            "fast": summary_obj.get("relative_strength_fast_window"),
            "mid": summary_obj.get("relative_strength_mid_window"),
            "slow": summary_obj.get("relative_strength_slow_window"),
        },
        "relative_strength_weights": {
            "fast": summary_obj.get("relative_strength_fast_weight"),
            "mid": summary_obj.get("relative_strength_mid_weight"),
            "slow": summary_obj.get("relative_strength_slow_weight"),
        },
        "absolute_filter_mode": summary_obj.get("absolute_filter_mode"),
        "absolute_filter_profile": summary_obj.get("absolute_filter_profile"),
        "candidate_pool_profile": summary_obj.get("candidate_pool_profile"),
        "selection_chain_profile": summary_obj.get("selection_chain_profile"),
        "absolute_filter_reject_count": summary_obj.get("absolute_filter_reject_count"),
        "absolute_filter_reject_reason_counts": dict(summary_obj.get("absolute_filter_reject_reason_counts") or {}),
        "candidate_pool_symbols": list(summary_obj.get("candidate_pool_symbols") or []),
        "candidate_pool_coverage_summary": dict(summary_obj.get("candidate_pool_coverage_summary") or {}),
        "candidate_pool_reject_reason_counts": dict(summary_obj.get("candidate_pool_reject_reason_counts") or {}),
        "selection_chain_winner_counts": dict(summary_obj.get("selection_chain_winner_counts") or {}),
        "selection_chain_reject_reason_counts": dict(summary_obj.get("selection_chain_reject_reason_counts") or {}),
        "exposure_policy_family": exposure_policy_family or None,
        "policy_scope": policy_scope or None,
        "broad_based_only": bool(broad_based_only),
        "layering_policy": layering_policy or None,
        "layering_band": layering_band or None,
        "layering_active": bool(layering_active),
        "layering_reason_codes": list(layering_reason_codes),
        "fallback_mode": summary_obj.get("fallback_mode"),
        "fallback_symbol": summary_obj.get("fallback_symbol"),
        "target_selected_count_source": target_selected_count_source or None,
        "fallback_allowed_source": fallback_allowed_source or None,
        "trans_up_contract_mode": trans_up_contract_mode or None,
        "trans_up_single_seat_core_recovery": bool(trans_up_single_seat_core_recovery),
        "target_selected_count_by_state_5": dict(summary_obj.get("target_selected_count_by_state_5") or {}),
        "fallback_allowed_by_state_5": dict(summary_obj.get("fallback_allowed_by_state_5") or {}),
        "deployment_evidence": deployment_evidence,
        "governor_boundary": governor_boundary,
        "local_policy_decision": local_policy_decision,
        "boundary_attribution": boundary_attribution,
        "fallback_allowed": fallback_allowed,
        "configured_under_deploy_reason_codes": configured_under_deploy_reason_codes,
        "etf_budget_roles_contract_version": etf_budget_roles_contract_version or None,
        "etf_budget_roles_effective_state_5": etf_budget_roles_effective_state_5 or None,
        "etf_budget_roles_target": etf_budget_roles_target,
        "etf_budget_roles_actual": etf_budget_roles_actual,
        "etf_budget_roles_deviation": etf_budget_roles_deviation,
        "formal_view": formal_view,
        "research_view": research_view,
    }
    metrics = {
        "input_count": len(input_etfs),
        "eligible_count": len(eligible_etfs),
        "selected_count": len(selected_etfs),
        "out_of_scope_count": len(out_of_scope_etfs),
        "invalid_selected_count": len(invalid_selected),
        "missing_selected_reason_count": len(missing_selected_reasons),
        "missing_out_of_scope_reason_count": len(missing_out_of_scope_reasons),
        "formal_mainline_compatible": formal_mainline_compatible,
        "formal_alignment_status": formal_alignment_status,
        "formal_alignment_reason_count": len(formal_alignment_reason_codes),
        "order_count": order_count,
        "trade_count": trade_count,
        "requested_budget": requested_budget,
        "applied_budget": applied_budget,
        "cash_weight": cash_weight,
        "defense_weight": defense_weight,
        "target_symbol_count": len(target_map),
        "vol_target_active": bool(vol_target.get("active", False)),
        "vol_target_scaled_symbol_count": len(dict(vol_target.get("scale_by_symbol") or {})),
        **deployment_metrics,
    }
    return {"status": status, "reason": reason, "evidence": evidence, "metrics": metrics}


def evaluate_unified_runtime_completeness(
    *,
    results_dir: str | Path | None,
    run_meta: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    run_meta_obj = dict(run_meta or {})
    data_meta = dict(run_meta_obj.get("data") or {})
    stage_pipeline = dict(run_meta_obj.get("stage_pipeline") or {})
    asset_role = str(data_meta.get("asset_role") or "").strip().lower()
    execution_shell = str(stage_pipeline.get("execution_shell") or "").strip().lower()
    if asset_role != "unified_multi_sleeve_combo" and execution_shell != "unified_combo_phase1":
        return None

    config_payload = _read_json(Path(results_dir).resolve() / "config.json")[0] if results_dir is not None else None
    sleeves = dict(run_meta_obj.get("sleeves") or {})
    combo_governed = dict(run_meta_obj.get("governed_snapshot") or {})
    combo_regime = dict((run_meta_obj.get("regime") or {}).get("latest_state") or {})
    combo_attribution = dict(run_meta_obj.get("attribution") or {})
    combo_runtime = dict(run_meta_obj.get("combo_runtime") or {})
    account_allocator_runtime = dict(run_meta_obj.get("account_allocator_runtime") or {})
    sleeve_budgets = dict(combo_governed.get("sleeve_budgets") or {})
    dependencies = dict(run_meta_obj.get("dependencies") or {})
    component_runs = dict(dependencies.get("component_runs") or {})
    component_experiments = dict((config_payload or {}).get("component_experiments") or {})
    stock_component = dict(component_runs.get("stock_alpha_core") or component_experiments.get("stock_alpha_core") or {})
    etf_component = dict(component_runs.get("etf_beta") or component_experiments.get("etf_beta") or {})
    stock_sleeve = dict(sleeves.get("stock_alpha_core") or {})
    etf_sleeve = dict(sleeves.get("etf_beta") or {})

    root = Path(results_dir).resolve() if results_dir is not None else None
    refs = {}
    if root is not None:
        refs = {
            "portfolio_daily": _clean_ref(root / ARTIFACT_FILENAMES["daily"], root=root),
            "portfolio_trades": _clean_ref(root / ARTIFACT_FILENAMES["trades"], root=root),
            "regime_audit_summary": _clean_ref(root / ARTIFACT_FILENAMES["regime_audit_summary"], root=root),
            "attribution_audit": _clean_ref(root / ARTIFACT_FILENAMES["attribution_audit"], root=root),
            "run_meta": _clean_ref(root / ARTIFACT_FILENAMES["run_meta"], root=root),
        }

    has_components = bool(stock_component.get("exp_id")) and bool(etf_component.get("exp_id"))
    has_sleeve_summaries = bool(stock_sleeve) and bool(etf_sleeve)
    has_combo_governed = bool(combo_governed.get("budget_owner")) and all(
        key in sleeve_budgets for key in ("cn_stock_trend_alpha_core", "cn_etf_beta")
    )
    has_combo_regime = bool(combo_regime.get("effective_state")) and bool(combo_regime.get("base_state"))
    attribution_summary = dict(combo_attribution.get("summary") or {})
    has_combo_attribution = all(
        key in attribution_summary for key in ("state_log_count", "budget_log_count", "sleeve_log_count")
    )
    has_daily_artifact = bool(str(refs.get("portfolio_daily") or "").strip())
    has_account_allocator_runtime = bool(account_allocator_runtime.get("runtime_truth_source")) and bool(
        account_allocator_runtime.get("budget_roles")
    )
    research_combo_only = bool(
        combo_runtime.get("research_combo_only")
        or combo_governed.get("research_combo_only")
    )
    combo_budget_semantics = str(combo_governed.get("budget_semantics") or "").strip()
    combo_budget_owner = str(combo_governed.get("budget_owner") or "").strip()

    metrics = {
        "component_count": int(bool(stock_component.get("exp_id"))) + int(bool(etf_component.get("exp_id"))),
        "has_combo_governed_snapshot": has_combo_governed,
        "has_combo_regime": has_combo_regime,
        "has_combo_attribution": has_combo_attribution,
        "has_daily_artifact": has_daily_artifact,
        "has_account_allocator_runtime": has_account_allocator_runtime,
        "has_account_state_transition_policy": bool(account_allocator_runtime.get("state_transition_policy")),
        "has_account_state_resolution": bool(account_allocator_runtime.get("state_resolution")),
        "has_account_state_transition_runtime": bool(account_allocator_runtime.get("state_transition_runtime")),
        "has_account_transition_action_handoff": bool(account_allocator_runtime.get("transition_action_handoff")),
        "has_account_transition_execution": bool(account_allocator_runtime.get("transition_execution")),
        "account_transition_execution_owner_is_shared_runtime": (
            str(((account_allocator_runtime.get("transition_execution") or {}).get("owner")) or "").strip()
            == "shared_account_execution_runtime"
        ),
        "has_account_transition_execution_reference": bool(
            account_allocator_runtime.get("transition_execution_reference")
        ),
        "riskoff_left_side_accumulation_active": bool(
            (account_allocator_runtime.get("riskoff_left_side_accumulation_budget") or {}).get("active")
        ),
        "riskoff_budget_execution_materialization_active": bool(
            (account_allocator_runtime.get("riskoff_budget_execution_materialization") or {}).get("active")
        ),
        "riskoff_budget_execution_materialization_execution_activated": bool(
            (account_allocator_runtime.get("riskoff_budget_execution_materialization") or {}).get("execution_activated")
        ),
        "riskoff_budget_execution_materialization_execution_rejected": bool(
            (account_allocator_runtime.get("riskoff_budget_execution_materialization") or {}).get("execution_rejected")
        ),
        "research_combo_only": research_combo_only,
        "stock_component_present": bool(stock_component.get("exp_id")),
        "etf_component_present": bool(etf_component.get("exp_id")),
    }
    evidence = {
        "asset_role": asset_role,
        "execution_shell": execution_shell,
        "combo_budget_owner": combo_budget_owner or None,
        "combo_budget_semantics": combo_budget_semantics or None,
        "runtime_truth_source": str(run_meta_obj.get("runtime_truth_source") or "").strip() or None,
        "account_allocator_runtime_contract_version": str(account_allocator_runtime.get("contract_version") or "").strip() or None,
        "account_allocator_budget_owner": str(account_allocator_runtime.get("budget_owner") or "").strip() or None,
        "account_allocator_state_source": str(account_allocator_runtime.get("state_source") or "").strip() or None,
        "account_allocator_effective_state_5": str(account_allocator_runtime.get("effective_state_5") or "").strip() or None,
        "account_allocator_state_transition_policy": dict(account_allocator_runtime.get("state_transition_policy") or {}),
        "account_allocator_state_resolution": dict(account_allocator_runtime.get("state_resolution") or {}),
        "account_allocator_state_transition_runtime": dict(account_allocator_runtime.get("state_transition_runtime") or {}),
        "account_allocator_transition_action_handoff": dict(account_allocator_runtime.get("transition_action_handoff") or {}),
        "account_allocator_transition_execution": dict(account_allocator_runtime.get("transition_execution") or {}),
        "account_allocator_transition_execution_reference": dict(
            account_allocator_runtime.get("transition_execution_reference") or {}
        ),
        "account_allocator_budget_roles": dict(account_allocator_runtime.get("budget_roles") or {}),
        "account_allocator_riskoff_left_side_accumulation_budget": dict(
            account_allocator_runtime.get("riskoff_left_side_accumulation_budget") or {}
        ),
        "account_allocator_riskoff_budget_execution_materialization": dict(
            account_allocator_runtime.get("riskoff_budget_execution_materialization") or {}
        ),
        "account_allocator_reference_combo": dict(account_allocator_runtime.get("reference_combo") or {}),
        "research_combo_only": research_combo_only,
        "stock_component_exp_id": stock_component.get("exp_id"),
        "etf_component_exp_id": etf_component.get("exp_id"),
        "sleeve_budget_keys": list(sleeve_budgets.keys()),
        "refs": refs,
    }
    if (
        has_components
        and has_sleeve_summaries
        and has_combo_governed
        and has_combo_regime
        and has_combo_attribution
        and has_daily_artifact
        and has_account_allocator_runtime
    ):
        status = "PASS"
        reason = "Unified runtime combo exposes account-allocator runtime truth plus combo-level and sleeve-level audit traceability."
    else:
        status = "FAIL"
        reason = "Unified runtime combo is missing account-allocator runtime truth or combo/sleeve completeness evidence."
    return {"status": status, "reason": reason, "evidence": evidence, "metrics": metrics}


def evaluate_attribution_traceability(
    *,
    results_dir: str | Path | None,
    run_meta: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    run_meta_obj = dict(run_meta or {})
    governed = dict(run_meta_obj.get("governed_a_share") or {})
    attribution = dict(run_meta_obj.get("attribution") or {})
    governed_snapshot = dict(run_meta_obj.get("governed_snapshot") or {})
    regime_meta = dict(run_meta_obj.get("regime") or {})
    latest_regime = dict(regime_meta.get("latest_state") or {})
    data_meta = dict(run_meta_obj.get("data") or {})
    stage_pipeline = dict(run_meta_obj.get("stage_pipeline") or {})
    asset_role = str(data_meta.get("asset_role") or "").strip().lower()
    execution_shell = str(stage_pipeline.get("execution_shell") or "").strip().lower()
    should_apply = bool(governed.get("enabled")) or bool(attribution)
    if not should_apply:
        return None

    attribution_obj = attribution
    root = Path(results_dir).resolve() if results_dir is not None else None
    refs: dict[str, Any] = {}
    if root is not None:
        payload, _ = _read_json(root / ARTIFACT_FILENAMES["attribution_audit"])
        if isinstance(payload, Mapping):
            attribution_obj = {
                "contract_version": payload.get("contract_version"),
                "summary": payload.get("summary"),
                "reason_code_summary": payload.get("reason_code_summary"),
                "refs": {"attribution_audit": _clean_ref(root / ARTIFACT_FILENAMES["attribution_audit"], root=root)},
            }
        refs["regime_audit_summary"] = _clean_ref(root / ARTIFACT_FILENAMES["regime_audit_summary"], root=root)

    summary = dict(attribution_obj.get("summary") or {})
    reason_code_summary = dict(attribution_obj.get("reason_code_summary") or {})
    refs = {**refs, **dict(attribution_obj.get("refs") or {})}
    has_logs = all(
        key in summary
        for key in ("state_log_count", "budget_log_count", "sleeve_log_count", "manual_override_log_count")
    )
    has_reason_code_summary = any(bool(dict(reason_code_summary.get(key) or {})) for key in reason_code_summary.keys())
    has_attribution_ref = bool(str(refs.get("attribution_audit") or "").strip())
    has_regime_ref = bool(str(refs.get("regime_audit_summary") or "").strip())
    normalized_governor_base_state = str(
        governed_snapshot.get("base_state") or governed_snapshot.get("regime_source_state") or ""
    ).strip()
    normalized_governor_effective_state = str(
        governed_snapshot.get("effective_state") or governed_snapshot.get("regime_effective_state") or ""
    ).strip()
    normalized_governor_coarse_state = str(governed_snapshot.get("coarse_state") or "").strip()
    normalized_governor_effective_coarse_state = str(governed_snapshot.get("effective_coarse_state") or "").strip()
    normalized_governor_budget_scalar = _safe_float(governed_snapshot.get("risk_budget_multiplier"))
    if normalized_governor_budget_scalar is None and (
        asset_role == "unified_multi_sleeve_combo" or execution_shell == "unified_combo_phase1"
    ):
        normalized_governor_budget_scalar = _safe_float(governed_snapshot.get("total_risk_budget"))
    has_governor_snapshot = all(
        [
            bool(normalized_governor_base_state),
            bool(normalized_governor_effective_state),
            bool(normalized_governor_coarse_state),
            bool(normalized_governor_effective_coarse_state),
            normalized_governor_budget_scalar is not None,
        ]
    )
    has_regime_snapshot = all(
        [
            bool(str(latest_regime.get("base_state") or "").strip()),
            bool(str(latest_regime.get("effective_state") or "").strip()),
            bool(str(latest_regime.get("coarse_state") or "").strip()),
            bool(str(latest_regime.get("effective_coarse_state") or "").strip()),
            isinstance(latest_regime.get("reason_codes"), list),
            isinstance(latest_regime.get("manual_override"), Mapping),
        ]
    )
    has_budget_reason_codes = isinstance(governed_snapshot.get("budget_reason_codes"), list)
    status = "PASS" if has_logs and has_attribution_ref and has_regime_ref and has_governor_snapshot and has_regime_snapshot and has_budget_reason_codes else "FAIL"
    reason = (
        "Formal regime snapshot, governor snapshot, and attribution audit refs are present."
        if status == "PASS"
        else "Missing unified regime/governor/attribution evidence chain."
    )
    return {
        "status": status,
        "reason": reason,
        "evidence": {
            "summary": summary,
            "reason_code_summary": reason_code_summary,
            "governed_snapshot": {
                "base_state": normalized_governor_base_state or None,
                "effective_state": normalized_governor_effective_state or None,
                "coarse_state": normalized_governor_coarse_state or None,
                "effective_coarse_state": normalized_governor_effective_coarse_state or None,
                "risk_budget_multiplier": normalized_governor_budget_scalar,
                "budget_reason_codes": governed_snapshot.get("budget_reason_codes"),
            },
            "latest_regime": {
                "base_state": latest_regime.get("base_state"),
                "effective_state": latest_regime.get("effective_state"),
                "coarse_state": latest_regime.get("coarse_state"),
                "effective_coarse_state": latest_regime.get("effective_coarse_state"),
                "reason_codes": latest_regime.get("reason_codes"),
                "manual_override": latest_regime.get("manual_override"),
            },
            "refs": refs,
        },
        "metrics": {
            "has_logs": has_logs,
            "has_reason_code_summary": has_reason_code_summary,
            "has_attribution_ref": has_attribution_ref,
            "has_regime_ref": has_regime_ref,
            "has_governor_snapshot": has_governor_snapshot,
            "has_regime_snapshot": has_regime_snapshot,
            "has_budget_reason_codes": has_budget_reason_codes,
            "state_log_count": _safe_int(summary.get("state_log_count")) or 0,
            "budget_log_count": _safe_int(summary.get("budget_log_count")) or 0,
            "sleeve_log_count": _safe_int(summary.get("sleeve_log_count")) or 0,
            "manual_override_log_count": _safe_int(summary.get("manual_override_log_count")) or 0,
        },
    }


def evaluate_execution_realism(
    *,
    results_dir: Path | None = None,
    trades_df: pd.DataFrame | None = None,
    bars_df: pd.DataFrame | None = None,
    bt_root: str | Path | None = None,
    runtime_access: Any = None,
) -> dict[str, Any]:
    root = Path(results_dir).resolve() if results_dir is not None else None
    trade_frame = trades_df if trades_df is not None else (_read_csv(root / "portfolio_trades.csv")[0] if root is not None else pd.DataFrame())
    trades = _normalize_trade_df(trade_frame)
    if trades.empty:
        return {
            "status": "UNKNOWN",
            "reason": "无交易数据或交易记录缺少核对所需字段。",
            "evidence": {"trades_path": "portfolio_trades.csv" if root is not None else None},
            "metrics": {"total_trades": 0},
        }

    load_error = None
    runtime_query_count = None
    bar_frame = bars_df
    if bar_frame is None:
        try:
            access = runtime_access or load_runtime_data_access(bt_root)
            symbols = sorted(set(trades["symbol"].astype(str).tolist()))
            start = trades["date"].min()
            end = trades["date"].max()
            bar_frame = access.provider.load_ohlcv_daily(
                symbols,
                start,
                end,
                source="research_audit_execution_realism",
            )
            runtime_query_count = len(getattr(access.provider, "query_audit", []) or [])
        except Exception as exc:
            load_error = f"{type(exc).__name__}: {exc}"
            bar_frame = pd.DataFrame()
    bars = _normalize_bar_df(bar_frame)
    if bars.empty:
        return {
            "status": "UNKNOWN",
            "reason": "无法回查成交对应 bar，execution realism 无法核对。",
            "evidence": {"trades_path": "portfolio_trades.csv" if root is not None else None, "bar_load_error": load_error},
            "metrics": {"total_trades": int(len(trades)), "runtime_query_count": runtime_query_count},
        }

    merged = trades.merge(bars, on=["symbol", "date"], how="left", indicator=True, suffixes=("", "_bar"))
    initial_missing_mask = merged["_merge"] != "both"
    if initial_missing_mask.any() and bar_frame is not None:
        try:
            access = runtime_access or load_runtime_data_access(bt_root)
            missing_symbols = sorted(set(merged.loc[initial_missing_mask, "symbol"].astype(str).tolist()))
            extra_bars, extra_query_count = _load_etf_bar_supplement(
                access=access,
                symbols=missing_symbols,
                start=trades["date"].min(),
                end=trades["date"].max(),
            )
            if extra_query_count is not None:
                runtime_query_count = int((runtime_query_count or 0) + extra_query_count)
            if not extra_bars.empty:
                combined_bars = pd.concat([bars, _normalize_bar_df(extra_bars)], ignore_index=True)
                combined_bars = combined_bars.drop_duplicates(subset=["symbol", "date"], keep="first")
                bars = combined_bars.sort_values(["symbol", "date"]).reset_index(drop=True)
                merged = trades.merge(bars, on=["symbol", "date"], how="left", indicator=True, suffixes=("", "_bar"))
        except Exception as exc:
            if load_error:
                load_error = f"{load_error}; etf_supplement={type(exc).__name__}: {exc}"
            else:
                load_error = f"etf_supplement={type(exc).__name__}: {exc}"
    merged["audit_price"] = _series_numeric(merged, "fill_price").fillna(_series_numeric(merged, "price"))
    missing_bar_mask = merged["_merge"] != "both"
    suspended_mask = (~missing_bar_mask) & _series_bool(merged, "is_suspended")
    volume = _series_numeric(merged, "volume")
    zero_volume_mask = (~missing_bar_mask) & volume.notna() & (volume <= 0)
    turnover = _series_numeric(merged, "amount")
    if turnover.isna().all():
        turnover = _series_numeric(merged, "turnover")
    zero_turnover_mask = (~missing_bar_mask) & turnover.notna() & (turnover <= 0)
    merged["limit_up"] = _normalize_limit_series(merged, "limit_up")
    merged["limit_down"] = _normalize_limit_series(merged, "limit_down")
    limit_up = _series_numeric(merged, "limit_up")
    limit_down = _series_numeric(merged, "limit_down")
    price = _series_numeric(merged, "audit_price")
    side = _series_text(merged, "side")
    tol_up = limit_up.abs().fillna(0.0) * 1e-4 + 1e-6
    tol_down = limit_down.abs().fillna(0.0) * 1e-4 + 1e-6
    limit_up_buy_mask = (~missing_bar_mask) & (side == "BUY") & price.notna() & limit_up.notna() & (price >= (limit_up - tol_up))
    limit_down_sell_mask = (~missing_bar_mask) & (side == "SELL") & price.notna() & limit_down.notna() & (price <= (limit_down + tol_down))

    total_trades = int(len(merged))
    hard_fail_count = int(missing_bar_mask.sum() + suspended_mask.sum() + zero_volume_mask.sum() + zero_turnover_mask.sum())
    limit_locked_count = int(limit_up_buy_mask.sum() + limit_down_sell_mask.sum())
    limit_locked_ratio = (limit_locked_count / total_trades) if total_trades > 0 else 0.0

    if hard_fail_count > 0:
        status = "FAIL"
        reason = "发现停牌成交、缺 bar 成交或零成交量/零成交额成交。"
    elif limit_locked_ratio > _LIMIT_LOCK_FAIL_RATIO:
        status = "FAIL"
        reason = "涨停买入或跌停卖出占比超过 1%，成交现实性不可接受。"
    elif limit_locked_count > 0:
        status = "WARN"
        reason = "存在少量涨停买入或跌停卖出，成交现实性存在风险。"
    else:
        status = "PASS"
        reason = "未发现明显违反市场约束的成交。"

    metrics = {
        "total_trades": total_trades,
        "missing_bar_count": int(missing_bar_mask.sum()),
        "suspended_trade_count": int(suspended_mask.sum()),
        "zero_volume_trade_count": int(zero_volume_mask.sum()),
        "zero_turnover_trade_count": int(zero_turnover_mask.sum()),
        "limit_up_buy_count": int(limit_up_buy_mask.sum()),
        "limit_down_sell_count": int(limit_down_sell_mask.sum()),
        "limit_locked_trade_ratio": round(limit_locked_ratio, 6),
        "runtime_query_count": runtime_query_count,
    }
    evidence = {
        "trades_path": "portfolio_trades.csv" if root is not None else None,
        "samples": {
            "missing_bar": _sample_issue_rows(merged, missing_bar_mask),
            "suspended_trade": _sample_issue_rows(merged, suspended_mask),
            "zero_volume_trade": _sample_issue_rows(merged, zero_volume_mask),
            "zero_turnover_trade": _sample_issue_rows(merged, zero_turnover_mask),
            "limit_up_buy": _sample_issue_rows(merged, limit_up_buy_mask),
            "limit_down_sell": _sample_issue_rows(merged, limit_down_sell_mask),
        },
        "bar_load_error": load_error,
    }
    return {"status": status, "reason": reason, "evidence": evidence, "metrics": metrics}


def evaluate_reproducibility(
    *,
    results_dir: Path,
    run_meta: Mapping[str, Any] | None,
    manifest: Mapping[str, Any] | None,
    artifact_presence: Mapping[str, bool] | None = None,
    read_errors: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    errors = dict(read_errors or {})
    if errors.get("run_meta") or errors.get("manifest") or errors.get("audit"):
        return {
            "status": "UNKNOWN",
            "reason": "关键产物存在读取失败，无法完成可复现性判断。",
            "evidence": {"read_errors": errors},
            "metrics": {},
        }

    def _artifact_exists(name: str, filename: str) -> bool:
        if artifact_presence is not None and name in artifact_presence:
            return bool(artifact_presence.get(name))
        return (results_dir / filename).exists()

    missing_core = [
        filename
        for name, filename in (("run_meta", "run_meta.json"), ("manifest", "manifest.json"), ("audit", "audit.json"))
        if not _artifact_exists(name, filename)
    ]
    run_meta_obj = dict(run_meta or {})
    manifest_obj = dict(manifest or {})
    config_snapshots = dict(manifest_obj.get("config_snapshots") or {})
    snapshots_present = [key for key in _REQUIRED_SNAPSHOTS if str(config_snapshots.get(key) or "").strip()]
    report_consistency = dict(run_meta_obj.get("report_consistency") or {})
    resolved_hash = str(report_consistency.get("resolved_config_hash") or "").strip()

    if missing_core:
        status = "FAIL"
        reason = f"缺少关键复现实验产物: {', '.join(missing_core)}"
    elif len(snapshots_present) == len(_REQUIRED_SNAPSHOTS) or bool(resolved_hash):
        status = "PASS"
        reason = "核心产物齐全，且配置快照或配置 hash 可追溯。"
    elif snapshots_present or report_consistency:
        status = "WARN"
        reason = "核心产物齐全，但配置快照不完整，仅能部分追溯。"
    else:
        status = "WARN"
        reason = "核心产物齐全，但缺少足够的配置追溯信息。"

    evidence = {
        "config_snapshots": {key: config_snapshots.get(key) for key in _REQUIRED_SNAPSHOTS},
        "resolved_config_hash_present": bool(resolved_hash),
    }
    metrics = {
        "missing_core_count": len(missing_core),
        "config_snapshot_count": len(snapshots_present),
    }
    return {"status": status, "reason": reason, "evidence": evidence, "metrics": metrics}


def _compute_profit_concentration(
    *,
    perf: Mapping[str, Any] | None,
    symbol_performance_df: pd.DataFrame,
) -> float | None:
    perf_obj = dict(perf or {})
    explicit = _coerce_concentration(perf_obj.get("top10_profit_concentration"))
    if explicit is not None:
        return explicit
    if symbol_performance_df.empty or "net_pnl" not in symbol_performance_df.columns:
        return None
    net_pnl = pd.to_numeric(symbol_performance_df["net_pnl"], errors="coerce").fillna(0.0)
    positive = net_pnl[net_pnl > 0]
    total_positive = float(positive.sum())
    if total_positive <= 0:
        return None
    top10_positive = float(positive.sort_values(ascending=False).head(10).sum())
    return top10_positive / total_positive


def evaluate_result_sanity(
    *,
    results_dir: Path | None = None,
    perf: Mapping[str, Any] | None,
    run_meta: Mapping[str, Any] | None,
    symbol_performance_df: pd.DataFrame | None = None,
    read_errors: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    errors = dict(read_errors or {})
    if errors.get("perf"):
        return {
            "status": "UNKNOWN",
            "reason": "关键收益指标读取失败，无法做结果异常检测。",
            "evidence": {"read_errors": errors},
            "metrics": {},
        }

    root = Path(results_dir).resolve() if results_dir is not None else None
    if symbol_performance_df is None:
        symbol_performance_df = _read_csv(root / "symbol_performance.csv")[0] if root is not None else pd.DataFrame()

    perf_obj = dict(perf or {})
    run_meta_obj = dict(run_meta or {})
    counters = dict(run_meta_obj.get("counters") or {})
    stage_pipeline = dict(run_meta_obj.get("stage_pipeline") or {})
    stage_summary = dict(run_meta_obj.get("stage_summary") or {})

    total_return = _safe_float(perf_obj.get("total_return"))
    sharpe = _safe_float(perf_obj.get("sharpe"))
    cagr = _safe_float(perf_obj.get("cagr"))
    trade_count = _safe_int(perf_obj.get("trades"))
    if trade_count is None:
        trade_count = _safe_int(counters.get("buy_orders_count")) or _safe_int(counters.get("orders")) or 0
    closed_trades = _safe_int(counters.get("closed_trades"))
    if closed_trades is None:
        closed_trades = trade_count
    trading_days = _safe_int(stage_pipeline.get("trading_days"))
    if trading_days is None:
        trading_days = _safe_int(stage_summary.get("trading_days"))

    contradiction = bool((trade_count or 0) == 0 and total_return is not None and abs(total_return) > 1e-9)
    if contradiction:
        return {
            "status": "FAIL",
            "reason": "交易数为 0，但净值或收益指标发生了明显变化，结果口径自相矛盾。",
            "evidence": {"perf": {"total_return": total_return, "trades": trade_count}},
            "metrics": {"trade_count": trade_count, "closed_trades": closed_trades, "trading_days": trading_days},
        }

    if sharpe is None and cagr is None:
        return {
            "status": "UNKNOWN",
            "reason": "缺少 Sharpe/CAGR 等关键收益指标，无法做结果异常检测。",
            "evidence": {"perf_path": "perf.json" if root is not None else None},
            "metrics": {"trade_count": trade_count, "closed_trades": closed_trades, "trading_days": trading_days},
        }

    sample_sufficient = bool((trading_days or 0) >= 252 and (closed_trades or 0) >= 20)
    if not sample_sufficient:
        return {
            "status": "UNKNOWN",
            "reason": "样本天数或已平仓交易数不足，无法可靠执行异常阈值检测。",
            "evidence": {"sample_rule": {"min_trading_days": 252, "min_closed_trades": 20}},
            "metrics": {"trade_count": trade_count, "closed_trades": closed_trades, "trading_days": trading_days},
        }

    concentration = _compute_profit_concentration(perf=perf_obj, symbol_performance_df=symbol_performance_df)
    if (sharpe is not None and sharpe > 5.0) or (cagr is not None and cagr > 1.0):
        status = "FAIL"
        reason = "Sharpe 或 CAGR 极端异常，结果可信度不足。"
    elif (
        (sharpe is not None and sharpe > 3.0)
        or (cagr is not None and cagr > 0.5)
        or (concentration is not None and concentration > _CONCENTRATION_WARN_THRESHOLD)
    ):
        status = "WARN"
        reason = "收益或利润集中度偏极端，结果存在异常风险。"
    else:
        status = "PASS"
        reason = "未发现明显的收益异常或口径矛盾。"

    evidence = {
        "perf_path": "perf.json" if root is not None else None,
        "symbol_performance_path": "symbol_performance.csv" if root is not None else None,
    }
    metrics = {
        "trade_count": trade_count,
        "closed_trades": closed_trades,
        "trading_days": trading_days,
        "sharpe": sharpe,
        "cagr": cagr,
        "profit_concentration": round(float(concentration), 6) if concentration is not None else None,
    }
    return {"status": status, "reason": reason, "evidence": evidence, "metrics": metrics}


def evaluate_accounting_integrity(
    *,
    result: Mapping[str, Any] | None = None,
    run_meta: Mapping[str, Any] | None = None,
    results_dir: Path | None = None,
) -> dict[str, Any]:
    run_meta_obj = dict(run_meta or {})
    data_meta = dict(run_meta_obj.get("data") or {})
    stage_pipeline = dict(run_meta_obj.get("stage_pipeline") or {})
    asset_role = str(data_meta.get("asset_role") or "").strip().lower()
    execution_shell = str(stage_pipeline.get("execution_shell") or "").strip().lower()
    if asset_role == "unified_multi_sleeve_combo" or execution_shell == "unified_combo_phase1":
        component_gates: dict[str, dict[str, Any]] = {}
        for sleeve_name, component in _load_combo_component_records(run_meta=run_meta_obj, results_dir=results_dir).items():
            component_run_meta = component.get("run_meta")
            component_results_dir = component.get("results_dir")
            if not isinstance(component_run_meta, Mapping):
                component_gates[sleeve_name] = {
                    "status": "UNKNOWN",
                    "reason": str(component.get("read_error") or "component run_meta unavailable"),
                }
                continue
            component_gates[sleeve_name] = evaluate_accounting_integrity(
                run_meta=component_run_meta,
                results_dir=component_results_dir,
            )
        component_statuses = {
            name: _normalize_status((gate or {}).get("status"))
            for name, gate in component_gates.items()
            if isinstance(gate, Mapping)
        }
        counts = Counter(component_statuses.values())
        if component_statuses and all(status == "PASS" for status in component_statuses.values()):
            status = "PASS"
            reason = "Unified combo aggregates only sleeves with PASS accounting integrity."
        elif any(status == "FAIL" for status in component_statuses.values()):
            status = "FAIL"
            reason = "Unified combo aggregates at least one sleeve with FAIL accounting integrity."
        elif any(status == "WARN" for status in component_statuses.values()):
            status = "WARN"
            reason = "Unified combo aggregates at least one sleeve with WARN accounting integrity."
        else:
            status = "UNKNOWN"
            reason = "Unified combo lacks sufficient sleeve accounting evidence."
        return {
            "status": status,
            "reason": reason,
            "evidence": {"component_statuses": component_statuses},
            "metrics": {
                "component_count": int(len(component_statuses)),
                "component_pass_count": int(counts.get("PASS", 0)),
                "component_warn_count": int(counts.get("WARN", 0)),
                "component_fail_count": int(counts.get("FAIL", 0)),
            },
        }

    payload, source = _extract_accounting_integrity_audit(
        result=result,
        run_meta=run_meta,
        results_dir=results_dir,
    )
    if not isinstance(payload, Mapping):
        return {
            "status": "UNKNOWN",
            "reason": "Missing canonical accounting integrity audit evidence.",
            "evidence": {"source": source},
            "metrics": {
                "trading_days": 0,
                "days_with_evidence": 0,
                "missing_evidence_days": 0,
                "cash_check_fail": 0,
                "position_check_fail": 0,
                "nav_check_fail": 0,
                "negative_cash_days": 0,
                "max_positions_breach_days": 0,
            },
        }

    summary = dict(payload.get("summary") or {})
    metrics = {
        "trading_days": _safe_int(summary.get("trading_days")) or 0,
        "days_with_evidence": _safe_int(summary.get("days_with_evidence")) or 0,
        "missing_evidence_days": _safe_int(summary.get("missing_evidence_days")) or 0,
        "cash_check_fail": _safe_int(summary.get("cash_check_fail")) or 0,
        "position_check_fail": _safe_int(summary.get("position_check_fail")) or 0,
        "nav_check_fail": _safe_int(summary.get("nav_check_fail")) or 0,
        "invalid_nav_days": _safe_int(summary.get("invalid_nav_days")) or 0,
        "negative_cash_days": _safe_int(summary.get("negative_cash_days")) or 0,
        "max_positions_breach_days": _safe_int(summary.get("max_positions_breach_days")) or 0,
    }
    explicit_status = _normalize_status(payload.get("status"))
    hard_fail_count = (
        int(metrics["cash_check_fail"])
        + int(metrics["position_check_fail"])
        + int(metrics["nav_check_fail"])
        + int(metrics["invalid_nav_days"])
        + int(metrics["negative_cash_days"])
        + int(metrics["max_positions_breach_days"])
    )
    if hard_fail_count > 0 or explicit_status == "FAIL":
        status = "FAIL"
        reason = str(payload.get("reason") or "Accounting integrity audit detected invariant violations.")
    elif (
        explicit_status == "PASS"
        and int(metrics["trading_days"]) > 0
        and int(metrics["missing_evidence_days"]) == 0
        and int(metrics["days_with_evidence"]) == int(metrics["trading_days"])
    ):
        status = "PASS"
        reason = str(payload.get("reason") or "Accounting integrity audit passed.")
    else:
        status = "UNKNOWN"
        reason = str(payload.get("reason") or "Accounting integrity evidence is incomplete.")

    samples = dict(payload.get("samples") or {})
    evidence = {
        "source": source,
        "contract_version": payload.get("contract_version"),
        "audit_status": explicit_status,
        "sample_keys": [key for key, value in samples.items() if value],
        "tolerances": dict(payload.get("tolerances") or {}),
    }
    return {"status": status, "reason": reason, "evidence": evidence, "metrics": metrics}


def build_research_audit(
    *,
    results_dir: str | Path,
    result: Mapping[str, Any] | None = None,
    run_meta: Mapping[str, Any] | None = None,
    manifest: Mapping[str, Any] | None = None,
    perf: Mapping[str, Any] | None = None,
    stage_summary: Mapping[str, Any] | None = None,
    stage_pipeline: Mapping[str, Any] | None = None,
    validation_audit_ref: Mapping[str, Any] | None = None,
    bt_root: str | Path | None = None,
    runtime_access: Any = None,
    artifact_presence: Mapping[str, bool] | None = None,
) -> dict[str, Any]:
    root = Path(results_dir).resolve()
    result_obj = dict(result or {})
    read_errors: dict[str, str] = {}

    if run_meta is None:
        run_meta, err = _read_json(root / "run_meta.json")
        if err:
            read_errors["run_meta"] = err
    if manifest is None:
        manifest, err = _read_json(root / "manifest.json")
        if err:
            read_errors["manifest"] = err
    if perf is None:
        perf, err = _read_json(root / "perf.json")
        if err:
            read_errors["perf"] = err
    if stage_summary is None:
        stage_summary, err = _read_json(root / "stage_summary.json")
        if err:
            read_errors["stage_summary"] = err
    if stage_pipeline is None and isinstance(run_meta, Mapping):
        stage_pipeline = (run_meta or {}).get("stage_pipeline")
    if stage_pipeline is None and isinstance(result_obj.get("stage_pipeline"), Mapping):
        stage_pipeline = result_obj.get("stage_pipeline")
    if not (root / "audit.json").exists():
        read_errors["audit"] = read_errors.get("audit") or "audit.json: missing"

    validation_ref = summarize_validation_audit_ref(validation_audit_ref)
    symbol_perf_df, symbol_perf_err = _read_csv(root / "symbol_performance.csv")
    if symbol_perf_err:
        read_errors["symbol_performance"] = symbol_perf_err

    gates = {
        "accounting_integrity": evaluate_accounting_integrity(
            result=result_obj,
            run_meta=run_meta,
            results_dir=root,
        ),
        "timing_alignment": evaluate_timing_alignment(
            stage_summary=stage_summary,
            stage_pipeline=stage_pipeline,
            result=result_obj,
            run_meta=run_meta,
            results_dir=root,
        ),
        "universe_lineage": evaluate_universe_lineage(run_meta=run_meta, results_dir=root),
        "price_adjustment_integrity": evaluate_price_adjustment_integrity(run_meta=run_meta, results_dir=root),
        "execution_realism": evaluate_execution_realism(
            results_dir=root,
            bt_root=bt_root,
            runtime_access=runtime_access,
        ),
        "reproducibility": evaluate_reproducibility(
            results_dir=root,
            run_meta=run_meta,
            manifest=manifest,
            artifact_presence=artifact_presence,
            read_errors=read_errors,
        ),
        "result_sanity": evaluate_result_sanity(
            results_dir=root,
            perf=perf,
            run_meta=run_meta,
            symbol_performance_df=symbol_perf_df,
            read_errors=read_errors,
        ),
    }
    unified_runtime_gate = evaluate_unified_runtime_completeness(
        results_dir=root,
        run_meta=run_meta,
    )
    if isinstance(unified_runtime_gate, dict):
        gates["unified_runtime_completeness"] = unified_runtime_gate
    etf_beta_gate = evaluate_etf_beta_sleeve(run_meta=run_meta, results_dir=root)
    if isinstance(etf_beta_gate, dict):
        gates["etf_beta_sleeve"] = etf_beta_gate
    attribution_gate = evaluate_attribution_traceability(results_dir=root, run_meta=run_meta)
    if isinstance(attribution_gate, dict):
        gates["attribution_traceability"] = attribution_gate

    return {
        "contract_version": RESEARCH_AUDIT_CONTRACT_VERSION,
        "overall_status": aggregate_overall_status(gates),
        "gates": gates,
        "evidence_refs": {
            "audit": _clean_ref(root / "audit.json", root=root),
            "run_meta": _clean_ref(root / "run_meta.json", root=root),
            "manifest": _clean_ref(root / "manifest.json", root=root),
            "stage_summary": _clean_ref(root / "stage_summary.json", root=root),
            "execution_lineage_ledger": _clean_ref(root / ARTIFACT_FILENAMES["execution_lineage_ledger"], root=root),
            "regime_audit_summary": _clean_ref(root / ARTIFACT_FILENAMES["regime_audit_summary"], root=root),
            "regime_transition_debug": _clean_ref(root / ARTIFACT_FILENAMES["regime_transition_debug"], root=root),
            "attribution_audit": _clean_ref(root / ARTIFACT_FILENAMES["attribution_audit"], root=root),
            "trades": _clean_ref(root / "portfolio_trades.csv", root=root),
            "symbol_performance": _clean_ref(root / "symbol_performance.csv", root=root),
            "validate_data": validation_ref,
        },
    }
