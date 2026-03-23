from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from backend.core.data.price_limits import round_price_to_tick
from backend.core.tools.runtime_data_access import load_runtime_data_access
from backend.core.universe.lineage import get_universe_lineage, normalize_universe_mode
from backend.api.backtest_v2.protocol import ARTIFACT_FILENAMES

RESEARCH_AUDIT_CONTRACT_VERSION = "research_audit@1"
RESEARCH_AUDIT_STATUSES = ("PASS", "WARN", "FAIL", "UNKNOWN")
UNIVERSE_LINEAGE_MODES = ("PIT_DYNAMIC", "DIRECT_SYMBOLS", "START_SNAPSHOT", "CURRENT_SNAPSHOT", "UNKNOWN")
_PRICE_ONLY_STRATEGIES = ("BREAKOUT_TREND", "BREAKOUT", "SMA_CROSS", "EMA_CROSS", "RSI_REVERSAL")
_NEXT_DAY_MATCHING_MODES = ("NEXT_OPEN", "NEXT_DAY", "NEXT_TRADING_DAY", "NEXT_BAR_OPEN")

_LIMIT_LOCK_FAIL_RATIO = 0.01
_CONCENTRATION_WARN_THRESHOLD = 0.8
_REQUIRED_SNAPSHOTS = ("input_config", "resolved_config", "compiled_plan")


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

    runtime_config = (
        dict(compiled_plan_obj.get("runtime_config") or {})
        if isinstance(compiled_plan_obj, Mapping)
        else {}
    )
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
    for field in ("schema_version", "execution_shell", "daily_loop_mode", "route_id", "stage_order", "enabled_stages"):
        left = summary_obj.get(field)
        right = pipeline_obj.get(field)
        if left in (None, "", [], {}) or right in (None, "", [], {}):
            continue
        if left != right:
            mismatch_fields.append(field)

    if bool(timing_meta.get("same_day_close_fill")) or bool(timing_meta.get("future_input_detected")):
        status = "FAIL"
        reason = "Detected explicit same-day fill or future-input risk."
    elif _normalize_status(timing_meta.get("status")) == "FAIL":
        status = "FAIL"
        reason = str(timing_meta.get("reason") or "Timing audit reported FAIL explicitly.")
    elif mismatch_fields:
        status = "WARN"
        reason = f"Stage execution metadata mismatch: {', ' .join(mismatch_fields)}"
    elif bool(timing_meta.get("contract_proved")) and bool(timing_meta.get("pit_safe")):
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
        "contract_proved": bool(timing_meta.get("contract_proved")),
        "pit_safe": bool(timing_meta.get("pit_safe")),
        "uses_fundamental_data": bool(timing_meta.get("uses_fundamental_data")),
        "uses_membership_signal": bool(timing_meta.get("uses_membership_signal")),
        "lineage_rows": _safe_int((timing_meta.get("lineage_metrics") or {}).get("rows")),
        "lineage_filled_count": _safe_int((timing_meta.get("lineage_metrics") or {}).get("filled_count")),
        "lineage_same_day_fill_count": _safe_int((timing_meta.get("lineage_metrics") or {}).get("same_day_fill_count")),
        "lineage_schedule_drift_count": _safe_int((timing_meta.get("lineage_metrics") or {}).get("schedule_drift_count")),
    }
    return {"status": status, "reason": reason, "evidence": evidence, "metrics": metrics}


def evaluate_universe_lineage(*, run_meta: Mapping[str, Any] | None) -> dict[str, Any]:
    run_meta_obj = dict(run_meta or {})
    universe_meta = dict(run_meta_obj.get("universe") or {})
    data_meta = dict(run_meta_obj.get("data") or {})
    asset_scope = str(
        universe_meta.get("asset_scope")
        or data_meta.get("asset_scope")
        or ""
    ).strip().lower()
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
        "universe_lineage": evaluate_universe_lineage(run_meta=run_meta),
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
            "trades": _clean_ref(root / "portfolio_trades.csv", root=root),
            "symbol_performance": _clean_ref(root / "symbol_performance.csv", root=root),
            "validate_data": validation_ref,
        },
    }
