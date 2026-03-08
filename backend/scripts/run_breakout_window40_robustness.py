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
    _compute_trade_stats,
    _load_json,
    _path_text,
    _run_one,
    _static_time_audit,
)


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _parse_target_window(argv: list[str]) -> int:
    default = 40
    if "--target-window" not in argv:
        return default
    idx = argv.index("--target-window")
    if idx + 1 >= len(argv):
        raise ValueError("--target-window requires a value")
    return int(argv[idx + 1])


def _assert_allowed_diffs(
    *,
    label: str,
    base_cfg: dict[str, Any],
    candidate_cfg: dict[str, Any],
    allowed_config_paths: set[str],
) -> None:
    diffs = _collect_diffs(base_cfg, candidate_cfg)
    unexpected = [diff for diff in diffs if _path_text(diff[0]) not in allowed_config_paths]
    if unexpected:
        lines = []
        for diff_path, base_value, phase_value in unexpected[:20]:
            lines.append(f"{_path_text(diff_path)}: base={base_value!r}, phase={phase_value!r}")
        raise RuntimeError(f"{label} drifted beyond allowed paths:\n" + "\n".join(lines))


def _build_variant_cfg(base_cfg: dict[str, Any], breakout_window: int) -> dict[str, Any]:
    cfg = json.loads(json.dumps(base_cfg))
    cfg.setdefault("strategy", {}).setdefault("params", {})["breakout_window"] = int(breakout_window)
    _assert_allowed_diffs(
        label=f"breakout_window_{breakout_window}",
        base_cfg=base_cfg,
        candidate_cfg=cfg,
        allowed_config_paths={"strategy.params.breakout_window"},
    )
    return cfg


def _annual_and_monthly_concentration(results_dir: Path) -> dict[str, Any]:
    daily = _safe_read_csv(results_dir / "portfolio_daily.csv")
    if daily.empty or "date" not in daily.columns or "nav" not in daily.columns:
        return {
            "positive_years": 0,
            "negative_years": 0,
            "top3_positive_month_share": None,
            "top3_positive_year_share": None,
        }

    df = daily.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    df = df.dropna(subset=["date", "nav"]).sort_values("date")
    if df.empty:
        return {
            "positive_years": 0,
            "negative_years": 0,
            "top3_positive_month_share": None,
            "top3_positive_year_share": None,
        }

    nav_s = df.set_index("date")["nav"].astype(float)
    monthly = nav_s.resample("ME").last().pct_change().dropna()
    yearly = nav_s.resample("YE").last().pct_change().dropna()

    pos_months = monthly[monthly > 0]
    pos_years = yearly[yearly > 0]
    top3_month_share = None
    if not pos_months.empty and float(pos_months.sum()) > 1e-12:
        top3_month_share = float(pos_months.sort_values(ascending=False).head(3).sum() / pos_months.sum())
    top3_year_share = None
    if not pos_years.empty and float(pos_years.sum()) > 1e-12:
        top3_year_share = float(pos_years.sort_values(ascending=False).head(3).sum() / pos_years.sum())

    return {
        "positive_years": int((yearly > 0).sum()),
        "negative_years": int((yearly < 0).sum()),
        "top3_positive_month_share": top3_month_share,
        "top3_positive_year_share": top3_year_share,
    }


