from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from backend.core.tools.reporting import write_report_to_local


@dataclass(slots=True)
class UnivoteV2Config:
    initial_cash: float = 1_000_000.0
    base_order_value: float = 10_000.0
    lot_mode: str = "LOT100_MIN1LOT"
    lot_size: int = 100


def baseline_variant() -> dict[str, Any]:
    return {
        "group_id": "BASELINE",
        "strategy": {
            "name": "sma_cross_regime_atr",
            "params": {
                "fast": 5,
                "slow": 20,
                "regime_ma": 120,
                "entry_buffer": 0.01,
                "atr_n": 14,
                "debug_atr": True,
                "enable_atr_stop": False,
                "enable_atr_trail": False,
            },
        },
    }


def candidate_variants() -> list[dict[str, Any]]:
    return [
        {
            "group_id": "V_C_S0.8_TNA_M1",
            "strategy": {
                "name": "sma_cross_regime_atr",
                "params": {
                    "fast": 5,
                    "slow": 20,
                    "regime_ma": 120,
                    "entry_buffer": 0.01,
                    "atr_n": 14,
                    "debug_atr": True,
                    "enable_atr_stop": True,
                    "atr_stop_k": 0.8,
                    "enable_atr_trail": False,
                },
            },
        },
        {
            "group_id": "V_B_S0.8_T2.0_M3",
            "strategy": {
                "name": "sma_cross_regime_atr",
                "params": {
                    "fast": 5,
                    "slow": 20,
                    "regime_ma": 120,
                    "entry_buffer": 0.01,
                    "atr_n": 14,
                    "debug_atr": True,
                    "enable_atr_stop": True,
                    "atr_stop_k": 0.8,
                    "enable_atr_trail": True,
                    "atr_trail_k": 2.0,
                },
            },
        },
        {
            "group_id": "V_D_S1.0_T2.0_M3",
            "strategy": {
                "name": "sma_cross_regime_atr",
                "params": {
                    "fast": 5,
                    "slow": 20,
                    "regime_ma": 120,
                    "entry_buffer": 0.01,
                    "atr_n": 14,
                    "debug_atr": True,
                    "enable_atr_stop": True,
                    "atr_stop_k": 1.0,
                    "enable_atr_trail": True,
                    "atr_trail_k": 2.0,
                },
            },
        },
    ]


