from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from backend.api.shared.json_utils import sanitize_json
from backend.core.tools.runtime_data_access import load_benchmark_series_frame, load_runtime_data_access
from backend.core.universe.ingest_universe import SW_L1_INDEX_MAP
from backend.research.mainline_factor_surface_common import outputs_root
from backend.research.study_definition import StudyDefinition


STYLE_INDEX_SPECS: dict[str, dict[str, str]] = {
    "hs300": {"symbol": "000300.SH", "name": "沪深300", "role": "large_cap"},
    "zz500": {"symbol": "000905.SH", "name": "中证500", "role": "mid_cap"},
    "csi1000": {"symbol": "000852.SH", "name": "中证1000", "role": "small_cap"},
}

DEFAULT_THRESHOLDS = {
    "risk_off_avg_ret20": -0.03,
    "risk_off_avg_ret60": -0.05,
    "risk_off_worst_drawdown60": -0.10,
    "trend_score_strong": 0.60,
    "trend_score_gap": 0.15,
    "relative_ret20_gap": 0.03,
    "split_ret20_gap": 0.02,
    "min_coverage_ratio": 0.70,
    "industry_healthy_ret20": 0.03,
    "industry_healthy_ret60": 0.0,
    "industry_watch_ret20": 0.0,
    "industry_weak_ret20": -0.03,
    "industry_weak_ret60": 0.0,
    "industry_weak_drawdown60": -0.10,
    "industry_min_coverage_ratio": 0.70,
}

