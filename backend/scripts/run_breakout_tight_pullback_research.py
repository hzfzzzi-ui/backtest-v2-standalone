from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.scripts.run_breakout_multi_alpha_research import (  # noqa: E402
    BASE_CFG_PATH,
    BASE_EXP_ID,
    BASE_META_PATH,
    _assert_base_contract,
    _build_overrides,
    _collect_diffs,
    _load_json,
    _path_text,
    _run_one,
    _static_time_audit,
)


PHASE_CONTRACTS: dict[str, dict[str, set[str]]] = {
    "baseline": {
        "config_paths": set(),
        "override_paths": set(),
    },
    "tight_pullback": {
        "config_paths": {
            "strategy.params.enable_pullback_candidates",
            "strategy.params.pullback_variant_mode",
        },
        "override_paths": set(),
    },
    "tight_pullback_source_residual": {
        "config_paths": {
            "strategy.params.enable_pullback_candidates",
            "strategy.params.pullback_variant_mode",
            "strategy.params.enable_residual_ranking",
            "strategy.params.residual_window",
            "strategy.params.source_aware_residual_mode",
        },
        "override_paths": {
            "enable_multifactor_rank",
            "mf_topk",
            "mf_concentrate_topn",
            "mf_concentrate_scale",
            "mf_rank_gate_mode",
        },
    },
}

ALPHA_SOURCE_ALIAS = {
    "breakout": "breakout",
    "pullback": "pullback_only",
    "pullback_only": "pullback_only",
    "breakout+pullback": "pullback_overlap",
    "pullback_overlap": "pullback_overlap",
}

SOURCE_ORDER = ["breakout", "pullback_overlap", "pullback_only"]