def build_universe_too_small_rows(
    *,
    raw_count: int,
    status: str,
    source: str,
    universe_limit: int | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    err = (
        "UNIVERSE_TOO_SMALL("
        f"raw_count={raw_count}, status={status}, source={source}, limit={universe_limit})"
    )
    for v in candidate_variants():
        rows.append(
            {
                "group_id": v["group_id"],
                "status": "FAILED",
                "strategy": "sma_cross_regime_atr",
                "strategy_name": "sma_cross_regime_atr",
                "strategy_name_full": "sma_cross_regime_atr",
                "params_json": json.dumps(v["strategy"].get("params", {}), ensure_ascii=False, sort_keys=True),
                "params_json_full": json.dumps(v["strategy"].get("params", {}), ensure_ascii=False, sort_keys=True),
                "run_id": "",
                "error_message": err,
                "error": err,
                "warning_notes": "universe_incomplete=true",
                "pass_rate": None,
                "median_delta_mdd": None,
                "median_delta_return": None,
                "p10_delta_mdd": None,
                "p90_delta_mdd": None,
                "p10_delta_return": None,
                "p90_delta_return": None,
                "mean_atr_exit_rate": None,
                "universe_raw_count": int(raw_count),
                "universe_filtered_count": int(raw_count),
                "skip_reason_top3": "{}",
                "note": f"source={source}; status={status}; universe_limit={universe_limit}",
            }
        )
    return rows


def run_univote_v2(
    *,
    exp_dir: Path,
    symbols: list[str],
    universe_raw_count: int,
    universe_filtered_count: int,
    excluded_reason_counts: dict[str, int],
    run_variant_fn: Callable[[str, dict[str, Any], dict[str, Any]], tuple[dict[str, Any], dict[str, Any]]],
    run_overrides: dict[str, Any],
    cfg: UnivoteV2Config,
    universe_meta: dict[str, Any] | None = None,
    universe_incomplete: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], Path]:
    exp_dir.mkdir(parents=True, exist_ok=True)
    baseline = baseline_variant()
    variants = candidate_variants()
    detail_rows: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []

    for symbol in symbols:
        per_symbol_overrides = dict(run_overrides)
        per_symbol_overrides["symbols"] = [symbol]
        per_symbol_overrides["initial_capital"] = float(cfg.initial_cash)
        per_symbol_overrides["sizing_mode"] = "fixed_value"
        per_symbol_overrides["order_value"] = float(cfg.base_order_value)
        per_symbol_overrides["lot_size"] = 1 if str(cfg.lot_mode).upper() == "ODDLOT_1" else int(cfg.lot_size)
        per_symbol_overrides["univote_lot_mode"] = str(cfg.lot_mode)

        b_row, b_run = run_variant_fn(symbol, baseline, per_symbol_overrides)
        runs.append(b_run)
        b_ret = _num(b_row.get("total_return"))
        b_mdd = _num(b_row.get("max_drawdown"))

        for v in variants:
            row, run_rec = run_variant_fn(symbol, v, per_symbol_overrides)
            runs.append(run_rec)
            ret = _num(row.get("total_return"))
            mdd = _num(row.get("max_drawdown"))
            atr_exit_rate = _num(row.get("atr_exit_rate"))
            d_ret = (ret - b_ret) if ret is not None and b_ret is not None else None
            d_mdd = (mdd - b_mdd) if mdd is not None and b_mdd is not None else None
            passed = False
            if ret is not None and mdd is not None and b_ret is not None and b_mdd is not None:
                passed = (mdd <= b_mdd * 0.8) and (ret >= b_ret - 0.005)
            detail_rows.append(
                {
                    "symbol": symbol,
                    "baseline_return": b_ret,
                    "baseline_mdd": b_mdd,
                    "group_id": v["group_id"],
                    "run_id": row.get("run_id"),
                    "return": ret,
                    "mdd": mdd,
                    "atr_exit_rate": atr_exit_rate,
                    "score": _num(row.get("score")),
                    "delta_return": d_ret,
                    "delta_mdd": d_mdd,
                    "pass": bool(passed),
                    "skip_reason": row.get("skipped_reasons_top3", "{}"),
                }
            )

    details_df = pd.DataFrame(detail_rows)
    details_df.to_csv(exp_dir / "univote_details.csv", index=False)

    rows = _aggregate_rows(
        details_df,
        universe_raw_count=universe_raw_count,
        universe_filtered_count=universe_filtered_count,
        lot_mode=cfg.lot_mode,
        initial_cash=cfg.initial_cash,
        base_order_value=cfg.base_order_value,
    )
    if universe_incomplete:
        err = (
            "UNIVERSE_TOO_SMALL("
            f"raw_count={universe_raw_count}, "
            f"status={str((universe_meta or {}).get('constituents_load_status', 'UNKNOWN'))}, "
            f"source={str((universe_meta or {}).get('symbols_source', 'UNKNOWN'))}, "
            f"limit={str((universe_meta or {}).get('universe_limit', None))})"
        )
        for r in rows:
            r["status"] = "FAILED"
            r["error_message"] = err
            r["error"] = err
            r["warning_notes"] = "universe_incomplete=true"

    report_md = _build_report_markdown(
        details_df=details_df,
        rows=rows,
        universe_raw_count=universe_raw_count,
        universe_filtered_count=universe_filtered_count,
        excluded_reason_counts=excluded_reason_counts,
        cfg=cfg,
        run_overrides=run_overrides,
        universe_meta=universe_meta or {},
        universe_incomplete=universe_incomplete,
    )
    report_path = write_report_to_local("ATR_UNIVOTE_v2.md", report_md)
    return rows, detail_rows, runs, report_path


def write_universe_load_failed_report(
    *,
    universe_meta: dict[str, Any],
    run_overrides: dict[str, Any],
    message: str,
    raw_count: int = 0,
    filtered_count: int = 0,
    universe_incomplete: bool = False,
) -> Path:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# ATR Universe Vote v2",
        "",
        "## 1) Run Info",
        f"- timestamp: {now}",
        f"- date_range: {str(run_overrides.get('start_date') or '')} ~ {str(run_overrides.get('end_date') or '')}",
        f"- symbols_source: {str(universe_meta.get('symbols_source', 'db_index_constituents'))}",
        f"- constituents_load_status: {str(universe_meta.get('constituents_load_status', 'ERROR'))}",
        f"- universe_limit: {str(universe_meta.get('universe_limit', None))}",
        f"- raw_count: {raw_count}",
        f"- filtered_count: {filtered_count}",
        "",
        "## Error",
        f"- UNIVERSE_LOAD_FAILED: {message}",
    ]
    if universe_incomplete:
        lines.extend(
            [
                "",
                "⚠ Universe 不完整，本次投票无效（pass_rate/分位数仅供调试，不可用于结论）。",
            ]
        )
    return write_report_to_local("ATR_UNIVOTE_v2.md", "\n".join(lines) + "\n")


