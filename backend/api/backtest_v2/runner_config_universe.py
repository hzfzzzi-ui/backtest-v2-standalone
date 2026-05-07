"""Universe/base-domain runtime config compilation helpers."""

from __future__ import annotations

from typing import Any


def apply_universe_runtime_cfg(
    cfg: dict[str, Any],
    body: Any,
    wb_cfg: dict[str, Any],
    *,
    use_body_universe_fields: bool = True,
) -> None:
    if wb_cfg.get("initial_capital") is not None:
        try:
            cfg["initial_capital"] = float(wb_cfg.get("initial_capital"))
        except Exception:
            pass

    universe = cfg.setdefault("universe", {})
    wb_universe = wb_cfg.get("universe") if isinstance(wb_cfg.get("universe"), dict) else {}
    wb_filters = wb_universe.get("filters") if isinstance(wb_universe.get("filters"), dict) else {}
    asset_context = cfg.get("asset_context") if isinstance(cfg.get("asset_context"), dict) else {}
    asset_scope = str(
        wb_cfg.get("asset_scope")
        or cfg.get("asset_scope")
        or asset_context.get("asset_scope")
        or ""
    ).strip().lower()
    benchmark_written = False
    if "start" in wb_universe and wb_universe.get("start") is not None:
        universe["start"] = str(wb_universe.get("start"))
    if "end" in wb_universe and wb_universe.get("end") is not None:
        universe["end"] = str(wb_universe.get("end"))
    if "benchmark" in wb_universe and wb_universe.get("benchmark") is not None:
        universe["benchmark"] = str(wb_universe.get("benchmark"))
        benchmark_written = True
    if "price_adj" in wb_universe and wb_universe.get("price_adj") is not None:
        universe["price_adj"] = str(wb_universe.get("price_adj"))
    if isinstance(wb_universe.get("symbols"), list):
        universe["symbols"] = list(wb_universe.get("symbols") or [])
    if wb_universe.get("membership_mode") is not None:
        universe["membership_mode"] = str(wb_universe.get("membership_mode"))
    if wb_universe.get("allow_low_fidelity_history") is not None:
        universe["allow_low_fidelity_history"] = bool(wb_universe.get("allow_low_fidelity_history"))
    if use_body_universe_fields:
        if getattr(body, "start_date", None) is not None:
            universe["start"] = str(getattr(body, "start_date"))
        if getattr(body, "end_date", None) is not None:
            universe["end"] = str(getattr(body, "end_date"))
        if getattr(body, "benchmark", None) is not None:
            universe["benchmark"] = str(getattr(body, "benchmark"))
            benchmark_written = True
        if getattr(body, "price_adj", None) is not None:
            universe["price_adj"] = str(getattr(body, "price_adj"))
        if getattr(body, "symbols", None):
            universe["symbols"] = list(getattr(body, "symbols"))
    if asset_scope == "cn_etf" and not benchmark_written:
        # ETF research entry must not silently inherit the stock baseline benchmark.
        universe["benchmark"] = ""
    if wb_filters:
        filters = {
            "exclude_st": bool(wb_filters.get("exclude_st", True)),
            "exclude_delisted": bool(wb_filters.get("exclude_delisted", True)),
            "exclude_suspended": bool(wb_filters.get("exclude_suspended", True)),
            "min_list_days": int(wb_filters.get("min_list_days", 120)),
            "min_avg_turnover_20d": float(wb_filters.get("min_avg_turnover_20d", 1e8)),
            "min_avg_turnover_rate_20d": float(wb_filters.get("min_avg_turnover_rate_20d", 0.0) or 0.0),
            "turnover_rate_field": str(wb_filters.get("turnover_rate_field", "turnover_rate_f") or "turnover_rate_f"),
            "price_min": float(wb_filters.get("price_min", 0.0)),
            "price_max": float(wb_filters.get("price_max", 99999.0)),
            "atr_pct_range": str(wb_filters.get("atr_pct_range", "0,100")),
            "limit_rule": str(wb_filters.get("limit_rule", "ignore")),
        }
        if "exclude_star_market" in wb_filters:
            filters["exclude_star_market"] = bool(wb_filters.get("exclude_star_market"))
        universe["filters"] = filters
