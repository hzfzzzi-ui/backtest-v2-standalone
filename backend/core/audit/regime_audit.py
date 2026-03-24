from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from backend.core.config.cn_a_governed_mainline import canonical_state_5, coarse_state_from_state_5

REGIME_AUDIT_CONTRACT_VERSION = "regime_audit@1"

_SUMMARY_FILENAME = "regime_audit_summary.json"
_TRANSITION_DEBUG_FILENAME = "regime_transition_debug.csv"
_REPORT_FILENAME = "regime_audit_report.md"


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    if pd.isna(value):
        return None
    try:
        out = float(value)
    except Exception:
        return None
    if pd.isna(out):
        return None
    return float(out)


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    if pd.isna(value):
        return None
    try:
        return int(value)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return None


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _coerce_reason_codes(value: Any, *, fallback: str | None = None) -> list[str]:
    if isinstance(value, list):
        return [text for text in (_normalize_text(item) for item in value) if text]
    text = _normalize_text(value)
    if text:
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = None
        if isinstance(parsed, list):
            return [item for item in (_normalize_text(entry) for entry in parsed) if item]
        if text:
            return [text]
    fallback_text = _normalize_text(fallback)
    return [fallback_text] if fallback_text else []


def _coerce_subscores(value: Any, *, technical_fallback: Any = None) -> dict[str, Any]:
    parsed: dict[str, Any] | None = None
    if isinstance(value, dict):
        parsed = dict(value)
    else:
        text = _normalize_text(value)
        if text:
            try:
                raw = json.loads(text)
            except Exception:
                raw = None
            if isinstance(raw, dict):
                parsed = raw
    if parsed is None:
        parsed = {}
    technical = parsed.get("technical", technical_fallback)
    return {
        "technical": _safe_float(technical),
        "sentiment": _safe_float(parsed.get("sentiment")),
        "macro_global": _safe_float(parsed.get("macro_global")),
    }


def _coerce_manual_override(value: Any) -> dict[str, Any]:
    parsed: dict[str, Any] | None = None
    if isinstance(value, dict):
        parsed = dict(value)
    else:
        text = _normalize_text(value)
        if text:
            try:
                raw = json.loads(text)
            except Exception:
                raw = None
            if isinstance(raw, dict):
                parsed = raw
    if parsed is None:
        parsed = {}
    return {
        "active": bool(parsed.get("active", False)),
        "reason": _normalize_text(parsed.get("reason")) or None,
        "scope": _normalize_text(parsed.get("scope")) or None,
        "actor": _normalize_text(parsed.get("actor")) or None,
    }


def _fmt_float_or_blank(value: Any, digits: int = 4) -> str:
    parsed = _safe_float(value)
    if parsed is None:
        return ""
    return f"{parsed:.{digits}f}"


def _coerce_feature_availability(value: Any) -> dict[str, bool]:
    if isinstance(value, dict):
        return {str(k): bool(v) for k, v in value.items() if str(k or "").strip()}
    text = _normalize_text(value)
    if not text:
        return {}
    try:
        obj = json.loads(text)
    except Exception:
        return {}
    if not isinstance(obj, dict):
        return {}
    return {str(k): bool(v) for k, v in obj.items() if str(k or "").strip()}


