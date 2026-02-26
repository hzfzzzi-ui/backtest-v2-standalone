from __future__ import annotations

import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _results_root() -> Path:
    raw = os.environ.get("RESULTS_ROOT", "outputs").strip() or "outputs"
    p = Path(raw)
    if not p.is_absolute():
        p = (_repo_root() / p).resolve()
    return p


def sanitize_json(obj: Any) -> Any:
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, (str, int, bool)) or obj is None:
        return obj
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, list):
        return [sanitize_json(x) for x in obj]
    if isinstance(obj, tuple):
        return [sanitize_json(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): sanitize_json(v) for k, v in obj.items()}
    return str(obj)


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


def _build_counters(result: dict[str, Any], results_dir: Path) -> dict[str, Any]:
    """从 result dict 和 results_dir 下的产物文件中提取完整 counters。"""
    counters: dict[str, Any] = {}

    # --- 引擎 metrics 直接透传的字段 ---
    counters["avg_positions"] = float(result.get("avg_positions", 0.0) or 0.0)
    counters["max_positions"] = int(result.get("max_positions", 10) or 10)
    counters["trend_slope_block_count"] = int(result.get("trend_slope_block_count", 0) or 0)
    counters["mf_rank_applied_rate"] = float(result.get("mf_rank_applied_rate", 0.0) or 0.0)
    counters["gate_on_rate"] = float(result.get("mf_gate_on_rate", result.get("gate_on_rate", 0.0)) or 0.0)
    counters["raw_signal"] = int(result.get("raw_signal", 0) or 0)
    counters["blocked"] = int(result.get("blocked", 0) or 0)
    counters["orders"] = int(result.get("orders", 0) or 0)
    counters["skipped"] = int(result.get("skipped", 0) or 0)
    counters["closed_trades"] = int(result.get("closed_trades", 0) or 0)

    # --- 从 portfolio_trades.csv 派生 exit 计数器 ---
    trades_path = results_dir / "portfolio_trades.csv"
    atr_stop = 0
    atr_trail = 0
    atr_trail_update = 0
    reversal = 0
    time_exit = 0
    if trades_path.exists():
        try:
            tdf = pd.read_csv(trades_path)
            if not tdf.empty and "reason_code" in tdf.columns:
                rc = tdf["reason_code"].astype(str).str.upper()
                atr_stop = int(rc.eq("ATR_STOP_LOSS").sum())
                atr_trail = int(rc.eq("ATR_TRAIL_EXIT").sum())
                reversal = int(rc.isin(["SIGNAL_REVERSE", "SMA_CROSS_DOWN"]).sum())
                time_exit = int(rc.eq("TIME_EXIT").sum())
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
    counters["atr_trail_update_count"] = atr_trail_update
    counters["reversal_exit_count"] = reversal
    counters["time_exit_count"] = time_exit

    # --- 从 candidate_diag_reason_counts 派生 constraint 计数器 ---
    diag = dict(result.get("candidate_diag_reason_counts") or {})
    counters["cash_skip_count"] = int(diag.get("SKIP_CASH_INSUFFICIENT", 0) or 0)
    counters["lot_skip_count"] = int(diag.get("SKIP_LOT_TOO_SMALL", 0) or 0)
    counters["cap_hit_single"] = int(diag.get("BLOCK_SINGLE_CAP", 0) or 0)
    counters["cap_hit_industry"] = int(diag.get("BLOCK_INDUSTRY_CAP", 0) or 0)

    # --- 派生字段 ---
    avg_pos = counters["avg_positions"]
    max_pos = counters["max_positions"]
    counters["slots_left"] = round(float(max_pos) - float(avg_pos), 1)

    return sanitize_json(counters)


def ensure_standard_artifacts(
    *,
    results_dir: Path,
    result: dict[str, Any],
    base_cfg: dict[str, Any],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    results_dir.mkdir(parents=True, exist_ok=True)

    perf_obj = {
        "total_return": _safe_float(result.get("total_return")),
        "max_drawdown": _safe_float(result.get("max_drawdown")),
        "cagr": _safe_float(result.get("cagr")),
        "sharpe": _safe_float(result.get("sharpe")),
        "calmar": _safe_float(result.get("calmar")),
        "trades": _safe_int(result.get("trades")),
        "turnover": _safe_float(result.get("turnover")),
    }
    perf_path = results_dir / "perf.json"
    perf_path.write_text(json.dumps(sanitize_json(perf_obj), ensure_ascii=False, indent=2), encoding="utf-8")

    nav_path = _write_nav_csv(results_dir, result)

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
    funnel_path = results_dir / "funnel.csv"
    pd.DataFrame([funnel_obj]).to_csv(funnel_path, index=False)

    reason_path = results_dir / "reason_codes.csv"
    if reason_rows:
        pd.DataFrame(reason_rows).to_csv(reason_path, index=False)
    else:
        pd.DataFrame(columns=["reason_code", "count"]).to_csv(reason_path, index=False)

    config_path = results_dir / "config.json"
    config_path.write_text(
        json.dumps(
            sanitize_json({"base_config": base_cfg, "overrides": overrides}),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    run_meta_obj = {
        "exp_id": str(result.get("exp_id") or ""),
        "status": str(result.get("status") or "OK"),
        "created_at": datetime.now().isoformat(),
        "data": {
            "start": overrides.get("start_date") or base_cfg.get("universe", {}).get("start"),
            "end": overrides.get("end_date") or base_cfg.get("universe", {}).get("end"),
            "benchmark": overrides.get("benchmark") or base_cfg.get("universe", {}).get("benchmark"),
            "compare_symbol": overrides.get("compare_symbol") or base_cfg.get("universe", {}).get("benchmark_compare_symbol"),
            "universe_limit": _safe_int(overrides.get("universe_limit")),
        },
        "code": {
            "engine_mode": str(overrides.get("engine_mode") or "VECTOR_FAST_STRICT"),
            "execution_profile": str(overrides.get("execution_profile") or "tradable"),
            "fast_mode": bool(overrides.get("fast_mode", True)),
        },
        "counters": _build_counters(result, results_dir),
    }
    run_meta_path = results_dir / "run_meta.json"
    run_meta_path.write_text(json.dumps(sanitize_json(run_meta_obj), ensure_ascii=False, indent=2), encoding="utf-8")

    artifacts = {
        "perf": _to_rel(perf_path, results_dir),
        "nav": _to_rel(nav_path, results_dir),
        "funnel": _to_rel(funnel_path, results_dir),
        "reason_codes": _to_rel(reason_path, results_dir),
        "config": _to_rel(config_path, results_dir),
        "run_meta": _to_rel(run_meta_path, results_dir),
    }
    # 如果引擎已写出 trades CSV，也加入 artifacts 映射
    if trades_path.exists():
        artifacts["trades"] = _to_rel(trades_path, results_dir)
    # 如果引擎已写出 daily CSV，也加入 artifacts 映射（供报告生成使用）
    daily_path = results_dir / "portfolio_daily.csv"
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
    manifest_path, manifest_obj = write_manifest(results_dir, out)

    files = dict(out.get("files") or {})
    files["manifest"] = _to_rel(manifest_path, results_dir)
    out["files"] = files
    out["manifest"] = manifest_obj

    if run_profile_summary:
        out["run_profile_summary"] = run_profile_summary

    return sanitize_json(out)