def _aggregate_rows(
    details_df: pd.DataFrame,
    *,
    universe_raw_count: int,
    universe_filtered_count: int,
    lot_mode: str,
    initial_cash: float,
    base_order_value: float,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if details_df.empty:
        return out

    for gid, g in details_df.groupby("group_id"):
        pass_rate = float(g["pass"].astype(bool).mean()) if len(g) > 0 else 0.0
        delta_mdd = pd.to_numeric(g["delta_mdd"], errors="coerce")
        delta_ret = pd.to_numeric(g["delta_return"], errors="coerce")
        atr_exit = pd.to_numeric(g["atr_exit_rate"], errors="coerce")
        skip_counter: dict[str, int] = {}
        for raw in g["skip_reason"].fillna("{}").astype(str):
            try:
                payload = json.loads(raw)
                if isinstance(payload, dict):
                    for k, v in payload.items():
                        skip_counter[str(k)] = skip_counter.get(str(k), 0) + int(v or 0)
            except Exception:
                continue
        top_skip = dict(sorted(skip_counter.items(), key=lambda x: x[1], reverse=True)[:3])
        out.append(
            {
                "group_id": gid,
                "status": "OK",
                "strategy": "sma_cross_regime_atr",
                "strategy_name": "sma_cross_regime_atr",
                "strategy_name_full": "sma_cross_regime_atr",
                "params_json": "{}",
                "params_json_full": "{}",
                "run_id": f"univote_v2_{gid.lower()}",
                "total_return": _safe_stat(delta_ret.median()),
                "max_drawdown": _safe_stat(delta_mdd.median()),
                "filled_rate": pass_rate,
                "trades_count": int(len(g)),
                "tradable_orders_total": int(len(g)),
                "skipped_reasons_top3": json.dumps(top_skip, ensure_ascii=False, sort_keys=True),
                "warning_notes": f"pass_rate={pass_rate:.4f}",
                "pass_rate": pass_rate,
                "median_delta_mdd": _safe_stat(delta_mdd.median()),
                "median_delta_return": _safe_stat(delta_ret.median()),
                "p10_delta_mdd": _safe_stat(delta_mdd.quantile(0.1)),
                "p90_delta_mdd": _safe_stat(delta_mdd.quantile(0.9)),
                "p10_delta_return": _safe_stat(delta_ret.quantile(0.1)),
                "p90_delta_return": _safe_stat(delta_ret.quantile(0.9)),
                "mean_atr_exit_rate": _safe_stat(atr_exit.mean()),
                "universe_raw_count": int(universe_raw_count),
                "universe_filtered_count": int(universe_filtered_count),
                "skip_reason_top3": json.dumps(top_skip, ensure_ascii=False, sort_keys=True),
                "note": f"lot_mode={lot_mode}; initial_cash={initial_cash:.0f}; base_order_value={base_order_value:.0f}",
            }
        )
    return out


def _build_report_markdown(
    *,
    details_df: pd.DataFrame,
    rows: list[dict[str, Any]],
    universe_raw_count: int,
    universe_filtered_count: int,
    excluded_reason_counts: dict[str, int],
    cfg: UnivoteV2Config,
    run_overrides: dict[str, Any],
    universe_meta: dict[str, Any],
    universe_incomplete: bool,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    start_s = str(run_overrides.get("start_date") or "")
    end_s = str(run_overrides.get("end_date") or "")

    lines: list[str] = []
    lines.append("# ATR Universe Vote v2")
    lines.append("")
    lines.append("## 1) 运行信息")
    lines.append(f"- timestamp: {now}")
    lines.append(f"- date_range: {start_s} ~ {end_s}")
    lines.append("- universe_rules: HS300+CSI500, exclude_st, exclude_suspended, min_list_days=120, min_avg_turnover_20d=1e8")
    lines.append(f"- symbols_source: {str(universe_meta.get('symbols_source', 'db_index_constituents'))}")
    lines.append(f"- constituents_load_status: {str(universe_meta.get('constituents_load_status', 'UNKNOWN'))}")
    lines.append(f"- universe_limit: {str(universe_meta.get('universe_limit', None))}")
    lines.append(f"- lot_mode: {cfg.lot_mode}")
    lines.append(f"- initial_cash: {cfg.initial_cash:.0f}")
    lines.append(f"- base_order_value: {cfg.base_order_value:.0f}")
    lines.append("")
    lines.append("## 2) Universe 概况")
    lines.append(f"- raw_count: {universe_raw_count}")
    lines.append(f"- filtered_count: {universe_filtered_count}")
    ex_top = dict(sorted(excluded_reason_counts.items(), key=lambda x: x[1], reverse=True)[:10])
    lines.append(f"- excluded_reason_top10: `{json.dumps(ex_top, ensure_ascii=False)}`")
    lines.append("")
    lines.append("## 3) 三个候选的核心结论")
    lines.append("| group | pass_rate | medianΔmdd | medianΔret | p10Δmdd | p90Δmdd | p10Δret | p90Δret | mean_atr_exit_rate |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        lines.append(
            f"| {r.get('group_id')} | {_fmt_pct(r.get('pass_rate'))} | {_fmt_num(r.get('median_delta_mdd'))} | {_fmt_num(r.get('median_delta_return'))} | "
            f"{_fmt_num(r.get('p10_delta_mdd'))} | {_fmt_num(r.get('p90_delta_mdd'))} | {_fmt_num(r.get('p10_delta_return'))} | "
            f"{_fmt_num(r.get('p90_delta_return'))} | {_fmt_pct(r.get('mean_atr_exit_rate'))} |"
        )
    lines.append("")
    lines.append("## 4) Top 20 改善（按 Δmdd）")
    top20 = details_df.sort_values(["delta_mdd", "delta_return"], ascending=[True, False]).head(20)
    for _, x in top20.iterrows():
        lines.append(f"- {x['symbol']} {x['group_id']} Δmdd={_fmt_num(x['delta_mdd'])} Δret={_fmt_num(x['delta_return'])}")
    lines.append("")
    lines.append("## 5) Worst 20")
    worst20 = details_df.sort_values(["delta_mdd", "delta_return"], ascending=[False, True]).head(20)
    for _, x in worst20.iterrows():
        lines.append(f"- {x['symbol']} {x['group_id']} Δmdd={_fmt_num(x['delta_mdd'])} Δret={_fmt_num(x['delta_return'])}")
    lines.append("")
    lines.append("## 6) 跳过原因统计")
    skip_counter: dict[str, int] = {}
    for raw in details_df["skip_reason"].fillna("{}").astype(str):
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                for k, v in obj.items():
                    skip_counter[str(k)] = skip_counter.get(str(k), 0) + int(v or 0)
        except Exception:
            continue
    for k, v in sorted(skip_counter.items(), key=lambda kv: kv[1], reverse=True)[:5]:
        lines.append(f"- {k}: {v}")
    lines.append("")
    if universe_incomplete:
        lines.append("⚠ Universe 不完整，本次投票无效（pass_rate/分位数仅供调试，不可用于结论）。")
        lines.append("")
    lines.append("## 7) 一句话结论")
    lines.append(f"- 推荐默认：{_recommend(rows)}")
    lines.append("")
    return "\n".join(lines) + "\n"


def _recommend(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "无结果（请检查数据与配置）"
    rows2 = sorted(
        rows,
        key=lambda r: (float(r.get("pass_rate") or 0.0), -float(r.get("median_delta_mdd") or 0.0)),
        reverse=True,
    )
    best = rows2[0]
    return (
        f"{best.get('group_id')}，通过率 {_fmt_pct(best.get('pass_rate'))}，"
        f"中位回撤改善 {_fmt_num(best.get('median_delta_mdd'))}，"
        f"收益中位差 {_fmt_num(best.get('median_delta_return'))}"
    )


def _num(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _safe_stat(v: Any) -> float | None:
    try:
        if pd.isna(v):
            return None
        return float(v)
    except Exception:
        return None


def _fmt_num(v: Any) -> str:
    try:
        return f"{float(v):.6f}"
    except Exception:
        return "NA"


def _fmt_pct(v: Any) -> str:
    try:
        return f"{float(v) * 100:.2f}%"
    except Exception:
        return "NA"