def _normalize_daily_frame(daily_df: pd.DataFrame) -> pd.DataFrame:
    df = daily_df.copy()
    if "date" not in df.columns:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    if df.empty:
        return df
    for column in ("market_state", "trade_mode", "regime_engine", "regime_transition_reason", "feature_availability_json"):
        if column not in df.columns:
            df[column] = ""
        df[column] = df[column].map(_normalize_text)
    if "market_state_5" not in df.columns:
        df["market_state_5"] = df["market_state"]
    if "base_state_5" not in df.columns:
        df["base_state_5"] = df.apply(
            lambda row: canonical_state_5(row.get("market_state_5") or row.get("market_state"), trade_mode=row.get("trade_mode")),
            axis=1,
        )
    else:
        df["base_state_5"] = df.apply(
            lambda row: canonical_state_5(row.get("base_state_5"), trade_mode=row.get("trade_mode")),
            axis=1,
        )
    if "effective_state_5" not in df.columns:
        df["effective_state_5"] = df["base_state_5"]
    else:
        df["effective_state_5"] = df.apply(
            lambda row: canonical_state_5(row.get("effective_state_5") or row.get("base_state_5"), trade_mode=row.get("trade_mode")),
            axis=1,
        )
    df["coarse_state"] = df["base_state_5"].map(coarse_state_from_state_5)
    if "effective_coarse_state" not in df.columns:
        df["effective_coarse_state"] = df["effective_state_5"].map(coarse_state_from_state_5)
    else:
        df["effective_coarse_state"] = df["effective_state_5"].map(coarse_state_from_state_5)
    for column in ("regime_confidence",):
        if column not in df.columns:
            df[column] = pd.NA
        df[column] = pd.to_numeric(df[column], errors="coerce")
    if "market_state_score" not in df.columns:
        df["market_state_score"] = pd.NA
    df["market_state_score"] = pd.to_numeric(df["market_state_score"], errors="coerce")
    for column in ("regime_duration_bars",):
        if column not in df.columns:
            df[column] = pd.NA
        df[column] = pd.to_numeric(df[column], errors="coerce").astype("Int64")
    if "reason_codes_json" not in df.columns:
        df["reason_codes_json"] = ""
    df["reason_codes"] = [
        _coerce_reason_codes(raw, fallback=reason)
        for raw, reason in zip(df["reason_codes_json"].tolist(), df["regime_transition_reason"].tolist())
    ]
    if "subscores_json" not in df.columns:
        df["subscores_json"] = ""
    df["subscores"] = [
        _coerce_subscores(raw, technical_fallback=score)
        for raw, score in zip(df["subscores_json"].tolist(), df["market_state_score"].tolist())
    ]
    if "manual_override_json" not in df.columns:
        df["manual_override_json"] = ""
    df["manual_override"] = [_coerce_manual_override(raw) for raw in df["manual_override_json"].tolist()]
    return df