def _normalize_source(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "unknown"
    return ALPHA_SOURCE_ALIAS.get(text, text)


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _safe_json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        obj = json.loads(text)
    except Exception:
        return {}
    return dict(obj) if isinstance(obj, dict) else {}


def _safe_float(value: Any) -> float | None:
    if value in (None, "", "nan", "None"):
        return None
    try:
        out = float(value)
    except Exception:
        return None
    if pd.isna(out):
        return None
    return float(out)


def _assert_allowed_diffs(phase_name: str, base_cfg: dict[str, Any], phase_cfg: dict[str, Any]) -> None:
    allowed = set((PHASE_CONTRACTS.get(phase_name) or {}).get("config_paths", set()))
    diffs = _collect_diffs(base_cfg, phase_cfg)
    unexpected = [diff for diff in diffs if _path_text(diff[0]) not in allowed]
    if unexpected:
        lines = []
        for diff_path, base_value, phase_value in unexpected[:20]:
            lines.append(f"{_path_text(diff_path)}: base={base_value!r}, phase={phase_value!r}")
        raise RuntimeError(f"{phase_name} drifted beyond allowed paths:\n" + "\n".join(lines))


def _build_phase_cfg(base_cfg: dict[str, Any], phase_name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    cfg = json.loads(json.dumps(base_cfg))
    params = cfg.setdefault("strategy", {}).setdefault("params", {})
    overrides: dict[str, Any] = {}

    if phase_name == "baseline":
        _assert_allowed_diffs(phase_name, base_cfg, cfg)
        return cfg, overrides
    if phase_name == "tight_pullback":
        params["enable_pullback_candidates"] = True
        params["pullback_variant_mode"] = "pb_tight_combo"
    elif phase_name == "tight_pullback_source_residual":
        params["enable_pullback_candidates"] = True
        params["pullback_variant_mode"] = "pb_tight_combo"
        params["enable_residual_ranking"] = True
        params["residual_window"] = 60
        params["source_aware_residual_mode"] = "pullback_only"
        overrides.update(
            {
                "enable_multifactor_rank": True,
                "mf_topk": 0,
                "mf_concentrate_topn": 0,
                "mf_concentrate_scale": 1.0,
                "mf_rank_gate_mode": "ALWAYS_ON",
            }
        )
    else:
        raise ValueError(f"unknown phase: {phase_name}")

    _assert_allowed_diffs(phase_name, base_cfg, cfg)
    return cfg, overrides


def _build_phase_audit(base_cfg: dict[str, Any], base_meta: dict[str, Any]) -> list[dict[str, Any]]:
    base_overrides = _build_overrides(base_cfg, base_meta)
    rows: list[dict[str, Any]] = []
    for phase_name in ("baseline", "tight_pullback", "tight_pullback_source_residual"):
        phase_cfg, phase_override = _build_phase_cfg(base_cfg, phase_name)
        cfg_diff_paths = sorted(_path_text(path) for path, _, _ in _collect_diffs(base_cfg, phase_cfg))
        combined_overrides = dict(base_overrides)
        combined_overrides.update(phase_override)
        override_diff_paths = sorted(
            key
            for key in sorted(set(base_overrides.keys()) | set(combined_overrides.keys()))
            if base_overrides.get(key) != combined_overrides.get(key)
        )
        allowed = PHASE_CONTRACTS.get(phase_name) or {"config_paths": set(), "override_paths": set()}
        unexpected_cfg = [path for path in cfg_diff_paths if path not in allowed.get("config_paths", set())]
        unexpected_override = [path for path in override_diff_paths if path not in allowed.get("override_paths", set())]
        rows.append(
            {
                "phase": phase_name,
                "config_diff_paths": cfg_diff_paths,
                "override_diff_paths": override_diff_paths,
                "single_path_audit_pass": not unexpected_cfg and not unexpected_override,
                "unexpected_config_paths": unexpected_cfg,
                "unexpected_override_paths": unexpected_override,
            }
        )
    return rows


def _collect_candidate_source_stats(results_dir: Path) -> tuple[dict[str, Any], pd.DataFrame]:
    funnel = _safe_read_csv(results_dir / "alpha_funnel.csv")
    if not funnel.empty and {"alpha_source", "candidate_count", "selected_count"}.issubset(funnel.columns):
        df = funnel.copy()
        df["alpha_source"] = df["alpha_source"].map(_normalize_source)
        grouped = (
            df.groupby("alpha_source", dropna=False)[["candidate_count", "selected_count", "rejected_count"]]
            .sum(numeric_only=True)
            .reset_index()
        )
    else:
        candidate_df = _safe_read_csv(results_dir / "candidate_signals.csv")
        if candidate_df.empty or "alpha_source" not in candidate_df.columns:
            grouped = pd.DataFrame(columns=["alpha_source", "candidate_count", "selected_count", "rejected_count"])
        else:
            df = candidate_df.copy()
            if "is_candidate" in df.columns:
                df = df[df["is_candidate"].astype(bool)]
            df["alpha_source"] = df["alpha_source"].map(_normalize_source)
            df["selected_flag"] = df.get("selected_flag", False)
            grouped = (
                df.groupby("alpha_source", dropna=False)
                .agg(
                    candidate_count=("symbol", "count"),
                    selected_count=("selected_flag", lambda s: int(pd.Series(s).astype(bool).sum())),
                )
                .reset_index()
            )
            grouped["rejected_count"] = grouped["candidate_count"] - grouped["selected_count"]

    if grouped.empty:
        stats = {
            "alpha_candidate_total": 0,
            "breakout_candidates": 0,
            "pullback_overlap_candidates": 0,
            "pullback_only_candidates": 0,
            "breakout_selected": 0,
            "pullback_overlap_selected": 0,
            "pullback_only_selected": 0,
        }
        return stats, grouped

    grouped["alpha_source"] = grouped["alpha_source"].fillna("unknown").astype(str)
    grouped = grouped.sort_values("alpha_source").reset_index(drop=True)
    stats = {
        "alpha_candidate_total": int(grouped["candidate_count"].sum()),
        "breakout_candidates": int(grouped.loc[grouped["alpha_source"] == "breakout", "candidate_count"].sum()),
        "pullback_overlap_candidates": int(grouped.loc[grouped["alpha_source"] == "pullback_overlap", "candidate_count"].sum()),
        "pullback_only_candidates": int(grouped.loc[grouped["alpha_source"] == "pullback_only", "candidate_count"].sum()),
        "breakout_selected": int(grouped.loc[grouped["alpha_source"] == "breakout", "selected_count"].sum()),
        "pullback_overlap_selected": int(grouped.loc[grouped["alpha_source"] == "pullback_overlap", "selected_count"].sum()),
        "pullback_only_selected": int(grouped.loc[grouped["alpha_source"] == "pullback_only", "selected_count"].sum()),
    }
    return stats, grouped


def _collect_pullback_variant_stats(results_dir: Path) -> pd.DataFrame:
    candidate_df = _safe_read_csv(results_dir / "candidate_signals.csv")
    if candidate_df.empty or "pullback_variant" not in candidate_df.columns:
        return pd.DataFrame(
            columns=[
                "pullback_variant",
                "candidate_count",
                "selected_count",
                "executed_buys",
                "realized_matches",
                "win_rate",
                "avg_return",
                "avg_hold_days",
                "realized_pnl",
            ]
        )

    df = candidate_df.copy()
    if "is_candidate" in df.columns:
        df = df[df["is_candidate"].astype(bool)]
    if df.empty:
        return pd.DataFrame()
    df["alpha_source"] = df.get("alpha_source", "").map(_normalize_source)
    df["pullback_variant"] = df["pullback_variant"].fillna("").astype(str)
    df["selected_flag"] = df.get("selected_flag", False)
    df = df[(df["alpha_source"].isin({"pullback_only", "pullback_overlap"})) & (df["pullback_variant"] != "")]
    if df.empty:
        return pd.DataFrame()
    grouped = (
        df.groupby("pullback_variant", dropna=False)
        .agg(
            candidate_count=("symbol", "count"),
            selected_count=("selected_flag", lambda s: int(pd.Series(s).astype(bool).sum())),
        )
        .reset_index()
    )
    return grouped


def _collect_source_trade_stats(results_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    trades = _safe_read_csv(results_dir / "portfolio_trades.csv")
    if trades.empty or "symbol" not in trades.columns or "side" not in trades.columns:
        empty = pd.DataFrame(
            columns=[
                "alpha_source",
                "executed_buys",
                "realized_matches",
                "win_rate",
                "avg_return",
                "avg_hold_days",
                "realized_pnl",
                "realized_pnl_share",
            ]
        )
        return empty, pd.DataFrame()

    df = trades.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["symbol"] = df["symbol"].astype(str).str.lower()
    df = df.dropna(subset=["date", "symbol"])
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    open_lots: dict[str, list[dict[str, Any]]] = {}
    buy_counts: dict[str, int] = {}
    matched_rows: list[dict[str, Any]] = []

    for row in df.sort_values(["date"], kind="mergesort").itertuples(index=False):
        sym = str(getattr(row, "symbol", "")).lower()
        side = str(getattr(row, "side", "")).upper()
        qty = int(float(getattr(row, "qty", 0) or 0))
        if qty <= 0:
            continue
        meta = _safe_json_dict(getattr(row, "meta_json", None))
        net_amount = _safe_float(getattr(row, "net_amount", None))
        fill_price = _safe_float(getattr(row, "fill_price", None))
        price = fill_price if fill_price is not None else _safe_float(getattr(row, "price", None))
        if net_amount is not None:
            unit_value = net_amount / max(qty, 1)
        elif price is not None:
            unit_value = price
        else:
            continue
        day = pd.Timestamp(getattr(row, "date"))

        if side == "BUY":
            alpha_source = _normalize_source(meta.get("alpha_source"))
            buy_counts[alpha_source] = int(buy_counts.get(alpha_source, 0)) + 1
            open_lots.setdefault(sym, []).append(
                {
                    "qty": qty,
                    "unit_cost": float(unit_value),
                    "date": day,
                    "alpha_source": alpha_source,
                    "pullback_variant": str(meta.get("pullback_variant") or ""),
                }
            )
            continue

        if side != "SELL":
            continue

        remain = qty
        lots = open_lots.get(sym, [])
        while remain > 0 and lots:
            head = lots[0]
            matched = min(remain, int(head["qty"]))
            unit_cost = float(head["unit_cost"])
            pnl = float(unit_value - unit_cost) * matched
            ret = (float(unit_value) / unit_cost - 1.0) if unit_cost > 1e-8 else None
            hold_days = int((day - pd.Timestamp(head["date"])).days)
            matched_rows.append(
                {
                    "alpha_source": str(head["alpha_source"]),
                    "pullback_variant": str(head["pullback_variant"]),
                    "matched_qty": int(matched),
                    "return_pct": ret,
                    "hold_days": hold_days,
                    "pnl": pnl,
                }
            )
            head["qty"] = int(head["qty"]) - matched
            remain -= matched
            if int(head["qty"]) <= 0:
                lots.pop(0)
        if lots:
            open_lots[sym] = lots

    matched_df = pd.DataFrame(matched_rows)
    if matched_df.empty:
        source_df = pd.DataFrame(
            [
                {
                    "alpha_source": source,
                    "executed_buys": int(buy_counts.get(source, 0)),
                    "realized_matches": 0,
                    "win_rate": None,
                    "avg_return": None,
                    "avg_hold_days": None,
                    "realized_pnl": 0.0,
                    "realized_pnl_share": None,
                }
                for source in sorted(buy_counts.keys())
            ]
        )
        return source_df, matched_df

    grouped = (
        matched_df.groupby("alpha_source", dropna=False)
        .agg(
            realized_matches=("matched_qty", "count"),
            win_rate=("pnl", lambda s: float((pd.Series(s) > 0).mean())),
            avg_return=("return_pct", "mean"),
            avg_hold_days=("hold_days", "mean"),
            realized_pnl=("pnl", "sum"),
        )
        .reset_index()
    )
    grouped["executed_buys"] = grouped["alpha_source"].map(lambda source: int(buy_counts.get(str(source), 0)))
    total_realized_pnl = float(grouped["realized_pnl"].sum())
    if abs(total_realized_pnl) > 1e-8:
        grouped["realized_pnl_share"] = grouped["realized_pnl"] / total_realized_pnl
    else:
        grouped["realized_pnl_share"] = None
    grouped = grouped[
        [
            "alpha_source",
            "executed_buys",
            "realized_matches",
            "win_rate",
            "avg_return",
            "avg_hold_days",
            "realized_pnl",
            "realized_pnl_share",
        ]
    ]
    grouped = grouped.sort_values("alpha_source").reset_index(drop=True)
    return grouped, matched_df


def _merge_source_stats(
    *,
    phase_name: str,
    candidate_stats_df: pd.DataFrame,
    trade_stats_df: pd.DataFrame,
) -> pd.DataFrame:
    left = candidate_stats_df.copy()
    if left.empty:
        left = pd.DataFrame({"alpha_source": SOURCE_ORDER})
        left["candidate_count"] = 0
        left["selected_count"] = 0
        left["rejected_count"] = 0
    right = trade_stats_df.copy()
    if right.empty:
        right = pd.DataFrame({"alpha_source": SOURCE_ORDER})
        right["executed_buys"] = 0
        right["realized_matches"] = 0
        right["win_rate"] = None
        right["avg_return"] = None
        right["avg_hold_days"] = None
        right["realized_pnl"] = 0.0
        right["realized_pnl_share"] = None
    merged = left.merge(right, on="alpha_source", how="outer")
    for col in ("candidate_count", "selected_count", "rejected_count", "executed_buys", "realized_matches"):
        if col in merged.columns:
            merged[col] = merged[col].fillna(0).astype(int)
    merged.insert(0, "phase", phase_name)
    merged["source_order"] = merged["alpha_source"].map(
        {name: idx for idx, name in enumerate(SOURCE_ORDER, start=1)}
    ).fillna(99)
    merged = merged.sort_values(["phase", "source_order", "alpha_source"]).drop(columns=["source_order"]).reset_index(drop=True)
    return merged


def _merge_variant_stats(
    *,
    phase_name: str,
    candidate_variant_df: pd.DataFrame,
    matched_df: pd.DataFrame,
) -> pd.DataFrame:
    left = candidate_variant_df.copy()
    if left.empty:
        return pd.DataFrame()

    right = pd.DataFrame(columns=["pullback_variant"])
    if not matched_df.empty and "pullback_variant" in matched_df.columns:
        raw = matched_df.copy()
        raw["pullback_variant"] = raw["pullback_variant"].fillna("").astype(str)
        raw = raw[raw["pullback_variant"] != ""]
        if not raw.empty:
            right = (
                raw.groupby("pullback_variant", dropna=False)
                .agg(
                    realized_matches=("matched_qty", "count"),
                    win_rate=("pnl", lambda s: float((pd.Series(s) > 0).mean())),
                    avg_return=("return_pct", "mean"),
                    avg_hold_days=("hold_days", "mean"),
                    realized_pnl=("pnl", "sum"),
                )
                .reset_index()
            )
            buy_orders = (
                raw.groupby("pullback_variant", dropna=False)
                .size()
                .reset_index(name="executed_buys_proxy")
            )
            right = right.merge(buy_orders, on="pullback_variant", how="left")

    merged = left.merge(right, on="pullback_variant", how="left")
    for col in ("executed_buys_proxy", "realized_matches"):
        if col in merged.columns:
            merged[col] = merged[col].fillna(0).astype(int)
    merged.insert(0, "phase", phase_name)
    merged = merged.sort_values(["phase", "pullback_variant"]).reset_index(drop=True)
    return merged


def _enrich_phase_metrics(row: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    results_dir = Path(str(row.get("results_dir") or ""))
    candidate_stats, candidate_source_df = _collect_candidate_source_stats(results_dir)
    trade_source_df, matched_df = _collect_source_trade_stats(results_dir)
    merged_source_df = _merge_source_stats(
        phase_name=str(row.get("phase") or ""),
        candidate_stats_df=candidate_source_df,
        trade_stats_df=trade_source_df,
    )
    variant_source_df = _merge_variant_stats(
        phase_name=str(row.get("phase") or ""),
        candidate_variant_df=_collect_pullback_variant_stats(results_dir),
        matched_df=matched_df,
    )
    row.update(candidate_stats)
    row["breakout_executed_buys"] = int(
        merged_source_df.loc[merged_source_df["alpha_source"] == "breakout", "executed_buys"].sum()
    )
    row["pullback_overlap_executed_buys"] = int(
        merged_source_df.loc[merged_source_df["alpha_source"] == "pullback_overlap", "executed_buys"].sum()
    )
    row["pullback_only_executed_buys"] = int(
        merged_source_df.loc[merged_source_df["alpha_source"] == "pullback_only", "executed_buys"].sum()
    )
    row["pullback_only_realized_pnl"] = float(
        merged_source_df.loc[merged_source_df["alpha_source"] == "pullback_only", "realized_pnl"].sum()
        if "realized_pnl" in merged_source_df.columns
        else 0.0
    )
    row["pullback_overlap_realized_pnl"] = float(
        merged_source_df.loc[merged_source_df["alpha_source"] == "pullback_overlap", "realized_pnl"].sum()
        if "realized_pnl" in merged_source_df.columns
        else 0.0
    )
    return row, merged_source_df, variant_source_df


def _write_summary(
    *,
    out_dir: Path,
    base_cfg: dict[str, Any],
    base_meta: dict[str, Any],
    audit: dict[str, Any],
    phase_audit: list[dict[str, Any]],
    results: list[dict[str, Any]],
    source_rows: list[pd.DataFrame],
    variant_rows: list[pd.DataFrame],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    ab_df = pd.DataFrame(results)
    ab_df.to_csv(out_dir / "ab_summary.csv", index=False)

    source_df = pd.concat([df for df in source_rows if not df.empty], ignore_index=True) if source_rows else pd.DataFrame()
    source_df.to_csv(out_dir / "source_contribution.csv", index=False)

    variant_df = pd.concat([df for df in variant_rows if not df.empty], ignore_index=True) if variant_rows else pd.DataFrame()
    variant_df.to_csv(out_dir / "pullback_variant_contribution.csv", index=False)

    summary = {
        "generated_at": datetime.now().isoformat(),
        "base_exp_id": BASE_EXP_ID,
        "base_config_path": str(BASE_CFG_PATH),
        "base_meta_path": str(BASE_META_PATH),
        "unchanged_contract": {
            "benchmark": str((base_cfg.get("universe") or {}).get("benchmark") or ""),
            "start": str((base_cfg.get("universe") or {}).get("start") or ""),
            "end": str((base_cfg.get("universe") or {}).get("end") or ""),
            "costs": base_cfg.get("costs") or {},
            "execution": base_cfg.get("execution") or {},
            "benchmark_regime": base_cfg.get("benchmark_regime") or {},
            "universe_mode": str((base_meta.get("data") or {}).get("universe_mode") or ""),
        },
        "static_audit": audit,
        "phase_audit": phase_audit,
        "results": results,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# Breakout Tight Pullback Research",
        "",
        f"- base_exp_id: `{BASE_EXP_ID}`",
        f"- universe_mode: `{(base_meta.get('data') or {}).get('universe_mode', '')}`",
        f"- benchmark: `{(base_cfg.get('universe') or {}).get('benchmark', '')}`",
        f"- static_audit: `{json.dumps(audit, ensure_ascii=False)}`",
        "",
        "## Phase Audit",
        "",
    ]
    for row in phase_audit:
        md_lines.append(
            "- `{phase}`: pass=`{single_path_audit_pass}` | config={config_diff_paths} | overrides={override_diff_paths}".format(
                phase=row["phase"],
                single_path_audit_pass=row["single_path_audit_pass"],
                config_diff_paths=json.dumps(row["config_diff_paths"], ensure_ascii=False),
                override_diff_paths=json.dumps(row["override_diff_paths"], ensure_ascii=False),
            )
        )

    md_lines.extend(
        [
            "",
            "## AB Summary",
            "",
            "| phase | raw_signal | alpha_candidates | pullback_only_candidates | avg_positions | utilization | CAGR | MaxDD | Sharpe | Calmar | win_rate | avg_hold_days | exp_id |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in results:
        win_rate = "-" if row.get("win_rate") is None else f"{float(row['win_rate']):.2%}"
        avg_hold_days = "-" if row.get("avg_hold_days") is None else f"{float(row['avg_hold_days']):.2f}"
        md_lines.append(
            "| {phase} | {raw_signal} | {alpha_candidate_total} | {pullback_only_candidates} | {avg_positions:.2f} | {utilization:.2%} | "
            "{cagr:.2%} | {max_drawdown:.2%} | {sharpe:.2f} | {calmar:.2f} | "
            f"{win_rate} | {avg_hold_days} | `{row.get('exp_id', '')}` |".format(**row)
        )

    if not source_df.empty:
        md_lines.extend(
            [
                "",
                "## Source Contribution",
                "",
                "| phase | alpha_source | candidate_count | selected_count | executed_buys | realized_matches | win_rate | avg_return | realized_pnl |",
                "|---|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in source_df.to_dict(orient="records"):
            win_rate = "-" if pd.isna(row.get("win_rate")) else f"{float(row['win_rate']):.2%}"
            avg_return = "-" if pd.isna(row.get("avg_return")) else f"{float(row['avg_return']):.2%}"
            realized_pnl = "-" if pd.isna(row.get("realized_pnl")) else f"{float(row['realized_pnl']):.2f}"
            md_lines.append(
                f"| {row.get('phase', '')} | {row.get('alpha_source', '')} | {int(row.get('candidate_count', 0))} | "
                f"{int(row.get('selected_count', 0))} | {int(row.get('executed_buys', 0))} | "
                f"{int(row.get('realized_matches', 0))} | {win_rate} | {avg_return} | {realized_pnl} |"
            )

    if not variant_df.empty:
        md_lines.extend(
            [
                "",
                "## Pullback Variant Contribution",
                "",
                "| phase | pullback_variant | candidate_count | selected_count | realized_matches | win_rate | avg_return | realized_pnl |",
                "|---|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in variant_df.to_dict(orient="records"):
            win_rate = "-" if pd.isna(row.get("win_rate")) else f"{float(row['win_rate']):.2%}"
            avg_return = "-" if pd.isna(row.get("avg_return")) else f"{float(row['avg_return']):.2%}"
            realized_pnl = "-" if pd.isna(row.get("realized_pnl")) else f"{float(row['realized_pnl']):.2f}"
            md_lines.append(
                f"| {row.get('phase', '')} | {row.get('pullback_variant', '')} | {int(row.get('candidate_count', 0))} | "
                f"{int(row.get('selected_count', 0))} | {int(row.get('realized_matches', 0) if not pd.isna(row.get('realized_matches')) else 0)} | "
                f"{win_rate} | {avg_return} | {realized_pnl} |"
            )

    (out_dir / "summary.md").write_text("\n".join(md_lines), encoding="utf-8")


def _dry_run() -> None:
    base_cfg = _load_json(BASE_CFG_PATH)
    base_meta = _load_json(BASE_META_PATH)
    _assert_base_contract(base_cfg, base_meta)
    _static_time_audit()
    phase_audit = _build_phase_audit(base_cfg, base_meta)
    for row in phase_audit:
        if not bool(row.get("single_path_audit_pass")):
            raise RuntimeError(f"phase audit failed: {row}")
    for phase_name in ("baseline", "tight_pullback", "tight_pullback_source_residual"):
        phase_cfg, phase_override = _build_phase_cfg(base_cfg, phase_name)
        combined_overrides = _build_overrides(base_cfg, base_meta)
        combined_overrides.update(phase_override)
        print(json.dumps({"phase": phase_name, "override_keys": sorted(combined_overrides.keys())}, ensure_ascii=False))
        if not isinstance(phase_cfg, dict):
            raise RuntimeError(f"{phase_name} config build failed")
    print("dry-run-ok")


def main(argv: list[str] | None = None) -> None:
    argv = list(argv or sys.argv[1:])
    if not BASE_CFG_PATH.exists():
        raise FileNotFoundError(f"missing base config: {BASE_CFG_PATH}")
    if not BASE_META_PATH.exists():
        raise FileNotFoundError(f"missing base meta: {BASE_META_PATH}")

    if "--dry-run" in argv:
        _dry_run()
        return

    base_cfg = _load_json(BASE_CFG_PATH)
    base_meta = _load_json(BASE_META_PATH)
    _assert_base_contract(base_cfg, base_meta)
    audit = _static_time_audit()
    phase_audit = _build_phase_audit(base_cfg, base_meta)
    failed_phase_audit = [row for row in phase_audit if not bool(row.get("single_path_audit_pass"))]
    if failed_phase_audit:
        raise RuntimeError(f"phase audit failed: {failed_phase_audit}")

    results: list[dict[str, Any]] = []
    source_rows: list[pd.DataFrame] = []
    variant_rows: list[pd.DataFrame] = []
    for phase_name in ("baseline", "tight_pullback", "tight_pullback_source_residual"):
        phase_cfg, phase_override = _build_phase_cfg(base_cfg, phase_name)
        overrides = _build_overrides(base_cfg, base_meta)
        overrides.update(phase_override)
        row = _run_one(phase_name=phase_name, runtime_cfg=phase_cfg, overrides=overrides)
        row, source_df, variant_df = _enrich_phase_metrics(row)
        results.append(row)
        source_rows.append(source_df)
        if not variant_df.empty:
            variant_rows.append(variant_df)

    out_dir = ROOT / "outputs" / "experiments" / f"tight_pullback_research_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    _write_summary(
        out_dir=out_dir,
        base_cfg=base_cfg,
        base_meta=base_meta,
        audit=audit,
        phase_audit=phase_audit,
        results=results,
        source_rows=source_rows,
        variant_rows=variant_rows,
    )
    print(f"summary_dir={out_dir}")


if __name__ == "__main__":
    main()