INDUSTRY_INDEX_SPECS: dict[str, dict[str, str]] = {
    index_code: {"symbol": index_code, "name": name}
    for name, index_code in sorted(SW_L1_INDEX_MAP.items(), key=lambda item: item[1])
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_repo_path(path_text: str) -> Path:
    raw = Path(str(path_text or "").strip())
    if raw.is_absolute():
        return raw.resolve()
    return (_repo_root() / raw).resolve()


def _study_root(study: StudyDefinition) -> Path:
    parts = [part for part in str(study.study_id or "").replace("\\", "/").split("/") if part]
    return outputs_root().joinpath(*parts).resolve()


def _study_item_dir(study: StudyDefinition, *, window_key: str, variant_name: str) -> Path:
    return (_study_root(study) / str(window_key) / str(variant_name)).resolve()


def _thresholds(runner_params: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {key: float(value) for key, value in DEFAULT_THRESHOLDS.items()}
    custom = runner_params.get("thresholds") if isinstance(runner_params.get("thresholds"), dict) else {}
    for key in out:
        if key not in custom:
            continue
        try:
            out[key] = float(custom[key])
        except Exception:
            continue
    return out


def _style_specs(runner_params: dict[str, Any]) -> dict[str, dict[str, str]]:
    specs = {key: dict(value) for key, value in STYLE_INDEX_SPECS.items()}
    custom = runner_params.get("style_index_symbols")
    if not isinstance(custom, dict):
        return specs
    for key, symbol in custom.items():
        style_key = str(key or "").strip().lower()
        if style_key not in specs:
            continue
        text = str(symbol or "").strip().upper()
        if text:
            specs[style_key]["symbol"] = text
    return specs


def _normalize_index_history(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["date", "symbol", "close"])
    out = frame.copy()
    rename_map: dict[str, str] = {}
    if "trade_date" in out.columns and "date" not in out.columns:
        rename_map["trade_date"] = "date"
    if "index_code" in out.columns and "symbol" not in out.columns:
        rename_map["index_code"] = "symbol"
    if rename_map:
        out.rename(columns=rename_map, inplace=True)
    required = {"date", "symbol", "close"}
    missing = sorted(required - set(out.columns))
    if missing:
        raise ValueError("index history is missing required columns: " + ", ".join(missing))
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out["symbol"] = out["symbol"].astype(str).str.strip().str.upper()
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out = out.loc[out["date"].notna() & out["symbol"].ne("") & out["close"].notna()].copy()
    cols = [col for col in ["date", "symbol", "open", "high", "low", "close", "volume", "amount"] if col in out.columns]
    return out[cols].sort_values(["date", "symbol"]).reset_index(drop=True)


def _load_index_history_from_csv(path: Path) -> pd.DataFrame:
    return _normalize_index_history(pd.read_csv(path, encoding="utf-8-sig", low_memory=False))


def _load_index_history_from_runtime(
    *,
    specs: dict[str, dict[str, str]],
    start: str,
    end: str,
) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    frames: list[pd.DataFrame] = []
    missing: list[dict[str, str]] = []
    start_date = pd.to_datetime(start).date()
    end_date = pd.to_datetime(end).date()
    for key, spec in specs.items():
        symbol = str(spec.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        try:
            frame = load_benchmark_series_frame(
                symbol=symbol,
                start=start_date,
                end=end_date,
                asset_scope="cn_a_equity",
            )
        except Exception as exc:
            missing.append({"style_key": key, "symbol": symbol, "reason": str(exc)})
            continue
        if frame.empty:
            missing.append({"style_key": key, "symbol": symbol, "reason": "runtime provider returned no rows"})
            continue
        frame = frame.copy()
        frame["symbol"] = symbol
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=["date", "symbol", "close"]), missing
    return _normalize_index_history(pd.concat(frames, ignore_index=True)), missing


def _date_filtered(df: pd.DataFrame, *, start: str, end: str) -> pd.DataFrame:
    if df.empty or "date" not in df.columns:
        return pd.DataFrame(columns=list(df.columns))
    start_ts = pd.to_datetime(start)
    end_ts = pd.to_datetime(end)
    out = df.copy()
    out["_date"] = pd.to_datetime(out["date"], errors="coerce")
    return out.loc[(out["_date"] >= start_ts) & (out["_date"] <= end_ts)].drop(columns=["_date"]).copy()


def _drawdown(close: pd.DataFrame, window: int) -> pd.DataFrame:
    high = close.rolling(window, min_periods=max(5, window // 3)).max()
    return close / high - 1.0


def _trend_score(
    *,
    ret20: pd.DataFrame,
    ret60: pd.DataFrame,
    close_vs_ma20: pd.DataFrame,
    ma20_vs_ma60: pd.DataFrame,
    dd60: pd.DataFrame,
) -> pd.DataFrame:
    parts = [
        ret20.gt(0.0),
        ret60.gt(0.0),
        close_vs_ma20.gt(0.0),
        ma20_vs_ma60.gt(0.0),
        dd60.gt(-0.08),
    ]
    stacked = [part.astype(float).where(part.notna()) for part in parts]
    return sum(stacked) / float(len(stacked))


def compute_style_state_daily(
    index_history: pd.DataFrame,
    thresholds: dict[str, float],
    *,
    specs: dict[str, dict[str, str]] | None = None,
) -> pd.DataFrame:
    specs = specs or STYLE_INDEX_SPECS
    history = _normalize_index_history(index_history)
    if history.empty:
        return pd.DataFrame()

    symbol_to_key = {str(spec["symbol"]).upper(): key for key, spec in specs.items()}
    history = history.loc[history["symbol"].isin(symbol_to_key)].copy()
    if history.empty:
        return pd.DataFrame()
    history["style_key"] = history["symbol"].map(symbol_to_key)
    close = history.pivot_table(index="date", columns="style_key", values="close", aggfunc="last").sort_index()
    style_keys = [key for key in ("hs300", "zz500", "csi1000") if key in close.columns]
    close = close.reindex(columns=style_keys)

    ret20 = close.pct_change(20)
    ret60 = close.pct_change(60)
    ma20 = close.rolling(20, min_periods=10).mean()
    ma60 = close.rolling(60, min_periods=30).mean()
    close_vs_ma20 = close / ma20 - 1.0
    ma20_vs_ma60 = ma20 / ma60 - 1.0
    dd20 = _drawdown(close, 20)
    dd60 = _drawdown(close, 60)
    vol20 = close.pct_change().rolling(20, min_periods=10).std()
    score = _trend_score(
        ret20=ret20,
        ret60=ret60,
        close_vs_ma20=close_vs_ma20,
        ma20_vs_ma60=ma20_vs_ma60,
        dd60=dd60,
    )

    rows: list[dict[str, Any]] = []
    for dt in close.index:
        row: dict[str, Any] = {"date": pd.Timestamp(dt).strftime("%Y-%m-%d")}
        present = [key for key in style_keys if pd.notna(close.at[dt, key])]
        mature = [key for key in present if pd.notna(ret60.at[dt, key])]
        row["coverage_count"] = int(len(present))
        row["mature_coverage_count"] = int(len(mature))
        row["coverage_ratio"] = float(len(present) / max(len(specs), 1))
        row["mature_coverage_ratio"] = float(len(mature) / max(len(specs), 1))
        row["coverage_status"] = "complete" if len(mature) == len(specs) else ("partial" if len(mature) >= 2 else "insufficient")
        for key in style_keys:
            row[f"{key}_symbol"] = specs[key]["symbol"]
            row[f"{key}_name"] = specs[key]["name"]
            for prefix, frame in (
                ("ret20", ret20),
                ("ret60", ret60),
                ("close_vs_ma20", close_vs_ma20),
                ("ma20_vs_ma60", ma20_vs_ma60),
                ("drawdown20", dd20),
                ("drawdown60", dd60),
                ("vol20", vol20),
                ("trend_score", score),
            ):
                value = frame.at[dt, key] if key in frame.columns else pd.NA
                row[f"{key}_{prefix}"] = None if pd.isna(value) else float(value)

        hs_ret20 = row.get("hs300_ret20")
        zz_ret20 = row.get("zz500_ret20")
        c1_ret20 = row.get("csi1000_ret20")
        row["zz500_minus_hs300_ret20"] = None if hs_ret20 is None or zz_ret20 is None else float(zz_ret20 - hs_ret20)
        row["csi1000_minus_hs300_ret20"] = None if hs_ret20 is None or c1_ret20 is None else float(c1_ret20 - hs_ret20)
        row["csi1000_minus_zz500_ret20"] = None if zz_ret20 is None or c1_ret20 is None else float(c1_ret20 - zz_ret20)

        mature_ret20 = [row.get(f"{key}_ret20") for key in mature if row.get(f"{key}_ret20") is not None]
        mature_ret60 = [row.get(f"{key}_ret60") for key in mature if row.get(f"{key}_ret60") is not None]
        mature_dd60 = [row.get(f"{key}_drawdown60") for key in mature if row.get(f"{key}_drawdown60") is not None]
        mature_scores = {key: row.get(f"{key}_trend_score") for key in mature if row.get(f"{key}_trend_score") is not None}
        row["avg_ret20"] = float(sum(mature_ret20) / len(mature_ret20)) if mature_ret20 else None
        row["avg_ret60"] = float(sum(mature_ret60) / len(mature_ret60)) if mature_ret60 else None
        row["worst_drawdown60"] = float(min(mature_dd60)) if mature_dd60 else None

        label = "unknown"
        reason = "insufficient mature style-index coverage"
        if len(mature_scores) >= 2:
            avg_ret20 = float(row["avg_ret20"] or 0.0)
            avg_ret60 = float(row["avg_ret60"] or 0.0)
            worst_dd60 = float(row["worst_drawdown60"] or 0.0)
            rel_mid = row.get("zz500_minus_hs300_ret20")
            rel_small = row.get("csi1000_minus_hs300_ret20")
            rel_values = [abs(float(value)) for value in (rel_mid, rel_small, row.get("csi1000_minus_zz500_ret20")) if value is not None]
            strongest = max(mature_scores, key=lambda key: float(mature_scores[key] or 0.0))
            weakest = min(mature_scores, key=lambda key: float(mature_scores[key] or 0.0))
            strongest_score = float(mature_scores[strongest] or 0.0)
            weakest_score = float(mature_scores[weakest] or 0.0)
            gap = strongest_score - weakest_score
            if (
                avg_ret20 <= thresholds["risk_off_avg_ret20"]
                and avg_ret60 <= thresholds["risk_off_avg_ret60"]
                and worst_dd60 <= thresholds["risk_off_worst_drawdown60"]
            ):
                label = "risk_off"
                reason = "broad index returns and drawdown are both weak"
            elif (
                strongest == "hs300"
                and strongest_score >= thresholds["trend_score_strong"]
                and gap >= thresholds["trend_score_gap"]
                and (rel_mid is None or rel_mid <= -thresholds["split_ret20_gap"])
                and (rel_small is None or rel_small <= -thresholds["split_ret20_gap"])
            ):
                label = "large_cap_defense"
                reason = "HS300 trend is stronger while mid/small-cap relative returns lag"
            elif (
                strongest in {"zz500", "csi1000"}
                and strongest_score >= thresholds["trend_score_strong"]
                and (
                    (rel_mid is not None and rel_mid >= thresholds["relative_ret20_gap"])
                    or (rel_small is not None and rel_small >= thresholds["relative_ret20_gap"])
                )
            ):
                label = "mid_small_beta"
                reason = "ZZ500/CSI1000 trend is stronger with positive relative ret20"
            elif avg_ret20 > 0 and avg_ret60 > 0 and min(float(value or 0.0) for value in mature_scores.values()) >= thresholds["trend_score_strong"]:
                label = "broad_bull"
                reason = "major style indices are jointly above trend thresholds"
            elif gap >= thresholds["trend_score_gap"] or (rel_values and max(rel_values) >= thresholds["split_ret20_gap"]):
                label = "split_rotation"
                reason = "style-index scores or relative returns diverge"
            else:
                label = "split_rotation"
                reason = "no broad risk-off or broad-bull agreement; treat as mixed rotation"
        row["style_state_label"] = label
        row["style_state_reason"] = reason
        rows.append(row)
    return pd.DataFrame(rows)


def _industry_specs() -> dict[str, dict[str, str]]:
    return {key: dict(value) for key, value in INDUSTRY_INDEX_SPECS.items()}


def _load_industry_history_from_runtime(*, start: str, end: str) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    start_date = pd.to_datetime(start).date()
    end_date = pd.to_datetime(end).date()
    try:
        access = load_runtime_data_access(asset_scope="cn_a_equity")
        frame = access.provider.load_sector_indices(start_date, end_date)
    except Exception as exc:
        return pd.DataFrame(columns=["date", "symbol", "close"]), [
            {"source": "load_sector_indices", "reason": str(exc)}
        ]
    if frame.empty:
        return pd.DataFrame(columns=["date", "symbol", "close"]), [
            {"source": "load_sector_indices", "reason": "runtime provider returned no rows"}
        ]
    return _normalize_index_history(frame), []


def _load_industry_source_frame(
    *,
    runner_params: dict[str, Any],
    start: str,
    end: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    csv_path_text = str(runner_params.get("industry_index_history_csv") or "").strip()
    if csv_path_text:
        csv_path = _resolve_repo_path(csv_path_text)
        if not csv_path.exists():
            return pd.DataFrame(), {
                "source_kind": "csv",
                "source_path": str(csv_path),
                "missing_source": True,
                "reason": f"industry_index_history_csv not found: {csv_path}",
            }
        return _load_index_history_from_csv(csv_path), {
            "source_kind": "csv",
            "source_path": str(csv_path),
            "missing_source": False,
            "missing_index_symbols": [],
        }
    frame, missing = _load_industry_history_from_runtime(start=start, end=end)
    return frame, {
        "source_kind": "runtime_provider",
        "source_path": "pit_index_daily 801*.SI via load_sector_indices",
        "missing_source": frame.empty,
        "missing_index_symbols": missing,
        "reason": "runtime provider returned no SW L1 industry rows" if frame.empty else "",
    }


def compute_industry_health_daily(
    industry_history: pd.DataFrame,
    thresholds: dict[str, float],
    *,
    specs: dict[str, dict[str, str]] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    specs = specs or _industry_specs()
    history = _normalize_index_history(industry_history)
    if history.empty:
        return pd.DataFrame(), pd.DataFrame()
    symbol_to_name = {str(spec["symbol"]).upper(): str(spec["name"]) for spec in specs.values()}
    history = history.loc[history["symbol"].isin(symbol_to_name)].copy()
    if history.empty:
        return pd.DataFrame(), pd.DataFrame()
    close = history.pivot_table(index="date", columns="symbol", values="close", aggfunc="last").sort_index()
    ret20 = close.pct_change(20)
    ret60 = close.pct_change(60)
    ma20 = close.rolling(20, min_periods=10).mean()
    ma60 = close.rolling(60, min_periods=30).mean()
    dd60 = _drawdown(close, 60)
    score = _trend_score(
        ret20=ret20,
        ret60=ret60,
        close_vs_ma20=close / ma20 - 1.0,
        ma20_vs_ma60=ma20 / ma60 - 1.0,
        dd60=dd60,
    )

    long_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    expected_count = max(len(specs), 1)
    for dt in close.index:
        present = [symbol for symbol in close.columns if pd.notna(close.at[dt, symbol])]
        mature = [symbol for symbol in present if pd.notna(ret60.at[dt, symbol])]
        day_items: list[dict[str, Any]] = []
        for symbol in present:
            r20 = ret20.at[dt, symbol] if symbol in ret20.columns else pd.NA
            r60 = ret60.at[dt, symbol] if symbol in ret60.columns else pd.NA
            d60 = dd60.at[dt, symbol] if symbol in dd60.columns else pd.NA
            sc = score.at[dt, symbol] if symbol in score.columns else pd.NA
            if pd.isna(r60):
                label = "unknown"
                reason = "insufficient mature industry-index coverage"
            elif (
                float(r20) <= thresholds["industry_weak_ret20"]
                or (float(r20) < thresholds["industry_watch_ret20"] and float(r60) < thresholds["industry_weak_ret60"])
                or float(d60) <= thresholds["industry_weak_drawdown60"]
            ):
                label = "weak"
                reason = "industry ret20/ret60/drawdown is weak"
            elif float(r20) >= thresholds["industry_healthy_ret20"] and float(r60) >= thresholds["industry_healthy_ret60"] and float(sc) >= thresholds["trend_score_strong"]:
                label = "healthy"
                reason = "industry ret20/ret60 and trend score are positive"
            elif float(r20) >= thresholds["industry_watch_ret20"] and float(sc) >= 0.40:
                label = "watch"
                reason = "industry is positive but not broad healthy"
            else:
                label = "watch"
                reason = "industry is mixed"
            item = {
                "date": pd.Timestamp(dt).strftime("%Y-%m-%d"),
                "industry_index_code": symbol,
                "industry_name": symbol_to_name.get(symbol, symbol),
                "industry_health_label": label,
                "industry_health_reason": reason,
                "ret20": None if pd.isna(r20) else float(r20),
                "ret60": None if pd.isna(r60) else float(r60),
                "drawdown60": None if pd.isna(d60) else float(d60),
                "trend_score": None if pd.isna(sc) else float(sc),
            }
            long_rows.append(item)
            if label != "unknown":
                day_items.append(item)
        labels = [item["industry_health_label"] for item in day_items]
        healthy = sum(1 for value in labels if value == "healthy")
        weak = sum(1 for value in labels if value == "weak")
        watch = sum(1 for value in labels if value == "watch")
        available = max(len(day_items), 1)
        ranked = sorted(
            day_items,
            key=lambda item: -999.0 if item.get("ret20") is None else float(item["ret20"]),
            reverse=True,
        )
        breadth = healthy / available if day_items else 0.0
        weak_ratio = weak / available if day_items else 0.0
        if not day_items:
            market_label = "unknown"
            market_reason = "no mature industry rows"
        elif weak_ratio >= 0.50:
            market_label = "industry_broad_weak"
            market_reason = "more than half of mature industries are weak"
        elif breadth >= 0.50:
            market_label = "industry_broad_healthy"
            market_reason = "more than half of mature industries are healthy"
        elif healthy >= 3 and weak >= 3:
            market_label = "industry_rotation"
            market_reason = "healthy and weak industries coexist"
        else:
            market_label = "industry_mixed"
            market_reason = "industry health is mixed"
        daily_rows.append(
            {
                "date": pd.Timestamp(dt).strftime("%Y-%m-%d"),
                "coverage_count": int(len(present)),
                "mature_coverage_count": int(len(mature)),
                "coverage_ratio": float(len(present) / expected_count),
                "mature_coverage_ratio": float(len(mature) / expected_count),
                "healthy_industry_count": int(healthy),
                "watch_industry_count": int(watch),
                "weak_industry_count": int(weak),
                "industry_breadth_healthy": float(breadth),
                "industry_breadth_weak": float(weak_ratio),
                "industry_market_health_label": market_label,
                "industry_market_health_reason": market_reason,
                "top_healthy_industries": "; ".join(
                    f"{item['industry_name']}:{float(item['ret20']):.2%}"
                    for item in ranked[:5]
                    if item.get("ret20") is not None
                ),
                "top_weak_industries": "; ".join(
                    f"{item['industry_name']}:{float(item['ret20']):.2%}"
                    for item in sorted(
                        day_items,
                        key=lambda item: 999.0 if item.get("ret20") is None else float(item["ret20"]),
                    )[:5]
                    if item.get("ret20") is not None
                ),
            }
        )
    return pd.DataFrame(daily_rows), pd.DataFrame(long_rows)


def _baseline_artifact_root(runner_params: dict[str, Any], baseline_id: str) -> Path:
    root_text = str(runner_params.get("baseline_artifact_root") or "").strip()
    if root_text:
        return _resolve_repo_path(root_text)
    artifact_id = str(runner_params.get("baseline_artifact_id") or baseline_id or "").strip()
    if not artifact_id:
        artifact_id = "CN_STOCK_ETF_COMBO_BASELINE_V4"
    return (_repo_root() / "outputs" / "baselines" / artifact_id).resolve()


def _load_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)


def _resolve_stock_component_exp_id(frame: pd.DataFrame) -> str:
    if frame.empty or "component_exp_id" not in frame.columns:
        return ""
    work = frame.copy()
    if "sleeve_id" in work.columns:
        sleeve = work["sleeve_id"].fillna("").astype(str)
        work = work.loc[sleeve.str.contains("stock", case=False, na=False)].copy()
    values = [
        str(value or "").strip()
        for value in work["component_exp_id"].dropna().astype(str).tolist()
        if str(value or "").strip()
    ]
    return values[0] if values else ""


def _load_candidate_signals_source(
    *,
    runner_params: dict[str, Any],
    baseline_root: Path,
    orders_frame: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    explicit = str(runner_params.get("candidate_signals_csv") or "").strip()
    source_kind = "explicit_csv"
    path = _resolve_repo_path(explicit) if explicit else baseline_root / "candidate_signals.csv"
    if not explicit:
        source_kind = "baseline_artifact"
    if not path.exists() and not explicit:
        exp_id = _resolve_stock_component_exp_id(orders_frame)
        if exp_id:
            path = (_repo_root() / "outputs" / "experiments" / exp_id / "candidate_signals.csv").resolve()
            source_kind = "component_experiment_candidate_signals"
    if not path.exists() and not explicit:
        exp_id = _resolve_stock_component_exp_id(orders_frame)
        if exp_id:
            path = (_repo_root() / "outputs" / "experiments" / exp_id / "portfolio_candidates.csv").resolve()
            source_kind = "component_experiment_portfolio_candidates"
    if not path.exists():
        return pd.DataFrame(), {
            "source_kind": source_kind,
            "source_path": str(path),
            "missing_source": True,
            "reason": f"candidate signal source not found: {path}",
            "stock_component_exp_id": _resolve_stock_component_exp_id(orders_frame),
        }
    frame = _load_csv_if_exists(path)
    if not frame.empty:
        selected_count = int(
            frame.get("selected_flag", frame.get("selected", False))
            .fillna(False)
            .astype(str)
            .str.lower()
            .isin(["true", "1", "yes"])
            .sum()
        )
        reject_reason_counts = (
            frame.get("reject_reason", pd.Series(dtype=str))
            .fillna("")
            .astype(str)
            .replace("", "NONE")
            .value_counts()
            .head(12)
            .to_dict()
        )
    else:
        selected_count = 0
        reject_reason_counts = {}
    source_scope = (
        "rejected_or_diagnostic_candidates"
        if int(len(frame)) > 0 and selected_count == 0 and set(reject_reason_counts).difference({"NONE"})
        else "candidate_signals"
    )
    return frame, {
        "source_kind": source_kind,
        "source_scope": source_scope,
        "source_path": str(path),
        "missing_source": frame.empty,
        "reason": "candidate signal source is empty" if frame.empty else "",
        "row_count": int(len(frame)),
        "selected_row_count": selected_count,
        "reject_reason_counts": reject_reason_counts,
        "stock_component_exp_id": _resolve_stock_component_exp_id(orders_frame),
    }


def _load_stock_industry_history_from_runtime(
    *,
    symbols: list[str],
    start: str,
    end: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    clean_symbols = sorted({str(symbol or "").strip().lower() for symbol in symbols if str(symbol or "").strip()})
    if not clean_symbols:
        return pd.DataFrame(columns=["symbol", "industry_l1", "start_date", "end_date"]), {
            "source_kind": "runtime_provider",
            "source_path": "pit_industry_history via load_industry_history",
            "missing_source": False,
            "symbol_count": 0,
            "loaded_symbol_count": 0,
        }
    start_date = pd.to_datetime(start).date()
    end_date = pd.to_datetime(end).date()
    try:
        access = load_runtime_data_access(asset_scope="cn_a_equity")
        frame = access.provider.load_industry_history(clean_symbols, start_date, end_date)
    except Exception as exc:
        return pd.DataFrame(columns=["symbol", "industry_l1", "start_date", "end_date"]), {
            "source_kind": "runtime_provider",
            "source_path": "pit_industry_history via load_industry_history",
            "missing_source": True,
            "reason": str(exc),
            "symbol_count": len(clean_symbols),
            "loaded_symbol_count": 0,
        }
    if frame.empty:
        return pd.DataFrame(columns=["symbol", "industry_l1", "start_date", "end_date"]), {
            "source_kind": "runtime_provider",
            "source_path": "pit_industry_history via load_industry_history",
            "missing_source": True,
            "reason": "runtime provider returned no PIT industry rows",
            "symbol_count": len(clean_symbols),
            "loaded_symbol_count": 0,
        }
    out = frame.copy()
    if "ts_code" in out.columns and "symbol" not in out.columns:
        out.rename(columns={"ts_code": "symbol"}, inplace=True)
    out["symbol"] = out["symbol"].astype(str).str.strip().str.lower()
    out["industry_l1"] = out.get("industry_l1", pd.Series(dtype=str)).fillna("").astype(str).str.strip()
    out["start_date"] = pd.to_datetime(out["start_date"], errors="coerce").dt.normalize()
    out["end_date"] = pd.to_datetime(out.get("end_date"), errors="coerce").dt.normalize()
    out = out.loc[out["symbol"].ne("") & out["start_date"].notna()].copy()
    return out, {
        "source_kind": "runtime_provider",
        "source_path": "pit_industry_history via load_industry_history",
        "missing_source": False,
        "symbol_count": len(clean_symbols),
        "loaded_symbol_count": int(out["symbol"].nunique()),
    }


def _prepare_stock_trades(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["date", "symbol", "side", "qty"])
    out = trades.copy()
    out["symbol"] = out.get("symbol", pd.Series(dtype=str)).astype(str).str.strip().str.lower()
    out["date"] = pd.to_datetime(out.get("date"), errors="coerce").dt.normalize()
    out["side"] = out.get("side", pd.Series(dtype=str)).astype(str).str.strip().str.upper()
    out["qty"] = pd.to_numeric(out.get("qty"), errors="coerce").fillna(0.0)
    if "sleeve_id" in out.columns:
        sleeve = out["sleeve_id"].fillna("").astype(str)
        out = out.loc[sleeve.eq("") | sleeve.str.contains("stock", case=False, na=False)].copy()
    out = out.loc[out["date"].notna() & out["symbol"].str.match(r"^(sh|sz)\d{6}$") & out["side"].isin(["BUY", "SELL"])].copy()
    return out[["date", "symbol", "side", "qty"]].sort_values(["date", "symbol"]).reset_index(drop=True)


def _build_daily_stock_holdings(trades: pd.DataFrame, nav: pd.DataFrame) -> pd.DataFrame:
    trades = _prepare_stock_trades(trades)
    if nav.empty or "date" not in nav.columns:
        return pd.DataFrame(columns=["date", "symbol", "qty"])
    dates = pd.to_datetime(nav["date"], errors="coerce").dropna().dt.normalize().drop_duplicates().sort_values()
    if dates.empty or trades.empty:
        return pd.DataFrame(columns=["date", "symbol", "qty"])
    by_date = {dt: frame for dt, frame in trades.groupby("date")}
    positions: dict[str, float] = {}
    rows: list[dict[str, Any]] = []
    for dt in dates:
        frame = by_date.get(dt)
        if frame is not None:
            for row in frame.itertuples(index=False):
                sign = 1.0 if str(row.side).upper() == "BUY" else -1.0
                positions[str(row.symbol)] = positions.get(str(row.symbol), 0.0) + sign * float(row.qty or 0.0)
                if positions[str(row.symbol)] <= 0.000001:
                    positions.pop(str(row.symbol), None)
        for symbol, qty in sorted(positions.items()):
            rows.append({"date": pd.Timestamp(dt).strftime("%Y-%m-%d"), "symbol": symbol, "qty": float(qty)})
    return pd.DataFrame(rows)


def _attach_pit_industry(holdings: pd.DataFrame, industry_history: pd.DataFrame) -> pd.DataFrame:
    if holdings.empty:
        return holdings.assign(industry_l1="", industry_index_code="")
    if industry_history.empty:
        out = holdings.copy()
        out["industry_l1"] = ""
        out["industry_index_code"] = ""
        return out
    intervals: dict[str, pd.DataFrame] = {}
    hist = industry_history.copy()
    hist["symbol"] = hist["symbol"].astype(str).str.strip().str.lower()
    hist["start_date"] = pd.to_datetime(hist["start_date"], errors="coerce").dt.normalize()
    hist["end_date"] = pd.to_datetime(hist["end_date"], errors="coerce").dt.normalize()
    for symbol, frame in hist.sort_values(["symbol", "start_date"]).groupby("symbol"):
        intervals[str(symbol)] = frame
    industry_names: list[str] = []
    for row in holdings.itertuples(index=False):
        dt = pd.to_datetime(getattr(row, "date"), errors="coerce").normalize()
        frame = intervals.get(str(getattr(row, "symbol")).lower())
        value = ""
        if frame is not None and pd.notna(dt):
            hit = frame.loc[
                (frame["start_date"] <= dt)
                & (frame["end_date"].isna() | (frame["end_date"] > dt))
            ]
            if not hit.empty:
                value = str(hit.iloc[-1].get("industry_l1") or "")
        industry_names.append(value)
    out = holdings.copy()
    out["industry_l1"] = industry_names
    out["industry_index_code"] = out["industry_l1"].map(SW_L1_INDEX_MAP).fillna("")
    return out


def compute_rotation_pressure_daily(
    *,
    trades: pd.DataFrame,
    nav: pd.DataFrame,
    industry_history: pd.DataFrame,
    industry_long_daily: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    holdings = _build_daily_stock_holdings(trades, nav)
    holdings = _attach_pit_industry(holdings, industry_history)
    if nav.empty or "date" not in nav.columns:
        return pd.DataFrame(), pd.DataFrame()
    nav_frame = nav.copy()
    nav_frame["date"] = pd.to_datetime(nav_frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    nav_frame = nav_frame.loc[nav_frame["date"].notna()].copy()
    health = industry_long_daily.copy()
    if not health.empty:
        health["date"] = pd.to_datetime(health["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        health["industry_index_code"] = health["industry_index_code"].astype(str).str.strip().str.upper()
        health = health[
            [
                "date",
                "industry_index_code",
                "industry_name",
                "industry_health_label",
                "ret20",
                "ret60",
                "drawdown60",
                "trend_score",
            ]
        ].copy()
    else:
        health = pd.DataFrame(columns=["date", "industry_index_code", "industry_name", "industry_health_label", "ret20", "ret60", "drawdown60", "trend_score"])
    if not holdings.empty:
        holdings["date"] = pd.to_datetime(holdings["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        holdings["industry_index_code"] = holdings["industry_index_code"].astype(str).str.strip().str.upper()
        holdings = holdings.merge(health, how="left", on=["date", "industry_index_code"], suffixes=("", "_health"))
        holdings["industry_health_label"] = holdings["industry_health_label"].fillna("unknown")
        holdings["industry_name"] = holdings["industry_name"].fillna(holdings["industry_l1"])
    holding_rows: list[dict[str, Any]] = []
    if not holdings.empty:
        for (dt, index_code, industry_name), frame in holdings.groupby(["date", "industry_index_code", "industry_name"], dropna=False):
            labels = frame["industry_health_label"].fillna("unknown").astype(str)
            holding_rows.append(
                {
                    "date": str(dt),
                    "industry_index_code": str(index_code or ""),
                    "industry_name": str(industry_name or ""),
                    "held_symbol_count": int(frame["symbol"].nunique()),
                    "held_qty_sum": float(pd.to_numeric(frame["qty"], errors="coerce").fillna(0.0).sum()),
                    "industry_health_label": str(labels.mode().iloc[0]) if not labels.empty else "unknown",
                    "held_symbols": ";".join(sorted(frame["symbol"].astype(str).unique())),
                    "ret20": None if frame["ret20"].isna().all() else float(pd.to_numeric(frame["ret20"], errors="coerce").dropna().iloc[-1]),
                    "ret60": None if frame["ret60"].isna().all() else float(pd.to_numeric(frame["ret60"], errors="coerce").dropna().iloc[-1]),
                }
            )
    held_industry_daily = pd.DataFrame(holding_rows).sort_values(["date", "industry_index_code"]).reset_index(drop=True) if holding_rows else pd.DataFrame()

    daily_rows: list[dict[str, Any]] = []
    holdings_by_date = {str(dt): frame for dt, frame in holdings.groupby("date")} if not holdings.empty else {}
    for row in nav_frame.itertuples(index=False):
        dt = str(getattr(row, "date"))
        frame = holdings_by_date.get(dt, pd.DataFrame())
        stock_ret = getattr(row, "stock_ret", None) if hasattr(row, "stock_ret") else None
        combo_ret = getattr(row, "combo_ret", None) if hasattr(row, "combo_ret") else None
        if frame.empty:
            label = "no_stock_exposure"
            reason = "stock leg has no holdings"
            counts = {"healthy": 0, "watch": 0, "weak": 0, "unknown": 0}
            held_count = 0
            industry_count = 0
        else:
            labels = frame["industry_health_label"].fillna("unknown").astype(str)
            counts = {key: int(labels.eq(key).sum()) for key in ["healthy", "watch", "weak", "unknown"]}
            held_count = int(frame["symbol"].nunique())
            industry_count = int(frame["industry_index_code"].replace("", pd.NA).dropna().nunique())
            weak_ratio = counts["weak"] / max(held_count, 1)
            healthy_ratio = counts["healthy"] / max(held_count, 1)
            unknown_ratio = counts["unknown"] / max(held_count, 1)
            if unknown_ratio >= 0.50:
                label = "unknown"
                reason = "most held stocks cannot be mapped to an I1 industry state"
            elif weak_ratio >= 0.50:
                label = "held_broad_weak"
                reason = "at least half of held stocks are in weak industries"
            elif weak_ratio >= 0.30 and healthy_ratio < 0.40:
                label = "rotation_pressure"
                reason = "weak-industry exposure is material while healthy exposure is not dominant"
            elif healthy_ratio >= 0.50:
                label = "held_broad_healthy"
                reason = "at least half of held stocks are in healthy industries"
            else:
                label = "held_mixed"
                reason = "held industries are mixed"
        daily_rows.append(
            {
                "date": dt,
                "held_stock_count": held_count,
                "held_industry_count": industry_count,
                "held_healthy_count": counts["healthy"],
                "held_watch_count": counts["watch"],
                "held_weak_count": counts["weak"],
                "held_unknown_count": counts["unknown"],
                "held_healthy_ratio": float(counts["healthy"] / max(held_count, 1)),
                "held_weak_ratio": float(counts["weak"] / max(held_count, 1)),
                "held_unknown_ratio": float(counts["unknown"] / max(held_count, 1)),
                "rotation_pressure_label": label,
                "rotation_pressure_reason": reason,
                "stock_ret": None if pd.isna(stock_ret) else float(stock_ret),
                "combo_ret": None if pd.isna(combo_ret) else float(combo_ret),
            }
        )
    return pd.DataFrame(daily_rows), held_industry_daily


def _rotation_pressure_summary(daily: pd.DataFrame, held_industry_daily: pd.DataFrame) -> dict[str, Any]:
    if daily.empty:
        return {
            "row_count": 0,
            "first_date": "",
            "last_date": "",
            "latest_rotation_pressure": "unknown",
            "label_counts": {},
        }
    labels = daily["rotation_pressure_label"].fillna("unknown").astype(str)
    latest = daily.iloc[-1]
    by_label: dict[str, dict[str, Any]] = {}
    work = daily.copy()
    work["stock_ret"] = pd.to_numeric(work["stock_ret"], errors="coerce").fillna(0.0)
    work["combo_ret"] = pd.to_numeric(work["combo_ret"], errors="coerce").fillna(0.0)
    for label, frame in work.groupby("rotation_pressure_label"):
        by_label[str(label)] = {
            "days": int(len(frame)),
            "stock_ret_total": float((1.0 + frame["stock_ret"]).prod() - 1.0),
            "combo_ret_total": float((1.0 + frame["combo_ret"]).prod() - 1.0),
            "avg_held_weak_ratio": float(pd.to_numeric(frame["held_weak_ratio"], errors="coerce").mean()),
            "avg_held_healthy_ratio": float(pd.to_numeric(frame["held_healthy_ratio"], errors="coerce").mean()),
        }
    latest_industries = ""
    if not held_industry_daily.empty:
        latest_held = held_industry_daily.loc[held_industry_daily["date"].astype(str) == str(latest["date"])].copy()
        latest_industries = "; ".join(
            f"{row.industry_name}:{row.industry_health_label}:{int(row.held_symbol_count)}"
            for row in latest_held.sort_values(["industry_health_label", "industry_name"]).itertuples(index=False)
        )
    return sanitize_json(
        {
            "row_count": int(len(daily)),
            "first_date": str(daily["date"].iloc[0]),
            "last_date": str(daily["date"].iloc[-1]),
            "latest_rotation_pressure": str(latest["rotation_pressure_label"]),
            "latest_reason": str(latest["rotation_pressure_reason"]),
            "latest_held_stock_count": int(latest["held_stock_count"]),
            "latest_held_industry_count": int(latest["held_industry_count"]),
            "latest_held_healthy_count": int(latest["held_healthy_count"]),
            "latest_held_watch_count": int(latest["held_watch_count"]),
            "latest_held_weak_count": int(latest["held_weak_count"]),
            "latest_held_industries": latest_industries,
            "avg_held_weak_ratio": float(pd.to_numeric(daily["held_weak_ratio"], errors="coerce").mean()),
            "avg_held_healthy_ratio": float(pd.to_numeric(daily["held_healthy_ratio"], errors="coerce").mean()),
            "label_counts": {str(key): int(value) for key, value in labels.value_counts().to_dict().items()},
            "by_label": by_label,
        }
    )


def compute_entry_candidate_pressure_daily(
    *,
    orders: pd.DataFrame,
    nav: pd.DataFrame,
    industry_history: pd.DataFrame,
    industry_long_daily: pd.DataFrame,
    rotation_daily: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    stock_orders = _prepare_stock_trades(orders)
    entries = stock_orders.loc[stock_orders["side"].eq("BUY")].copy()
    entries = _attach_pit_industry(entries, industry_history)
    if nav.empty or "date" not in nav.columns:
        return pd.DataFrame(), pd.DataFrame()
    nav_frame = nav.copy()
    nav_frame["date"] = pd.to_datetime(nav_frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    nav_frame = nav_frame.loc[nav_frame["date"].notna()].copy()

    health = industry_long_daily.copy()
    if not health.empty:
        health["date"] = pd.to_datetime(health["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        health["industry_index_code"] = health["industry_index_code"].astype(str).str.strip().str.upper()
        health = health[
            [
                "date",
                "industry_index_code",
                "industry_name",
                "industry_health_label",
                "ret20",
                "ret60",
                "drawdown60",
                "trend_score",
            ]
        ].copy()
    else:
        health = pd.DataFrame(columns=["date", "industry_index_code", "industry_name", "industry_health_label", "ret20", "ret60", "drawdown60", "trend_score"])

    if not entries.empty:
        entries["date"] = pd.to_datetime(entries["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        entries["industry_index_code"] = entries["industry_index_code"].astype(str).str.strip().str.upper()
        entries = entries.merge(health, how="left", on=["date", "industry_index_code"], suffixes=("", "_health"))
        entries["industry_health_label"] = entries["industry_health_label"].fillna("unknown")
        entries["industry_name"] = entries["industry_name"].fillna(entries["industry_l1"])

    entry_rows: list[dict[str, Any]] = []
    if not entries.empty:
        for (dt, index_code, industry_name), frame in entries.groupby(["date", "industry_index_code", "industry_name"], dropna=False):
            labels = frame["industry_health_label"].fillna("unknown").astype(str)
            entry_rows.append(
                {
                    "date": str(dt),
                    "industry_index_code": str(index_code or ""),
                    "industry_name": str(industry_name or ""),
                    "entry_symbol_count": int(frame["symbol"].nunique()),
                    "entry_qty_sum": float(pd.to_numeric(frame["qty"], errors="coerce").fillna(0.0).sum()),
                    "industry_health_label": str(labels.mode().iloc[0]) if not labels.empty else "unknown",
                    "entry_symbols": ";".join(sorted(frame["symbol"].astype(str).unique())),
                    "ret20": None if frame["ret20"].isna().all() else float(pd.to_numeric(frame["ret20"], errors="coerce").dropna().iloc[-1]),
                    "ret60": None if frame["ret60"].isna().all() else float(pd.to_numeric(frame["ret60"], errors="coerce").dropna().iloc[-1]),
                }
            )
    entry_industry_daily = pd.DataFrame(entry_rows).sort_values(["date", "industry_index_code"]).reset_index(drop=True) if entry_rows else pd.DataFrame()

    rotation = rotation_daily.copy()
    if not rotation.empty:
        rotation["date"] = pd.to_datetime(rotation["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        rotation = rotation[
            [
                "date",
                "held_stock_count",
                "held_healthy_ratio",
                "held_weak_ratio",
                "rotation_pressure_label",
            ]
        ].copy()
    else:
        rotation = pd.DataFrame(columns=["date", "held_stock_count", "held_healthy_ratio", "held_weak_ratio", "rotation_pressure_label"])

    entries_by_date = {str(dt): frame for dt, frame in entries.groupby("date")} if not entries.empty else {}
    daily_rows: list[dict[str, Any]] = []
    for row in nav_frame.itertuples(index=False):
        dt = str(getattr(row, "date"))
        frame = entries_by_date.get(dt, pd.DataFrame())
        stock_ret = getattr(row, "stock_ret", None) if hasattr(row, "stock_ret") else None
        combo_ret = getattr(row, "combo_ret", None) if hasattr(row, "combo_ret") else None
        if frame.empty:
            counts = {"healthy": 0, "watch": 0, "weak": 0, "unknown": 0}
            entry_count = 0
            industry_count = 0
            entry_label = "no_entry"
            entry_reason = "no stock buy order on this date"
        else:
            labels = frame["industry_health_label"].fillna("unknown").astype(str)
            counts = {key: int(labels.eq(key).sum()) for key in ["healthy", "watch", "weak", "unknown"]}
            entry_count = int(frame["symbol"].nunique())
            industry_count = int(frame["industry_index_code"].replace("", pd.NA).dropna().nunique())
            weak_ratio = counts["weak"] / max(entry_count, 1)
            healthy_ratio = counts["healthy"] / max(entry_count, 1)
            unknown_ratio = counts["unknown"] / max(entry_count, 1)
            if unknown_ratio >= 0.50:
                entry_label = "entry_unknown"
                entry_reason = "most entry orders cannot be mapped to an I1 industry state"
            elif weak_ratio >= 0.50:
                entry_label = "entry_broad_weak"
                entry_reason = "at least half of buy orders are in weak industries"
            elif weak_ratio >= 0.30 and healthy_ratio < 0.40:
                entry_label = "entry_rotation_pressure"
                entry_reason = "buy orders include material weak-industry exposure"
            elif healthy_ratio >= 0.50:
                entry_label = "entry_broad_healthy"
                entry_reason = "at least half of buy orders are in healthy industries"
            else:
                entry_label = "entry_mixed"
                entry_reason = "buy-order industries are mixed"
        daily_rows.append(
            {
                "date": dt,
                "entry_stock_count": entry_count,
                "entry_industry_count": industry_count,
                "entry_healthy_count": counts["healthy"],
                "entry_watch_count": counts["watch"],
                "entry_weak_count": counts["weak"],
                "entry_unknown_count": counts["unknown"],
                "entry_healthy_ratio": float(counts["healthy"] / max(entry_count, 1)),
                "entry_weak_ratio": float(counts["weak"] / max(entry_count, 1)),
                "entry_unknown_ratio": float(counts["unknown"] / max(entry_count, 1)),
                "entry_pressure_label": entry_label,
                "entry_pressure_reason": entry_reason,
                "stock_ret": None if pd.isna(stock_ret) else float(stock_ret),
                "combo_ret": None if pd.isna(combo_ret) else float(combo_ret),
            }
        )
    daily = pd.DataFrame(daily_rows)
    if not rotation.empty:
        daily = daily.merge(rotation, how="left", on="date")
    else:
        daily["held_stock_count"] = 0
        daily["held_healthy_ratio"] = 0.0
        daily["held_weak_ratio"] = 0.0
        daily["rotation_pressure_label"] = ""
    daily["held_healthy_ratio"] = pd.to_numeric(daily["held_healthy_ratio"], errors="coerce").fillna(0.0)
    daily["held_weak_ratio"] = pd.to_numeric(daily["held_weak_ratio"], errors="coerce").fillna(0.0)

    alignment_labels: list[str] = []
    alignment_reasons: list[str] = []
    for item in daily.itertuples(index=False):
        entry_count = int(getattr(item, "entry_stock_count") or 0)
        entry_healthy = float(getattr(item, "entry_healthy_ratio") or 0.0)
        entry_weak = float(getattr(item, "entry_weak_ratio") or 0.0)
        held_healthy = float(getattr(item, "held_healthy_ratio") or 0.0)
        held_weak = float(getattr(item, "held_weak_ratio") or 0.0)
        if entry_count <= 0:
            label = "no_entry_signal"
            reason = "no buy order; R2 cannot judge entry selection on this date"
        elif entry_weak >= 0.50:
            label = "entry_sorting_risk"
            reason = "buy orders are concentrated in weak industries"
        elif entry_healthy >= 0.50 and held_weak >= 0.30:
            label = "replacement_lag"
            reason = "buy orders are healthy but existing holdings still carry weak-industry exposure"
        elif entry_healthy >= 0.50 and held_healthy >= 0.50:
            label = "entry_held_aligned_healthy"
            reason = "buy orders and holdings are both mostly healthy"
        elif entry_healthy >= 0.50:
            label = "entry_improving"
            reason = "buy orders are healthier than the existing held mix"
        else:
            label = "entry_mixed"
            reason = "buy orders are not clearly healthy or weak"
        alignment_labels.append(label)
        alignment_reasons.append(reason)
    daily["entry_vs_held_alignment_label"] = alignment_labels
    daily["entry_vs_held_alignment_reason"] = alignment_reasons
    return daily, entry_industry_daily


def _entry_candidate_pressure_summary(daily: pd.DataFrame, entry_industry_daily: pd.DataFrame) -> dict[str, Any]:
    if daily.empty:
        return {
            "row_count": 0,
            "first_date": "",
            "last_date": "",
            "latest_entry_pressure": "unknown",
            "label_counts": {},
        }
    labels = daily["entry_pressure_label"].fillna("unknown").astype(str)
    align_labels = daily["entry_vs_held_alignment_label"].fillna("unknown").astype(str)
    latest = daily.iloc[-1]
    work = daily.copy()
    work["stock_ret"] = pd.to_numeric(work["stock_ret"], errors="coerce").fillna(0.0)
    work["combo_ret"] = pd.to_numeric(work["combo_ret"], errors="coerce").fillna(0.0)
    by_alignment: dict[str, dict[str, Any]] = {}
    for label, frame in work.groupby("entry_vs_held_alignment_label"):
        by_alignment[str(label)] = {
            "days": int(len(frame)),
            "entry_days": int((pd.to_numeric(frame["entry_stock_count"], errors="coerce").fillna(0) > 0).sum()),
            "stock_ret_total": float((1.0 + frame["stock_ret"]).prod() - 1.0),
            "combo_ret_total": float((1.0 + frame["combo_ret"]).prod() - 1.0),
            "avg_entry_weak_ratio": float(pd.to_numeric(frame["entry_weak_ratio"], errors="coerce").mean()),
            "avg_entry_healthy_ratio": float(pd.to_numeric(frame["entry_healthy_ratio"], errors="coerce").mean()),
            "avg_held_weak_ratio": float(pd.to_numeric(frame["held_weak_ratio"], errors="coerce").mean()),
            "avg_held_healthy_ratio": float(pd.to_numeric(frame["held_healthy_ratio"], errors="coerce").mean()),
        }
    latest_entries = ""
    if not entry_industry_daily.empty:
        latest_entry = entry_industry_daily.loc[entry_industry_daily["date"].astype(str) == str(latest["date"])].copy()
        latest_entries = "; ".join(
            f"{row.industry_name}:{row.industry_health_label}:{int(row.entry_symbol_count)}"
            for row in latest_entry.sort_values(["industry_health_label", "industry_name"]).itertuples(index=False)
        )
    return sanitize_json(
        {
            "row_count": int(len(daily)),
            "first_date": str(daily["date"].iloc[0]),
            "last_date": str(daily["date"].iloc[-1]),
            "latest_entry_pressure": str(latest["entry_pressure_label"]),
            "latest_entry_reason": str(latest["entry_pressure_reason"]),
            "latest_entry_vs_held_alignment": str(latest["entry_vs_held_alignment_label"]),
            "latest_entry_vs_held_reason": str(latest["entry_vs_held_alignment_reason"]),
            "latest_entry_stock_count": int(latest["entry_stock_count"]),
            "latest_entry_industry_count": int(latest["entry_industry_count"]),
            "latest_entry_healthy_count": int(latest["entry_healthy_count"]),
            "latest_entry_watch_count": int(latest["entry_watch_count"]),
            "latest_entry_weak_count": int(latest["entry_weak_count"]),
            "latest_entry_industries": latest_entries,
            "entry_day_count": int((pd.to_numeric(daily["entry_stock_count"], errors="coerce").fillna(0) > 0).sum()),
            "avg_entry_weak_ratio": float(pd.to_numeric(daily["entry_weak_ratio"], errors="coerce").mean()),
            "avg_entry_healthy_ratio": float(pd.to_numeric(daily["entry_healthy_ratio"], errors="coerce").mean()),
            "label_counts": {str(key): int(value) for key, value in labels.value_counts().to_dict().items()},
            "alignment_label_counts": {str(key): int(value) for key, value in align_labels.value_counts().to_dict().items()},
            "by_alignment": by_alignment,
        }
    )


def _prepare_candidate_signals(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame(columns=["date", "symbol", "selected_flag", "reject_reason", "cash_blocked_flag"])
    out = candidates.copy()
    out["date"] = pd.to_datetime(out.get("date"), errors="coerce").dt.normalize()
    out["symbol"] = out.get("symbol", pd.Series(dtype=str)).astype(str).str.strip().str.lower()
    if "is_candidate" in out.columns:
        text = out["is_candidate"].fillna(False).astype(str).str.lower()
        out = out.loc[text.isin(["true", "1", "yes"]) | out["is_candidate"].eq(True)].copy()
    if "selected_flag" not in out.columns:
        out["selected_flag"] = out.get("selected", False)
    out["selected_flag"] = out["selected_flag"].fillna(False).astype(str).str.lower().isin(["true", "1", "yes"])
    out["reject_reason"] = out.get("reject_reason", pd.Series(dtype=str)).fillna("").astype(str).str.strip().str.upper()
    if "cash_blocked_flag" not in out.columns:
        out["cash_blocked_flag"] = False
    out["cash_blocked_flag"] = (
        out["cash_blocked_flag"].fillna(False).astype(str).str.lower().isin(["true", "1", "yes"])
        | out["reject_reason"].eq("SKIP_NO_CASH")
    )
    for col in ("final_score", "final_score_value", "final_score_rank", "mf_score", "mf_rank", "cash_available", "estimated_amount", "estimated_price", "estimated_qty"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
        else:
            out[col] = None
    out = out.loc[out["date"].notna() & out["symbol"].str.match(r"^(sh|sz)\d{6}$")].copy()
    return out.sort_values(["date", "symbol"]).reset_index(drop=True)


def compute_candidate_pool_pressure_daily(
    *,
    candidates: pd.DataFrame,
    nav: pd.DataFrame,
    industry_history: pd.DataFrame,
    industry_long_daily: pd.DataFrame,
    rotation_daily: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cand = _prepare_candidate_signals(candidates)
    cand = _attach_pit_industry(cand, industry_history)
    if nav.empty or "date" not in nav.columns:
        return pd.DataFrame(), pd.DataFrame()
    nav_frame = nav.copy()
    nav_frame["date"] = pd.to_datetime(nav_frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    nav_frame = nav_frame.loc[nav_frame["date"].notna()].copy()

    health = industry_long_daily.copy()
    if not health.empty:
        health["date"] = pd.to_datetime(health["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        health["industry_index_code"] = health["industry_index_code"].astype(str).str.strip().str.upper()
        health = health[
            [
                "date",
                "industry_index_code",
                "industry_name",
                "industry_health_label",
                "ret20",
                "ret60",
                "drawdown60",
                "trend_score",
            ]
        ].copy()
    else:
        health = pd.DataFrame(columns=["date", "industry_index_code", "industry_name", "industry_health_label", "ret20", "ret60", "drawdown60", "trend_score"])

    if not cand.empty:
        cand["date"] = pd.to_datetime(cand["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        cand["industry_index_code"] = cand["industry_index_code"].astype(str).str.strip().str.upper()
        cand = cand.merge(health, how="left", on=["date", "industry_index_code"], suffixes=("", "_health"))
        cand["industry_health_label"] = cand["industry_health_label"].fillna("unknown")
        cand["industry_name"] = cand["industry_name"].fillna(cand["industry_l1"])

    industry_rows: list[dict[str, Any]] = []
    if not cand.empty:
        for (dt, index_code, industry_name), frame in cand.groupby(["date", "industry_index_code", "industry_name"], dropna=False):
            labels = frame["industry_health_label"].fillna("unknown").astype(str)
            selected = frame.loc[frame["selected_flag"].astype(bool)].copy()
            cash_blocked = frame.loc[frame["cash_blocked_flag"].astype(bool)].copy()
            industry_rows.append(
                {
                    "date": str(dt),
                    "industry_index_code": str(index_code or ""),
                    "industry_name": str(industry_name or ""),
                    "industry_health_label": str(labels.mode().iloc[0]) if not labels.empty else "unknown",
                    "candidate_symbol_count": int(frame["symbol"].nunique()),
                    "selected_symbol_count": int(selected["symbol"].nunique()),
                    "cash_blocked_symbol_count": int(cash_blocked["symbol"].nunique()),
                    "candidate_symbols": ";".join(sorted(frame["symbol"].astype(str).unique())),
                    "selected_symbols": ";".join(sorted(selected["symbol"].astype(str).unique())),
                    "cash_blocked_symbols": ";".join(sorted(cash_blocked["symbol"].astype(str).unique())),
                    "ret20": None if frame["ret20"].isna().all() else float(pd.to_numeric(frame["ret20"], errors="coerce").dropna().iloc[-1]),
                    "ret60": None if frame["ret60"].isna().all() else float(pd.to_numeric(frame["ret60"], errors="coerce").dropna().iloc[-1]),
                }
            )
    candidate_industry_daily = pd.DataFrame(industry_rows).sort_values(["date", "industry_index_code"]).reset_index(drop=True) if industry_rows else pd.DataFrame()

    rotation = rotation_daily.copy()
    if not rotation.empty:
        rotation["date"] = pd.to_datetime(rotation["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        rotation = rotation[
            [
                "date",
                "held_stock_count",
                "held_healthy_ratio",
                "held_weak_ratio",
                "rotation_pressure_label",
            ]
        ].copy()
    else:
        rotation = pd.DataFrame(columns=["date", "held_stock_count", "held_healthy_ratio", "held_weak_ratio", "rotation_pressure_label"])

    by_date = {str(dt): frame for dt, frame in cand.groupby("date")} if not cand.empty else {}
    daily_rows: list[dict[str, Any]] = []
    for row in nav_frame.itertuples(index=False):
        dt = str(getattr(row, "date"))
        frame = by_date.get(dt, pd.DataFrame())
        stock_ret = getattr(row, "stock_ret", None) if hasattr(row, "stock_ret") else None
        combo_ret = getattr(row, "combo_ret", None) if hasattr(row, "combo_ret") else None
        if frame.empty:
            counts = {"healthy": 0, "watch": 0, "weak": 0, "unknown": 0}
            selected_counts = {"healthy": 0, "watch": 0, "weak": 0, "unknown": 0}
            cash_counts = {"healthy": 0, "watch": 0, "weak": 0, "unknown": 0}
            candidate_count = selected_count = cash_count = topk_count = 0
            label = "no_candidate"
            reason = "no stock candidate signal on this date"
        else:
            labels = frame["industry_health_label"].fillna("unknown").astype(str)
            selected_frame = frame.loc[frame["selected_flag"].astype(bool)].copy()
            cash_frame = frame.loc[frame["cash_blocked_flag"].astype(bool)].copy()
            counts = {key: int(labels.eq(key).sum()) for key in ["healthy", "watch", "weak", "unknown"]}
            selected_labels = selected_frame["industry_health_label"].fillna("unknown").astype(str)
            cash_labels = cash_frame["industry_health_label"].fillna("unknown").astype(str)
            selected_counts = {key: int(selected_labels.eq(key).sum()) for key in ["healthy", "watch", "weak", "unknown"]}
            cash_counts = {key: int(cash_labels.eq(key).sum()) for key in ["healthy", "watch", "weak", "unknown"]}
            candidate_count = int(frame["symbol"].nunique())
            selected_count = int(selected_frame["symbol"].nunique())
            cash_count = int(cash_frame["symbol"].nunique())
            topk_count = int(frame["reject_reason"].eq("NOT_IN_TOPK").sum())
            candidate_weak = counts["weak"] / max(candidate_count, 1)
            candidate_healthy = counts["healthy"] / max(candidate_count, 1)
            selected_weak = selected_counts["weak"] / max(selected_count, 1)
            selected_healthy = selected_counts["healthy"] / max(selected_count, 1)
            if candidate_weak >= 0.50:
                label = "candidate_pool_broad_weak"
                reason = "candidate pool is concentrated in weak industries"
            elif selected_count > 0 and selected_weak >= 0.50:
                label = "selected_broad_weak"
                reason = "selected candidates are concentrated in weak industries"
            elif candidate_healthy >= 0.50 and selected_count == 0:
                label = "healthy_pool_not_deployed"
                reason = "candidate pool is healthy but no candidate was selected"
            elif candidate_healthy >= 0.50 and selected_healthy < 0.50:
                label = "selection_health_mismatch"
                reason = "candidate pool is healthy but selected candidates are not mostly healthy"
            elif candidate_healthy >= 0.50:
                label = "candidate_pool_broad_healthy"
                reason = "candidate pool is mostly healthy"
            else:
                label = "candidate_pool_mixed"
                reason = "candidate pool industries are mixed"
        daily_rows.append(
            {
                "date": dt,
                "candidate_stock_count": candidate_count,
                "selected_stock_count": selected_count,
                "cash_blocked_stock_count": cash_count,
                "topk_reject_count": topk_count,
                "candidate_healthy_count": counts["healthy"],
                "candidate_watch_count": counts["watch"],
                "candidate_weak_count": counts["weak"],
                "candidate_unknown_count": counts["unknown"],
                "selected_healthy_count": selected_counts["healthy"],
                "selected_watch_count": selected_counts["watch"],
                "selected_weak_count": selected_counts["weak"],
                "selected_unknown_count": selected_counts["unknown"],
                "cash_blocked_healthy_count": cash_counts["healthy"],
                "cash_blocked_watch_count": cash_counts["watch"],
                "cash_blocked_weak_count": cash_counts["weak"],
                "cash_blocked_unknown_count": cash_counts["unknown"],
                "candidate_healthy_ratio": float(counts["healthy"] / max(candidate_count, 1)),
                "candidate_weak_ratio": float(counts["weak"] / max(candidate_count, 1)),
                "selected_healthy_ratio": float(selected_counts["healthy"] / max(selected_count, 1)),
                "selected_weak_ratio": float(selected_counts["weak"] / max(selected_count, 1)),
                "cash_blocked_healthy_ratio": float(cash_counts["healthy"] / max(cash_count, 1)),
                "cash_blocked_weak_ratio": float(cash_counts["weak"] / max(cash_count, 1)),
                "candidate_pool_pressure_label": label,
                "candidate_pool_pressure_reason": reason,
                "stock_ret": None if pd.isna(stock_ret) else float(stock_ret),
                "combo_ret": None if pd.isna(combo_ret) else float(combo_ret),
            }
        )
    daily = pd.DataFrame(daily_rows)
    if not rotation.empty:
        daily = daily.merge(rotation, how="left", on="date")
    else:
        daily["held_stock_count"] = 0
        daily["held_healthy_ratio"] = 0.0
        daily["held_weak_ratio"] = 0.0
        daily["rotation_pressure_label"] = ""
    daily["held_healthy_ratio"] = pd.to_numeric(daily["held_healthy_ratio"], errors="coerce").fillna(0.0)
    daily["held_weak_ratio"] = pd.to_numeric(daily["held_weak_ratio"], errors="coerce").fillna(0.0)

    diagnosis_labels: list[str] = []
    diagnosis_reasons: list[str] = []
    for item in daily.itertuples(index=False):
        candidate_count = int(getattr(item, "candidate_stock_count") or 0)
        selected_count = int(getattr(item, "selected_stock_count") or 0)
        candidate_healthy = float(getattr(item, "candidate_healthy_ratio") or 0.0)
        candidate_weak = float(getattr(item, "candidate_weak_ratio") or 0.0)
        selected_healthy = float(getattr(item, "selected_healthy_ratio") or 0.0)
        selected_weak = float(getattr(item, "selected_weak_ratio") or 0.0)
        held_weak = float(getattr(item, "held_weak_ratio") or 0.0)
        if candidate_count <= 0:
            label = "no_candidate_signal"
            reason = "no candidate signal; cannot evaluate sorting or replacement"
        elif candidate_weak >= 0.50:
            label = "signal_pool_weak"
            reason = "raw candidate pool is already mostly weak"
        elif selected_count > 0 and selected_weak >= 0.50:
            label = "selection_weak"
            reason = "selected candidates are mostly weak"
        elif candidate_healthy >= 0.50 and selected_count == 0 and held_weak >= 0.30:
            label = "deployment_blocked_with_weak_holdings"
            reason = "healthy candidates exist but are not deployed while holdings remain weak"
        elif candidate_healthy >= 0.50 and selected_healthy >= 0.50 and held_weak >= 0.30:
            label = "replacement_lag_with_healthy_candidates"
            reason = "healthy candidates are selected but existing holdings still carry weak exposure"
        elif candidate_healthy >= 0.50 and selected_healthy >= 0.50:
            label = "candidate_selected_aligned_healthy"
            reason = "candidate pool and selected candidates are both mostly healthy"
        elif candidate_healthy >= 0.50:
            label = "selection_health_mismatch"
            reason = "candidate pool is healthy but selected candidates are not"
        else:
            label = "candidate_mixed"
            reason = "candidate pool is mixed"
        diagnosis_labels.append(label)
        diagnosis_reasons.append(reason)
    daily["candidate_vs_held_diagnosis_label"] = diagnosis_labels
    daily["candidate_vs_held_diagnosis_reason"] = diagnosis_reasons
    return daily, candidate_industry_daily


def _candidate_pool_pressure_summary(daily: pd.DataFrame, candidate_industry_daily: pd.DataFrame) -> dict[str, Any]:
    if daily.empty:
        return {
            "row_count": 0,
            "first_date": "",
            "last_date": "",
            "latest_candidate_pool_pressure": "unknown",
            "label_counts": {},
        }
    labels = daily["candidate_pool_pressure_label"].fillna("unknown").astype(str)
    diagnosis_labels = daily["candidate_vs_held_diagnosis_label"].fillna("unknown").astype(str)
    latest = daily.iloc[-1]
    work = daily.copy()
    work["stock_ret"] = pd.to_numeric(work["stock_ret"], errors="coerce").fillna(0.0)
    work["combo_ret"] = pd.to_numeric(work["combo_ret"], errors="coerce").fillna(0.0)
    by_diagnosis: dict[str, dict[str, Any]] = {}
    for label, frame in work.groupby("candidate_vs_held_diagnosis_label"):
        by_diagnosis[str(label)] = {
            "days": int(len(frame)),
            "candidate_days": int((pd.to_numeric(frame["candidate_stock_count"], errors="coerce").fillna(0) > 0).sum()),
            "stock_ret_total": float((1.0 + frame["stock_ret"]).prod() - 1.0),
            "combo_ret_total": float((1.0 + frame["combo_ret"]).prod() - 1.0),
            "avg_candidate_weak_ratio": float(pd.to_numeric(frame["candidate_weak_ratio"], errors="coerce").mean()),
            "avg_candidate_healthy_ratio": float(pd.to_numeric(frame["candidate_healthy_ratio"], errors="coerce").mean()),
            "avg_selected_weak_ratio": float(pd.to_numeric(frame["selected_weak_ratio"], errors="coerce").mean()),
            "avg_selected_healthy_ratio": float(pd.to_numeric(frame["selected_healthy_ratio"], errors="coerce").mean()),
            "avg_held_weak_ratio": float(pd.to_numeric(frame["held_weak_ratio"], errors="coerce").mean()),
            "avg_held_healthy_ratio": float(pd.to_numeric(frame["held_healthy_ratio"], errors="coerce").mean()),
        }
    latest_candidates = ""
    if not candidate_industry_daily.empty:
        latest_frame = candidate_industry_daily.loc[candidate_industry_daily["date"].astype(str) == str(latest["date"])].copy()
        latest_candidates = "; ".join(
            f"{row.industry_name}:{row.industry_health_label}:cand{int(row.candidate_symbol_count)}/sel{int(row.selected_symbol_count)}/cash{int(row.cash_blocked_symbol_count)}"
            for row in latest_frame.sort_values(["industry_health_label", "industry_name"]).itertuples(index=False)
        )
    return sanitize_json(
        {
            "row_count": int(len(daily)),
            "first_date": str(daily["date"].iloc[0]),
            "last_date": str(daily["date"].iloc[-1]),
            "latest_candidate_pool_pressure": str(latest["candidate_pool_pressure_label"]),
            "latest_candidate_pool_reason": str(latest["candidate_pool_pressure_reason"]),
            "latest_candidate_vs_held_diagnosis": str(latest["candidate_vs_held_diagnosis_label"]),
            "latest_candidate_vs_held_reason": str(latest["candidate_vs_held_diagnosis_reason"]),
            "latest_candidate_stock_count": int(latest["candidate_stock_count"]),
            "latest_selected_stock_count": int(latest["selected_stock_count"]),
            "latest_cash_blocked_stock_count": int(latest["cash_blocked_stock_count"]),
            "latest_topk_reject_count": int(latest["topk_reject_count"]),
            "latest_candidate_industries": latest_candidates,
            "candidate_day_count": int((pd.to_numeric(daily["candidate_stock_count"], errors="coerce").fillna(0) > 0).sum()),
            "selected_day_count": int((pd.to_numeric(daily["selected_stock_count"], errors="coerce").fillna(0) > 0).sum()),
            "avg_candidate_weak_ratio": float(pd.to_numeric(daily["candidate_weak_ratio"], errors="coerce").mean()),
            "avg_candidate_healthy_ratio": float(pd.to_numeric(daily["candidate_healthy_ratio"], errors="coerce").mean()),
            "avg_selected_weak_ratio": float(pd.to_numeric(daily["selected_weak_ratio"], errors="coerce").mean()),
            "avg_selected_healthy_ratio": float(pd.to_numeric(daily["selected_healthy_ratio"], errors="coerce").mean()),
            "label_counts": {str(key): int(value) for key, value in labels.value_counts().to_dict().items()},
            "diagnosis_label_counts": {str(key): int(value) for key, value in diagnosis_labels.value_counts().to_dict().items()},
            "by_diagnosis": by_diagnosis,
        }
    )


def _industry_summary(daily: pd.DataFrame, long_daily: pd.DataFrame, specs: dict[str, dict[str, str]]) -> dict[str, Any]:
    if daily.empty:
        return {
            "row_count": 0,
            "first_date": "",
            "last_date": "",
            "latest_industry_market_health": "unknown",
            "mature_coverage_ratio": 0.0,
            "label_counts": {},
            "industry_count": len(specs),
        }
    labels = daily["industry_market_health_label"].fillna("unknown").astype(str)
    latest = daily.iloc[-1]
    top_weak = ""
    top_healthy = ""
    if not long_daily.empty:
        latest_long = long_daily.loc[long_daily["date"].astype(str) == str(latest["date"])].copy()
        latest_long["ret20_num"] = pd.to_numeric(latest_long["ret20"], errors="coerce")
        top_weak = "; ".join(
            f"{row.industry_name}:{float(row.ret20_num):.2%}"
            for row in latest_long.sort_values("ret20_num").head(8).itertuples(index=False)
            if pd.notna(row.ret20_num)
        )
        top_healthy = "; ".join(
            f"{row.industry_name}:{float(row.ret20_num):.2%}"
            for row in latest_long.sort_values("ret20_num", ascending=False).head(8).itertuples(index=False)
            if pd.notna(row.ret20_num)
        )
    return sanitize_json(
        {
            "row_count": int(len(daily)),
            "first_date": str(daily["date"].iloc[0]),
            "last_date": str(daily["date"].iloc[-1]),
            "latest_industry_market_health": str(latest["industry_market_health_label"]),
            "latest_reason": str(latest["industry_market_health_reason"]),
            "latest_healthy_industry_count": int(latest["healthy_industry_count"]),
            "latest_watch_industry_count": int(latest["watch_industry_count"]),
            "latest_weak_industry_count": int(latest["weak_industry_count"]),
            "latest_top_healthy_industries": top_healthy,
            "latest_top_weak_industries": top_weak,
            "mature_coverage_ratio": float(pd.to_numeric(daily["mature_coverage_ratio"], errors="coerce").mean()),
            "avg_healthy_breadth": float(pd.to_numeric(daily["industry_breadth_healthy"], errors="coerce").mean()),
            "avg_weak_breadth": float(pd.to_numeric(daily["industry_breadth_weak"], errors="coerce").mean()),
            "label_counts": {str(key): int(value) for key, value in labels.value_counts().to_dict().items()},
            "industry_count": len(specs),
        }
    )


def _window_summary(daily: pd.DataFrame, specs: dict[str, dict[str, str]]) -> dict[str, Any]:
    if daily.empty:
        return {
            "row_count": 0,
            "first_date": "",
            "last_date": "",
            "latest_style_state": "unknown",
            "coverage_ratio": 0.0,
            "mature_coverage_ratio": 0.0,
            "transition_count": 0,
            "label_counts": {},
            "index_symbols": {key: spec["symbol"] for key, spec in specs.items()},
        }
    labels = daily["style_state_label"].fillna("unknown").astype(str)
    transitions = int(labels.ne(labels.shift()).sum() - 1) if len(labels) > 1 else 0
    return sanitize_json(
        {
            "row_count": int(len(daily)),
            "first_date": str(daily["date"].iloc[0]),
            "last_date": str(daily["date"].iloc[-1]),
            "latest_style_state": str(labels.iloc[-1]),
            "latest_reason": str(daily["style_state_reason"].iloc[-1]),
            "coverage_ratio": float(pd.to_numeric(daily["coverage_ratio"], errors="coerce").mean()),
            "mature_coverage_ratio": float(pd.to_numeric(daily["mature_coverage_ratio"], errors="coerce").mean()),
            "transition_count": max(transitions, 0),
            "label_counts": {str(key): int(value) for key, value in labels.value_counts().to_dict().items()},
            "index_symbols": {key: spec["symbol"] for key, spec in specs.items()},
        }
    )


def _derive_verdict(summary: dict[str, Any], source_audit: dict[str, Any], thresholds: dict[str, float]) -> dict[str, Any]:
    if source_audit.get("missing_source"):
        return {
            "status": "inconclusive",
            "reason": str(source_audit.get("reason") or "style index source is missing"),
            "gate_status": "UNKNOWN",
            "verdict_source": "style_industry_state_switch_shadow_runner",
        }
    if int(summary.get("row_count") or 0) == 0:
        return {
            "status": "inconclusive",
            "reason": "no style-index rows in this window",
            "gate_status": "UNKNOWN",
            "verdict_source": "style_industry_state_switch_shadow_runner",
        }
    coverage = float(summary.get("mature_coverage_ratio") or 0.0)
    if coverage < float(thresholds["min_coverage_ratio"]):
        return {
            "status": "inconclusive",
            "reason": f"mature style-index coverage is only {coverage:.2%}; diagnostic is not reliable enough",
            "gate_status": "UNKNOWN",
            "verdict_source": "style_industry_state_switch_shadow_runner",
        }
    return {
        "status": "confirmed",
        "reason": "M1 style-state daily surface generated with sufficient index coverage; diagnostic only, not a baseline upgrade",
        "gate_status": "UNKNOWN",
        "verdict_source": "style_industry_state_switch_shadow_runner",
    }


def _write_human_report(
    *,
    path: Path,
    study: StudyDefinition,
    item: dict[str, Any],
    summary: dict[str, Any],
    verdict: dict[str, Any],
    source_audit: dict[str, Any],
    industry_source_audit: dict[str, Any] | None,
    thresholds: dict[str, float],
    daily: pd.DataFrame,
    industry_daily: pd.DataFrame | None = None,
    industry_summary: dict[str, Any] | None = None,
    rotation_summary: dict[str, Any] | None = None,
    entry_summary: dict[str, Any] | None = None,
    candidate_summary: dict[str, Any] | None = None,
    candidate_signals_source_audit: dict[str, Any] | None = None,
) -> None:
    label_counts = summary.get("label_counts") if isinstance(summary.get("label_counts"), dict) else {}
    industry_summary = industry_summary if isinstance(industry_summary, dict) else {}
    rotation_summary = rotation_summary if isinstance(rotation_summary, dict) else {}
    entry_summary = entry_summary if isinstance(entry_summary, dict) else {}
    candidate_summary = candidate_summary if isinstance(candidate_summary, dict) else {}
    candidate_signals_source_audit = candidate_signals_source_audit if isinstance(candidate_signals_source_audit, dict) else {}
    industry_source_audit = industry_source_audit if isinstance(industry_source_audit, dict) else {}
    recent = daily.tail(12) if not daily.empty else pd.DataFrame()
    lines = [
        f"# {study.title}",
        "",
        "## Conclusion",
        "",
        f"- verdict: {verdict.get('status')}",
        f"- reason: {verdict.get('reason')}",
        "- scope: research-only M1/I1 state shadow; no trades, no NAV recomputation, no baseline change.",
        "- implemented layers: M1 style_state, I1 industry_health, R1 rotation_pressure, R2 entry_candidate_alignment, R3 candidate_pool_alignment",
        "- pending layers: none",
        "",
        "## Window",
        "",
        f"- window: {item.get('window_key')} ({item.get('request_payload', {}).get('start_date')} to {item.get('request_payload', {}).get('end_date')})",
        f"- latest style state: {summary.get('latest_style_state')}",
        f"- latest reason: {summary.get('latest_reason')}",
        f"- rows: {summary.get('row_count')}",
        f"- transitions: {summary.get('transition_count')}",
        f"- mature coverage ratio: {summary.get('mature_coverage_ratio')}",
        f"- label counts: {json.dumps(label_counts, ensure_ascii=False)}",
        f"- latest industry health: {industry_summary.get('latest_industry_market_health') or ''}",
        f"- latest industry reason: {industry_summary.get('latest_reason') or ''}",
        f"- latest industry healthy/watch/weak: {industry_summary.get('latest_healthy_industry_count')}/{industry_summary.get('latest_watch_industry_count')}/{industry_summary.get('latest_weak_industry_count')}",
        f"- latest top healthy industries: {industry_summary.get('latest_top_healthy_industries') or ''}",
        f"- latest top weak industries: {industry_summary.get('latest_top_weak_industries') or ''}",
        f"- latest held-industry pressure: {rotation_summary.get('latest_rotation_pressure') or ''}",
        f"- latest held healthy/watch/weak: {rotation_summary.get('latest_held_healthy_count')}/{rotation_summary.get('latest_held_watch_count')}/{rotation_summary.get('latest_held_weak_count')}",
        f"- latest held industries: {rotation_summary.get('latest_held_industries') or ''}",
        f"- latest entry pressure: {entry_summary.get('latest_entry_pressure') or ''}",
        f"- latest entry-vs-held alignment: {entry_summary.get('latest_entry_vs_held_alignment') or ''}",
        f"- latest entry industries: {entry_summary.get('latest_entry_industries') or ''}",
        f"- latest candidate-pool pressure: {candidate_summary.get('latest_candidate_pool_pressure') or ''}",
        f"- latest candidate-vs-held diagnosis: {candidate_summary.get('latest_candidate_vs_held_diagnosis') or ''}",
        f"- latest candidate industries: {candidate_summary.get('latest_candidate_industries') or ''}",
        f"- candidate signal source scope: {candidate_signals_source_audit.get('source_scope') or ''}",
        f"- candidate signal selected/rejected rows: {candidate_signals_source_audit.get('selected_row_count')}/{candidate_signals_source_audit.get('row_count')}",
        "",
        "## Recent Daily States",
        "",
        "| date | label | reason | hs300 ret20 | zz500 ret20 | csi1000 ret20 |",
        "|---|---|---|---:|---:|---:|",
    ]
    if not recent.empty:
        for row in recent.itertuples(index=False):
            lines.append(
                "| {date} | {label} | {reason} | {hs} | {zz} | {c1} |".format(
                    date=getattr(row, "date", ""),
                    label=getattr(row, "style_state_label", ""),
                    reason=getattr(row, "style_state_reason", ""),
                    hs=getattr(row, "hs300_ret20", ""),
                    zz=getattr(row, "zz500_ret20", ""),
                    c1=getattr(row, "csi1000_ret20", ""),
                )
            )
    lines.extend(
        [
            "",
            "## Thresholds",
            "",
            "```json",
            json.dumps(thresholds, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Source Lineage",
            "",
            f"- source kind: {source_audit.get('source_kind')}",
            f"- source path: {source_audit.get('source_path') or ''}",
            f"- missing source: {source_audit.get('missing_source')}",
            f"- missing index symbols: {json.dumps(source_audit.get('missing_index_symbols') or [], ensure_ascii=False)}",
            f"- index symbols: {json.dumps(summary.get('index_symbols'), ensure_ascii=False)}",
            f"- industry source kind: {industry_source_audit.get('source_kind') or ''}",
            f"- industry missing source: {industry_source_audit.get('missing_source')}",
            f"- industry missing index symbols: {json.dumps(industry_source_audit.get('missing_index_symbols') or [], ensure_ascii=False)}",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_matrix_summary(study: StudyDefinition, runs: list[dict[str, Any]]) -> dict[str, str]:
    root = _study_root(study)
    machine_dir = root / "machine"
    human_dir = root / "human"
    machine_dir.mkdir(parents=True, exist_ok=True)
    human_dir.mkdir(parents=True, exist_ok=True)
    machine_path = machine_dir / "style_state_shadow_matrix.json"
    human_path = human_dir / "style_state_shadow_matrix.md"
    machine_path.write_text(
        json.dumps(sanitize_json({"study_id": study.study_id, "runs": runs}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        f"# {study.title}",
        "",
        "| window | variant | verdict | rows | latest state | transitions | coverage |",
        "|---|---|---|---:|---|---:|---:|",
    ]
    for row in runs:
        summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
        verdict = row.get("verdict") if isinstance(row.get("verdict"), dict) else {}
        lines.append(
            "| {window} | {variant} | {verdict} | {rows} | {state} | {transitions} | {coverage} |".format(
                window=row.get("window_key") or "",
                variant=row.get("variant_name") or "",
                verdict=verdict.get("status") or "",
                rows=summary.get("row_count"),
                state=summary.get("latest_style_state"),
                transitions=summary.get("transition_count"),
                coverage=summary.get("mature_coverage_ratio"),
            )
        )
    human_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"machine_summary": str(machine_path), "human_summary": str(human_path)}


def _load_source_frame(
    *,
    runner_params: dict[str, Any],
    specs: dict[str, dict[str, str]],
    start: str,
    end: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    csv_path_text = str(runner_params.get("style_index_history_csv") or "").strip()
    if csv_path_text:
        csv_path = _resolve_repo_path(csv_path_text)
        if not csv_path.exists():
            return pd.DataFrame(), {
                "source_kind": "csv",
                "source_path": str(csv_path),
                "missing_source": True,
                "reason": f"style_index_history_csv not found: {csv_path}",
            }
        return _load_index_history_from_csv(csv_path), {
            "source_kind": "csv",
            "source_path": str(csv_path),
            "missing_source": False,
        }
    try:
        frame, missing = _load_index_history_from_runtime(specs=specs, start=start, end=end)
    except Exception as exc:
        return pd.DataFrame(), {
            "source_kind": "runtime_provider",
            "source_path": "pit_index_daily via load_benchmark_series_frame",
            "missing_source": True,
            "reason": f"runtime style-index load failed: {exc}",
        }
    missing_source = frame.empty
    return frame, {
        "source_kind": "runtime_provider",
        "source_path": "pit_index_daily via load_benchmark_series_frame",
        "missing_source": missing_source,
        "missing_index_symbols": missing,
        "reason": "runtime provider returned no style-index rows" if missing_source else "",
    }


def run_style_industry_state_switch_shadow_study(
    *,
    study: StudyDefinition,
    plan: list[dict[str, Any]],
    write_dual_output: bool = True,
    append_to_baseline: bool = False,
) -> dict[str, Any]:
    del append_to_baseline
    runs: list[dict[str, Any]] = []
    for item in plan:
        request_payload = dict(item.get("request_payload") or {})
        runner_params = request_payload.get("runner_params") if isinstance(request_payload.get("runner_params"), dict) else {}
        specs = _style_specs(runner_params)
        thresholds = _thresholds(runner_params)
        window_key = str(item.get("window_key") or "")
        variant_name = str(item.get("variant_name") or "")
        start = str(request_payload.get("start_date") or "")
        end = str(request_payload.get("end_date") or "")
        item_dir = _study_item_dir(study, window_key=window_key, variant_name=variant_name)
        machine_dir = item_dir / "machine"
        human_dir = item_dir / "human"
        machine_dir.mkdir(parents=True, exist_ok=True)
        human_dir.mkdir(parents=True, exist_ok=True)

        source_frame, source_audit = _load_source_frame(
            runner_params=runner_params,
            specs=specs,
            start=start,
            end=end,
        )
        window_frame = _date_filtered(source_frame, start=start, end=end)
        daily = compute_style_state_daily(window_frame, thresholds, specs=specs)
        summary = _window_summary(daily, specs)
        verdict = _derive_verdict(summary, source_audit, thresholds)
        industry_specs = _industry_specs()
        industry_source_frame, industry_source_audit = _load_industry_source_frame(
            runner_params=runner_params,
            start=start,
            end=end,
        )
        industry_window_frame = _date_filtered(industry_source_frame, start=start, end=end)
        industry_daily, industry_long_daily = compute_industry_health_daily(
            industry_window_frame,
            thresholds,
            specs=industry_specs,
        )
        industry_summary = _industry_summary(industry_daily, industry_long_daily, industry_specs)
        baseline_root = _baseline_artifact_root(runner_params, study.baseline_id)
        nav_frame = _load_csv_if_exists(baseline_root / "nav.csv")
        trades_frame = _load_csv_if_exists(baseline_root / "portfolio_trades.csv")
        orders_frame = _load_csv_if_exists(baseline_root / "orders.csv")
        stock_trades = _prepare_stock_trades(trades_frame)
        stock_symbols = sorted(stock_trades["symbol"].dropna().astype(str).unique().tolist()) if not stock_trades.empty else []
        stock_industry_history, stock_industry_source_audit = _load_stock_industry_history_from_runtime(
            symbols=stock_symbols,
            start=start,
            end=end,
        )
        r1_daily, r1_held_industry_daily = compute_rotation_pressure_daily(
            trades=stock_trades,
            nav=_date_filtered(nav_frame, start=start, end=end),
            industry_history=stock_industry_history,
            industry_long_daily=industry_long_daily,
        )
        r1_summary = _rotation_pressure_summary(r1_daily, r1_held_industry_daily)
        stock_orders = _prepare_stock_trades(orders_frame)
        r2_daily, r2_entry_industry_daily = compute_entry_candidate_pressure_daily(
            orders=stock_orders,
            nav=_date_filtered(nav_frame, start=start, end=end),
            industry_history=stock_industry_history,
            industry_long_daily=industry_long_daily,
            rotation_daily=r1_daily,
        )
        r2_summary = _entry_candidate_pressure_summary(r2_daily, r2_entry_industry_daily)
        entry_candidate_source_audit = {
            "source_kind": "baseline_orders_buy_proxy",
            "source_path": str(baseline_root / "orders.csv"),
            "missing_source": orders_frame.empty,
            "reason": "orders.csv missing; R2 entry proxy unavailable" if orders_frame.empty else "",
            "order_rows": int(len(orders_frame)),
            "stock_buy_order_rows": int(len(stock_orders.loc[stock_orders["side"].eq("BUY")])) if not stock_orders.empty else 0,
            "limitation": "uses filled stock BUY orders as entry-candidate proxy; full rejected/unfilled candidate pool is not available in the V4 baseline artifact",
        }
        candidate_signals_frame, candidate_signals_source_audit = _load_candidate_signals_source(
            runner_params=runner_params,
            baseline_root=baseline_root,
            orders_frame=orders_frame,
        )
        r3_daily, r3_candidate_industry_daily = compute_candidate_pool_pressure_daily(
            candidates=candidate_signals_frame,
            nav=_date_filtered(nav_frame, start=start, end=end),
            industry_history=stock_industry_history,
            industry_long_daily=industry_long_daily,
            rotation_daily=r1_daily,
        )
        r3_summary = _candidate_pool_pressure_summary(r3_daily, r3_candidate_industry_daily)

        daily_path = machine_dir / "style_state_daily.csv"
        industry_daily_path = machine_dir / "industry_health_daily.csv"
        industry_long_path = machine_dir / "industry_health_by_industry_daily.csv"
        r1_daily_path = machine_dir / "rotation_pressure_daily.csv"
        r1_held_industry_path = machine_dir / "rotation_pressure_held_industry_daily.csv"
        r2_daily_path = machine_dir / "entry_candidate_pressure_daily.csv"
        r2_entry_industry_path = machine_dir / "entry_candidate_industry_daily.csv"
        r3_daily_path = machine_dir / "candidate_pool_pressure_daily.csv"
        r3_candidate_industry_path = machine_dir / "candidate_pool_industry_daily.csv"
        source_path = machine_dir / "source_audit.json"
        industry_source_path = machine_dir / "industry_source_audit.json"
        stock_industry_source_path = machine_dir / "stock_industry_source_audit.json"
        entry_candidate_source_path = machine_dir / "entry_candidate_source_audit.json"
        candidate_signals_source_path = machine_dir / "candidate_signals_source_audit.json"
        window_summary_path = machine_dir / "style_state_window_summary.json"
        industry_summary_path = machine_dir / "industry_health_window_summary.json"
        r1_summary_path = machine_dir / "rotation_pressure_window_summary.json"
        r2_summary_path = machine_dir / "entry_candidate_pressure_window_summary.json"
        r3_summary_path = machine_dir / "candidate_pool_pressure_window_summary.json"
        daily.to_csv(daily_path, index=False, encoding="utf-8-sig")
        industry_daily.to_csv(industry_daily_path, index=False, encoding="utf-8-sig")
        industry_long_daily.to_csv(industry_long_path, index=False, encoding="utf-8-sig")
        r1_daily.to_csv(r1_daily_path, index=False, encoding="utf-8-sig")
        r1_held_industry_daily.to_csv(r1_held_industry_path, index=False, encoding="utf-8-sig")
        r2_daily.to_csv(r2_daily_path, index=False, encoding="utf-8-sig")
        r2_entry_industry_daily.to_csv(r2_entry_industry_path, index=False, encoding="utf-8-sig")
        r3_daily.to_csv(r3_daily_path, index=False, encoding="utf-8-sig")
        r3_candidate_industry_daily.to_csv(r3_candidate_industry_path, index=False, encoding="utf-8-sig")
        source_path.write_text(json.dumps(sanitize_json(source_audit), ensure_ascii=False, indent=2), encoding="utf-8")
        industry_source_path.write_text(json.dumps(sanitize_json(industry_source_audit), ensure_ascii=False, indent=2), encoding="utf-8")
        stock_industry_source_path.write_text(json.dumps(sanitize_json(stock_industry_source_audit), ensure_ascii=False, indent=2), encoding="utf-8")
        entry_candidate_source_path.write_text(json.dumps(sanitize_json(entry_candidate_source_audit), ensure_ascii=False, indent=2), encoding="utf-8")
        candidate_signals_source_path.write_text(json.dumps(sanitize_json(candidate_signals_source_audit), ensure_ascii=False, indent=2), encoding="utf-8")
        window_summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        industry_summary_path.write_text(json.dumps(industry_summary, ensure_ascii=False, indent=2), encoding="utf-8")
        r1_summary_path.write_text(json.dumps(r1_summary, ensure_ascii=False, indent=2), encoding="utf-8")
        r2_summary_path.write_text(json.dumps(r2_summary, ensure_ascii=False, indent=2), encoding="utf-8")
        r3_summary_path.write_text(json.dumps(r3_summary, ensure_ascii=False, indent=2), encoding="utf-8")

        machine_payload = sanitize_json(
            {
                "study_id": study.study_id,
                "title": study.title,
                "window_key": window_key,
                "variant_name": variant_name,
                "generated_at": datetime.now().isoformat(),
                "research_only": True,
                "not_nav_backtest": True,
                "baseline_id": study.baseline_id,
                "implemented_layers": ["M1_STYLE_STATE", "I1_INDUSTRY_HEALTH", "R1_ROTATION_PRESSURE", "R2_ENTRY_CANDIDATE_ALIGNMENT", "R3_CANDIDATE_POOL_ALIGNMENT"],
                "pending_layers": [],
                "thresholds": thresholds,
                "summary": summary,
                "industry_summary": industry_summary,
                "rotation_pressure_summary": r1_summary,
                "entry_candidate_pressure_summary": r2_summary,
                "candidate_pool_pressure_summary": r3_summary,
                "source_audit": source_audit,
                "industry_source_audit": industry_source_audit,
                "stock_industry_source_audit": stock_industry_source_audit,
                "entry_candidate_source_audit": entry_candidate_source_audit,
                "candidate_signals_source_audit": candidate_signals_source_audit,
                "baseline_artifact_root": str(baseline_root),
                "verdict": verdict,
            }
        )
        summary_path = machine_dir / "summary.json"
        summary_path.write_text(json.dumps(machine_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        human_path = human_dir / "summary.md"
        if write_dual_output:
            _write_human_report(
                path=human_path,
                study=study,
                item=item,
                summary=summary,
                verdict=verdict,
                source_audit=source_audit,
                industry_source_audit=industry_source_audit,
                thresholds=thresholds,
                daily=daily,
                industry_daily=industry_daily,
                industry_summary=industry_summary,
                rotation_summary=r1_summary,
                entry_summary=r2_summary,
                candidate_summary=r3_summary,
                candidate_signals_source_audit=candidate_signals_source_audit,
            )

        runs.append(
            sanitize_json(
                {
                    "study_id": study.study_id,
                    "window_key": window_key,
                    "window_role": str(item.get("window_role") or ""),
                    "variant_name": variant_name,
                    "exp_id": "",
                    "results_dir": str(item_dir),
                    "research_only": True,
                    "not_nav_backtest": True,
                    "baseline_outputs": {},
                    "implemented_layers": ["M1_STYLE_STATE", "I1_INDUSTRY_HEALTH", "R1_ROTATION_PRESSURE", "R2_ENTRY_CANDIDATE_ALIGNMENT", "R3_CANDIDATE_POOL_ALIGNMENT"],
                    "pending_layers": [],
                    "summary": summary,
                    "industry_summary": industry_summary,
                    "rotation_pressure_summary": r1_summary,
                    "entry_candidate_pressure_summary": r2_summary,
                    "candidate_pool_pressure_summary": r3_summary,
                    "source_audit": source_audit,
                    "industry_source_audit": industry_source_audit,
                    "stock_industry_source_audit": stock_industry_source_audit,
                    "entry_candidate_source_audit": entry_candidate_source_audit,
                    "candidate_signals_source_audit": candidate_signals_source_audit,
                    "thresholds": thresholds,
                    "verdict": verdict,
                    "machine_outputs": {
                        "summary": str(summary_path),
                        "daily": str(daily_path),
                        "industry_daily": str(industry_daily_path),
                        "industry_long_daily": str(industry_long_path),
                        "rotation_pressure_daily": str(r1_daily_path),
                        "rotation_pressure_held_industry_daily": str(r1_held_industry_path),
                        "entry_candidate_pressure_daily": str(r2_daily_path),
                        "entry_candidate_industry_daily": str(r2_entry_industry_path),
                        "candidate_pool_pressure_daily": str(r3_daily_path),
                        "candidate_pool_industry_daily": str(r3_candidate_industry_path),
                        "source_audit": str(source_path),
                        "industry_source_audit": str(industry_source_path),
                        "stock_industry_source_audit": str(stock_industry_source_path),
                        "entry_candidate_source_audit": str(entry_candidate_source_path),
                        "candidate_signals_source_audit": str(candidate_signals_source_path),
                        "window_summary": str(window_summary_path),
                        "industry_window_summary": str(industry_summary_path),
                        "rotation_pressure_window_summary": str(r1_summary_path),
                        "entry_candidate_pressure_window_summary": str(r2_summary_path),
                        "candidate_pool_pressure_window_summary": str(r3_summary_path),
                    },
                    "human_outputs": {"summary": str(human_path)} if write_dual_output else {},
                }
            )
        )
    summary_refs = _write_matrix_summary(study, runs)
    return sanitize_json(
        {
            "study_id": study.study_id,
            "status": "OK",
            "research_only": True,
            "not_nav_backtest": True,
            "implemented_layers": ["M1_STYLE_STATE", "I1_INDUSTRY_HEALTH", "R1_ROTATION_PRESSURE", "R2_ENTRY_CANDIDATE_ALIGNMENT", "R3_CANDIDATE_POOL_ALIGNMENT"],
            "pending_layers": [],
            "runs": runs,
            "summary_outputs": summary_refs,
        }
    )