def _realized_symbol_concentration(results_dir: Path) -> dict[str, Any]:
    trades = _safe_read_csv(results_dir / "portfolio_trades.csv")
    if trades.empty or "symbol" not in trades.columns or "side" not in trades.columns:
        return {
            "top3_positive_symbol_share": None,
            "realized_symbol_count": 0,
        }

    df = trades.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["symbol"] = df["symbol"].astype(str).str.lower()
    df["side"] = df["side"].astype(str).str.upper()
    fill_price = pd.to_numeric(df["fill_price"] if "fill_price" in df.columns else df.get("price"), errors="coerce")
    price = fill_price.fillna(pd.to_numeric(df.get("price"), errors="coerce"))
    df["fill_price_eff"] = price
    df["qty"] = pd.to_numeric(df.get("qty"), errors="coerce").fillna(0).astype(int)
    df = df.dropna(subset=["date", "symbol", "fill_price_eff"])
    if df.empty:
        return {
            "top3_positive_symbol_share": None,
            "realized_symbol_count": 0,
        }

    open_lots: dict[str, list[dict[str, Any]]] = {}
    realized_rows: list[dict[str, Any]] = []
    for row in df.sort_values(["date"]).itertuples(index=False):
        sym = str(getattr(row, "symbol", "")).lower()
        side = str(getattr(row, "side", "")).upper()
        qty = int(getattr(row, "qty", 0) or 0)
        px = float(getattr(row, "fill_price_eff", 0.0) or 0.0)
        day = pd.Timestamp(getattr(row, "date"))
        if qty <= 0 or px <= 0:
            continue
        if side == "BUY":
            open_lots.setdefault(sym, []).append({"qty": qty, "price": px, "date": day})
            continue
        if side != "SELL":
            continue
        remain = qty
        lots = open_lots.get(sym, [])
        while remain > 0 and lots:
            head = lots[0]
            matched = min(remain, int(head["qty"]))
            pnl = (px - float(head["price"])) * matched
            realized_rows.append({"symbol": sym, "pnl": pnl})
            head["qty"] = int(head["qty"]) - matched
            remain -= matched
            if int(head["qty"]) <= 0:
                lots.pop(0)
        if lots:
            open_lots[sym] = lots

    rdf = pd.DataFrame(realized_rows)
    if rdf.empty:
        return {
            "top3_positive_symbol_share": None,
            "realized_symbol_count": 0,
        }
    symbol_pnl = rdf.groupby("symbol", dropna=False)["pnl"].sum().sort_values(ascending=False)
    positive = symbol_pnl[symbol_pnl > 0]
    share = None
    if not positive.empty and float(positive.sum()) > 1e-12:
        share = float(positive.head(3).sum() / positive.sum())
    return {
        "top3_positive_symbol_share": share,
        "realized_symbol_count": int(symbol_pnl.shape[0]),
    }


def _collect_extra_metrics(row: dict[str, Any]) -> dict[str, Any]:
    results_dir = Path(str(row.get("results_dir") or ""))
    trade_stats = _compute_trade_stats(results_dir)
    concentration = _annual_and_monthly_concentration(results_dir)
    symbol_concentration = _realized_symbol_concentration(results_dir)
    row["win_rate"] = trade_stats.get("win_rate")
    row["avg_hold_days"] = trade_stats.get("avg_hold_days")
    row.update(concentration)
    row.update(symbol_concentration)
    return row