def build_regime_audit_summary(
    *,
    daily_df: pd.DataFrame,
    run_meta: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    df = _normalize_daily_frame(daily_df)
    if df.empty:
        return None

    regime_meta = dict((run_meta or {}).get("regime") or {})
    persistence_meta = dict(regime_meta.get("persistence") or {})
    feature_contract = dict(regime_meta.get("feature_availability_contract") or {})
    confidence_floor = _safe_float(persistence_meta.get("confidence_floor"))
    if confidence_floor is None:
        confidence_floor = 0.0

    engine = _normalize_text(df["regime_engine"].dropna().iloc[-1] if "regime_engine" in df.columns and not df["regime_engine"].dropna().empty else regime_meta.get("engine")) or "unknown"
    required_blocks = [
        _normalize_text(item)
        for item in list(feature_contract.get("required_blocks") or ())
        if _normalize_text(item)
    ]

    state_change = (
        df["market_state"].ne(df["market_state"].shift(1))
        | df["trade_mode"].ne(df["trade_mode"].shift(1))
    ) & df.index.to_series().gt(0)
    reason_present = df["regime_transition_reason"].astype(str).str.len() > 0
    transition_mask = state_change | reason_present

    transition_df = df.loc[transition_mask, [
        "date",
        "market_state",
        "base_state_5",
        "effective_state_5",
        "coarse_state",
        "effective_coarse_state",
        "trade_mode",
        "regime_confidence",
        "regime_duration_bars",
        "regime_transition_reason",
        "feature_availability_json",
        "reason_codes",
        "subscores",
        "manual_override",
    ]].copy()
    transition_df["state_changed"] = state_change.loc[transition_mask].astype(bool).to_list()
    transition_df["trade_mode_changed"] = (
        df["trade_mode"].ne(df["trade_mode"].shift(1)).loc[transition_mask] & df.index.to_series().gt(0).loc[transition_mask]
    ).astype(bool).to_list()
    transition_df["low_confidence"] = (
        pd.to_numeric(transition_df["regime_confidence"], errors="coerce") < float(confidence_floor)
    ).fillna(False)
    transition_df["date"] = pd.to_datetime(transition_df["date"], errors="coerce").dt.strftime("%Y-%m-%d")

    low_conf_mask = pd.to_numeric(df["regime_confidence"], errors="coerce") < float(confidence_floor)
    confidence_valid = pd.to_numeric(df["regime_confidence"], errors="coerce").notna()

    feature_days = 0
    missing_block_counts: dict[str, int] = {name: 0 for name in required_blocks}
    fallback_days = 0
    for payload in df["feature_availability_json"].tolist():
        availability = _coerce_feature_availability(payload)
        if not availability:
            continue
        feature_days += 1
        if required_blocks:
            missing = False
            for block in required_blocks:
                if not availability.get(block, False):
                    missing_block_counts[block] = int(missing_block_counts.get(block, 0)) + 1
                    missing = True
            if missing:
                fallback_days += 1

    latest_row = df.iloc[-1]
    latest_feature_availability = _coerce_feature_availability(latest_row.get("feature_availability_json"))
    latest_transition = transition_df.tail(1).to_dict(orient="records")
    latest_transition_row = latest_transition[0] if latest_transition else None
    override_active = df["manual_override"].map(lambda payload: bool((payload or {}).get("active", False)))

    summary = {
        "contract_version": REGIME_AUDIT_CONTRACT_VERSION,
        "regime_engine": engine,
        "regime_semantics": _normalize_text(regime_meta.get("regime_semantics")) or None,
        "confidence_floor": float(confidence_floor),
        "required_blocks": required_blocks,
        "summary": {
            "trading_days": int(len(df)),
            "state_day_counts": {str(k): int(v) for k, v in df["market_state"].value_counts(dropna=False).items() if _normalize_text(k)},
            "base_state_5_day_counts": {
                str(k): int(v) for k, v in df["base_state_5"].value_counts(dropna=False).items() if _normalize_text(k)
            },
            "effective_state_5_day_counts": {
                str(k): int(v) for k, v in df["effective_state_5"].value_counts(dropna=False).items() if _normalize_text(k)
            },
            "coarse_state_day_counts": {
                str(k): int(v) for k, v in df["coarse_state"].value_counts(dropna=False).items() if _normalize_text(k)
            },
            "trade_mode_day_counts": {str(k): int(v) for k, v in df["trade_mode"].value_counts(dropna=False).items() if _normalize_text(k)},
            "switch_count": int(state_change.sum()),
            "transition_event_count": int(len(transition_df)),
            "transition_reason_counts": {
                str(k): int(v)
                for k, v in transition_df["regime_transition_reason"].astype(str).value_counts().items()
                if _normalize_text(k)
            },
            "regime_confidence_mean": _safe_float(pd.to_numeric(df["regime_confidence"], errors="coerce").mean()),
            "low_confidence_days": int(low_conf_mask.fillna(False).sum()),
            "low_confidence_ratio": _safe_float(low_conf_mask.fillna(False).mean()),
            "feature_availability_days": int(feature_days),
            "feature_unavailable_days": int(fallback_days),
            "feature_unavailable_ratio": _safe_float((fallback_days / feature_days) if feature_days > 0 else None),
            "regime_duration_mean": _safe_float(pd.to_numeric(df["regime_duration_bars"], errors="coerce").mean()),
            "confidence_observation_days": int(confidence_valid.sum()),
            "override_active_days": int(override_active.sum()),
        },
        "feature_missing_counts": missing_block_counts,
        "latest_state": {
            "date": latest_row["date"].strftime("%Y-%m-%d"),
            "market_state": _normalize_text(latest_row.get("market_state")),
            "base_state_5": _normalize_text(latest_row.get("base_state_5")),
            "effective_state_5": _normalize_text(latest_row.get("effective_state_5")),
            "coarse_state": _normalize_text(latest_row.get("coarse_state")),
            "effective_coarse_state": _normalize_text(latest_row.get("effective_coarse_state")),
            "trade_mode": _normalize_text(latest_row.get("trade_mode")),
            "regime_confidence": _safe_float(latest_row.get("regime_confidence")),
            "regime_duration_bars": _safe_int(latest_row.get("regime_duration_bars")),
            "regime_transition_reason": _normalize_text(latest_row.get("regime_transition_reason")) or None,
            "feature_availability": latest_feature_availability,
            "reason_codes": list(latest_row.get("reason_codes") or []),
            "subscores": dict(latest_row.get("subscores") or {}),
            "manual_override": dict(latest_row.get("manual_override") or {}),
            "why_today": _normalize_text(latest_row.get("regime_transition_reason")) or "NO_TRANSITION_REASON_RECORDED",
        },
        "latest_transition": latest_transition_row,
    }
    return summary


def build_regime_audit_report(summary: dict[str, Any], transition_df: pd.DataFrame) -> str:
    latest_state = dict(summary.get("latest_state") or {})
    overall = dict(summary.get("summary") or {})
    feature_missing = dict(summary.get("feature_missing_counts") or {})

    lines = [
        "# Regime Audit",
        "",
        "## Conclusion",
        "",
        f"- `regime_engine`: `{summary.get('regime_engine')}`",
        f"- `latest_state`: `{latest_state.get('market_state')}` / `{latest_state.get('trade_mode')}`",
        f"- `why_today`: `{latest_state.get('why_today')}`",
        f"- `switch_count`: `{overall.get('switch_count')}`",
        f"- `low_confidence_days`: `{overall.get('low_confidence_days')}`",
        f"- `feature_unavailable_days`: `{overall.get('feature_unavailable_days')}`",
        "",
        "## Latest State",
        "",
        f"- `date`: `{latest_state.get('date')}`",
        f"- `market_state`: `{latest_state.get('market_state')}`",
        f"- `base_state_5`: `{latest_state.get('base_state_5')}`",
        f"- `effective_state_5`: `{latest_state.get('effective_state_5')}`",
        f"- `coarse_state`: `{latest_state.get('coarse_state')}`",
        f"- `effective_coarse_state`: `{latest_state.get('effective_coarse_state')}`",
        f"- `trade_mode`: `{latest_state.get('trade_mode')}`",
        f"- `regime_confidence`: `{latest_state.get('regime_confidence')}`",
        f"- `regime_duration_bars`: `{latest_state.get('regime_duration_bars')}`",
        f"- `regime_transition_reason`: `{latest_state.get('regime_transition_reason')}`",
        f"- `reason_codes`: `{json.dumps(latest_state.get('reason_codes') or [], ensure_ascii=False)}`",
        f"- `manual_override`: `{json.dumps(latest_state.get('manual_override') or {}, ensure_ascii=False)}`",
        "",
        "## Summary",
        "",
        f"- `state_day_counts`: `{json.dumps(overall.get('state_day_counts') or {}, ensure_ascii=False)}`",
        f"- `base_state_5_day_counts`: `{json.dumps(overall.get('base_state_5_day_counts') or {}, ensure_ascii=False)}`",
        f"- `effective_state_5_day_counts`: `{json.dumps(overall.get('effective_state_5_day_counts') or {}, ensure_ascii=False)}`",
        f"- `trade_mode_day_counts`: `{json.dumps(overall.get('trade_mode_day_counts') or {}, ensure_ascii=False)}`",
        f"- `transition_reason_counts`: `{json.dumps(overall.get('transition_reason_counts') or {}, ensure_ascii=False)}`",
        f"- `feature_missing_counts`: `{json.dumps(feature_missing, ensure_ascii=False)}`",
        "",
        "## Recent Transition Events",
        "",
    ]

    if transition_df.empty:
        lines.append("- No transition events recorded.")
        return "\n".join(lines)

    lines.extend(
        [
            "| date | state | effective | coarse | mode | confidence | duration | reason | low_confidence |",
            "|---|---|---|---|---|---:|---:|---|---|",
        ]
    )
    recent = transition_df.tail(10)
    for row in recent.itertuples(index=False):
        lines.append(
            f"| {row.date} | {row.base_state_5} | {row.effective_state_5} | {row.effective_coarse_state} | {row.trade_mode} | "
            f"{_fmt_float_or_blank(row.regime_confidence)} | "
            f"{'' if pd.isna(row.regime_duration_bars) else int(row.regime_duration_bars)} | "
            f"{row.regime_transition_reason or ''} | {bool(row.low_confidence)} |"
        )
    return "\n".join(lines)


def write_regime_audit_artifacts(
    *,
    results_dir: Path,
    daily_df: pd.DataFrame,
    run_meta: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    summary = build_regime_audit_summary(daily_df=daily_df, run_meta=run_meta)
    if summary is None:
        return None

    df = _normalize_daily_frame(daily_df)
    state_change = (
        df["market_state"].ne(df["market_state"].shift(1))
        | df["trade_mode"].ne(df["trade_mode"].shift(1))
    ) & df.index.to_series().gt(0)
    reason_present = df["regime_transition_reason"].astype(str).str.len() > 0
    transition_mask = state_change | reason_present
    transition_df = df.loc[transition_mask, [
        "date",
        "market_state",
        "base_state_5",
        "effective_state_5",
        "coarse_state",
        "effective_coarse_state",
        "trade_mode",
        "regime_confidence",
        "regime_duration_bars",
        "regime_transition_reason",
        "feature_availability_json",
        "reason_codes",
        "subscores",
        "manual_override",
    ]].copy()
    transition_df["state_changed"] = state_change.loc[transition_mask].astype(bool).to_list()
    transition_df["trade_mode_changed"] = (
        df["trade_mode"].ne(df["trade_mode"].shift(1)).loc[transition_mask] & df.index.to_series().gt(0).loc[transition_mask]
    ).astype(bool).to_list()
    confidence_floor = float(summary.get("confidence_floor") or 0.0)
    transition_df["low_confidence"] = (
        pd.to_numeric(transition_df["regime_confidence"], errors="coerce") < confidence_floor
    ).fillna(False)
    transition_df["date"] = pd.to_datetime(transition_df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    transition_df["reason_codes_json"] = transition_df["reason_codes"].map(lambda payload: json.dumps(list(payload or []), ensure_ascii=False))
    transition_df["subscores_json"] = transition_df["subscores"].map(lambda payload: json.dumps(dict(payload or {}), ensure_ascii=False))
    transition_df["manual_override_json"] = transition_df["manual_override"].map(
        lambda payload: json.dumps(dict(payload or {}), ensure_ascii=False)
    )
    transition_df["override_active"] = transition_df["manual_override"].map(lambda payload: bool((payload or {}).get("active", False)))
    transition_df = transition_df.drop(columns=["reason_codes", "subscores", "manual_override"])

    summary_path = results_dir / _SUMMARY_FILENAME
    debug_path = results_dir / _TRANSITION_DEBUG_FILENAME
    report_path = results_dir / _REPORT_FILENAME

    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    transition_df.to_csv(debug_path, index=False)
    report_path.write_text(build_regime_audit_report(summary, transition_df), encoding="utf-8")

    return {
        "summary": summary,
        "summary_path": summary_path,
        "transition_debug_path": debug_path,
        "report_path": report_path,
    }


__all__ = [
    "REGIME_AUDIT_CONTRACT_VERSION",
    "build_regime_audit_report",
    "build_regime_audit_summary",
    "write_regime_audit_artifacts",
]