def _execute_runs(
    *,
    run_specs: list[dict[str, Any]],
    base_cfg: dict[str, Any],
    base_meta: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    base_overrides = _build_overrides(base_cfg, base_meta)

    for spec in run_specs:
        label = str(spec["label"])
        breakout_window = int(spec["breakout_window"])
        runtime_cfg = _build_variant_cfg(base_cfg, breakout_window)
        overrides = dict(base_overrides)
        overrides.update(spec.get("override_values") or {})
        row = _run_one(phase_name=label, runtime_cfg=runtime_cfg, overrides=overrides)
        row["label"] = label
        row["breakout_window"] = breakout_window
        row["review_group"] = str(spec["group"])
        row["review_window"] = str(spec.get("review_window") or "")
        row["review_end"] = str(spec.get("review_end") or "")
        row = _collect_extra_metrics(row)
        results.append(row)

        cfg_diff_paths = sorted(_path_text(path) for path, _, _ in _collect_diffs(base_cfg, runtime_cfg))
        override_diff_paths = sorted(
            key
            for key in sorted(set(base_overrides.keys()) | set(overrides.keys()))
            if base_overrides.get(key) != overrides.get(key)
        )
        audits.append(
            {
                "label": label,
                "group": str(spec["group"]),
                "config_diff_paths": cfg_diff_paths,
                "override_diff_paths": override_diff_paths,
                "single_path_audit_pass": (
                    set(cfg_diff_paths).issubset({"strategy.params.breakout_window"})
                    and set(override_diff_paths).issubset({"start_date", "end_date"})
                ),
            }
        )
    return results, audits


def _write_table_md(rows: list[str]) -> list[str]:
    return rows + [""]


def _write_summary(
    *,
    out_dir: Path,
    base_cfg: dict[str, Any],
    audit: dict[str, Any],
    run_audits: list[dict[str, Any]],
    results: list[dict[str, Any]],
    target_window: int,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(results)
    df.to_csv(out_dir / "robustness_runs.csv", index=False)
    pd.DataFrame(run_audits).to_csv(out_dir / "run_audit.csv", index=False)

    local_df = df[df["review_group"] == "local"].copy()
    window_df = df[df["review_group"] == "window"].copy()
    terminal_df = df[df["review_group"] == "terminal"].copy()
    concentration_df = df[df["review_group"] == "local"].copy()
    concentration_df = concentration_df[concentration_df["label"].isin(["baseline_55", f"bw{target_window}"])]
    concentration_df = concentration_df[
        [
            "label",
            "breakout_window",
            "top3_positive_month_share",
            "top3_positive_year_share",
            "top3_positive_symbol_share",
            "positive_years",
            "negative_years",
            "realized_symbol_count",
        ]
    ]
    local_df.to_csv(out_dir / "local_robustness.csv", index=False)
    window_df.to_csv(out_dir / "window_check.csv", index=False)
    terminal_df.to_csv(out_dir / "terminal_sensitivity.csv", index=False)
    concentration_df.to_csv(out_dir / "concentration_check.csv", index=False)

    summary = {
        "generated_at": datetime.now().isoformat(),
        "base_exp_id": BASE_EXP_ID,
        "main_change_path": "strategy.params.breakout_window",
        "base_breakout_window": int(((base_cfg.get("strategy") or {}).get("params") or {}).get("breakout_window", 0) or 0),
        "unchanged_contract": {
            "benchmark": str((base_cfg.get("universe") or {}).get("benchmark") or ""),
            "start": str((base_cfg.get("universe") or {}).get("start") or ""),
            "end": str((base_cfg.get("universe") or {}).get("end") or ""),
            "costs": base_cfg.get("costs") or {},
            "execution": base_cfg.get("execution") or {},
            "benchmark_regime": base_cfg.get("benchmark_regime") or {},
            "atr_stop_k": float((((base_cfg.get("strategy") or {}).get("params") or {}).get("atr_stop_k", 0.0) or 0.0)),
        },
        "static_audit": audit,
        "run_audit": run_audits,
        "results": results,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Breakout Window {target_window} Robustness Review",
        "",
        f"- base_exp_id: `{BASE_EXP_ID}`",
        f"- main_change: `strategy.params.breakout_window`",
        f"- static_audit: `{json.dumps(audit, ensure_ascii=False)}`",
        "",
        "## Run Audit",
        "",
    ]
    for row in run_audits:
        lines.append(
            "- `{label}`: pass=`{single_path_audit_pass}` | config={config_diff_paths} | overrides={override_diff_paths}".format(
                **row
            )
        )

    lines.extend(_write_table_md([
        "## Local Robustness",
        "",
        "| label | breakout_window | CAGR | MaxDD | Sharpe | Calmar | trades | exp_id |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
        *[
            "| {label} | {breakout_window} | {cagr:.2%} | {max_drawdown:.2%} | {sharpe:.2f} | {calmar:.2f} | {trades} | `{exp_id}` |".format(**row)
            for row in local_df.to_dict(orient="records")
        ],
    ]))

    lines.extend(_write_table_md([
        "## Window Check",
        "",
        "| label | window | breakout_window | CAGR | MaxDD | Sharpe | Calmar | trades | exp_id |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
        *[
            "| {label} | {review_window} | {breakout_window} | {cagr:.2%} | {max_drawdown:.2%} | {sharpe:.2f} | {calmar:.2f} | {trades} | `{exp_id}` |".format(**row)
            for row in window_df.to_dict(orient="records")
        ],
    ]))

    lines.extend(_write_table_md([
        "## Terminal Sensitivity",
        "",
        "| label | end_date | breakout_window | CAGR | MaxDD | Sharpe | Calmar | trades | exp_id |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
        *[
            "| {label} | {review_end} | {breakout_window} | {cagr:.2%} | {max_drawdown:.2%} | {sharpe:.2f} | {calmar:.2f} | {trades} | `{exp_id}` |".format(**row)
            for row in terminal_df.to_dict(orient="records")
        ],
    ]))

    lines.extend(_write_table_md([
        "## Concentration Check",
        "",
        "| label | breakout_window | top3_positive_month_share | top3_positive_year_share | top3_positive_symbol_share | positive_years | negative_years | realized_symbol_count |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        *[
            "| {label} | {breakout_window} | {top3_positive_month_share:.2%} | {top3_positive_year_share:.2%} | {top3_positive_symbol_share:.2%} | {positive_years} | {negative_years} | {realized_symbol_count} |".format(
                **{
                    **row,
                    "top3_positive_month_share": (0.0 if pd.isna(row.get("top3_positive_month_share")) else float(row.get("top3_positive_month_share"))),
                    "top3_positive_year_share": (0.0 if pd.isna(row.get("top3_positive_year_share")) else float(row.get("top3_positive_year_share"))),
                    "top3_positive_symbol_share": (0.0 if pd.isna(row.get("top3_positive_symbol_share")) else float(row.get("top3_positive_symbol_share"))),
                }
            )
            for row in concentration_df.to_dict(orient="records")
        ],
    ]))
    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def _dry_run() -> None:
    target_window = _parse_target_window(sys.argv[1:])
    base_cfg = _load_json(BASE_CFG_PATH)
    base_meta = _load_json(BASE_META_PATH)
    _assert_base_contract(base_cfg, base_meta)
    _static_time_audit()
    _build_variant_cfg(base_cfg, target_window)
    print("dry-run-ok")


def main(argv: list[str] | None = None) -> None:
    argv = list(argv or sys.argv[1:])
    target_window = _parse_target_window(argv)
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

    lower_window = max(5, int(target_window) - 5)
    upper_window = int(target_window) + 5
    bw_label = f"bw{target_window}"
    run_specs = [
        {"label": "baseline_55", "group": "local", "breakout_window": 55},
        {"label": f"bw{lower_window}", "group": "local", "breakout_window": lower_window},
        {"label": bw_label, "group": "local", "breakout_window": int(target_window)},
        {"label": f"bw{upper_window}", "group": "local", "breakout_window": upper_window},
        {"label": "baseline_w1", "group": "window", "review_window": "W1", "breakout_window": 55, "override_values": {"start_date": "2016-03-01", "end_date": "2019-12-31"}},
        {"label": f"{bw_label}_w1", "group": "window", "review_window": "W1", "breakout_window": int(target_window), "override_values": {"start_date": "2016-03-01", "end_date": "2019-12-31"}},
        {"label": "baseline_w2", "group": "window", "review_window": "W2", "breakout_window": 55, "override_values": {"start_date": "2020-01-01", "end_date": "2022-12-31"}},
        {"label": f"{bw_label}_w2", "group": "window", "review_window": "W2", "breakout_window": int(target_window), "override_values": {"start_date": "2020-01-01", "end_date": "2022-12-31"}},
        {"label": "baseline_w3", "group": "window", "review_window": "W3", "breakout_window": 55, "override_values": {"start_date": "2023-01-01", "end_date": "2026-03-01"}},
        {"label": f"{bw_label}_w3", "group": "window", "review_window": "W3", "breakout_window": int(target_window), "override_values": {"start_date": "2023-01-01", "end_date": "2026-03-01"}},
        {"label": "baseline_end_2024_12_31", "group": "terminal", "review_end": "2024-12-31", "breakout_window": 55, "override_values": {"end_date": "2024-12-31"}},
        {"label": f"{bw_label}_end_2024_12_31", "group": "terminal", "review_end": "2024-12-31", "breakout_window": int(target_window), "override_values": {"end_date": "2024-12-31"}},
        {"label": "baseline_end_2025_06_30", "group": "terminal", "review_end": "2025-06-30", "breakout_window": 55, "override_values": {"end_date": "2025-06-30"}},
        {"label": f"{bw_label}_end_2025_06_30", "group": "terminal", "review_end": "2025-06-30", "breakout_window": int(target_window), "override_values": {"end_date": "2025-06-30"}},
        {"label": "baseline_end_2025_12_31", "group": "terminal", "review_end": "2025-12-31", "breakout_window": 55, "override_values": {"end_date": "2025-12-31"}},
        {"label": f"{bw_label}_end_2025_12_31", "group": "terminal", "review_end": "2025-12-31", "breakout_window": int(target_window), "override_values": {"end_date": "2025-12-31"}},
    ]
    results, run_audits = _execute_runs(run_specs=run_specs, base_cfg=base_cfg, base_meta=base_meta)
    failed = [row for row in run_audits if not bool(row.get("single_path_audit_pass"))]
    if failed:
        raise RuntimeError(f"run audit failed: {failed}")

    out_dir = ROOT / "outputs" / "experiments" / f"breakout_window{target_window}_robustness_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    _write_summary(
        out_dir=out_dir,
        base_cfg=base_cfg,
        audit=audit,
        run_audits=run_audits,
        results=results,
        target_window=target_window,
    )
    print(f"summary_dir={out_dir}")


if __name__ == "__main__":
    main()
