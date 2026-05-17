from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from backend.core.tools.runtime_data_access import load_runtime_data_access


DEFAULT_INPUT_ROOT = Path(
    "outputs/studies/cn_stock_etf/cn_stock_style_industry_state_switch_shadow_v1"
)
DEFAULT_OUTPUT_ROOT = Path(
    "outputs/studies/cn_stock_etf/weak_industry_stock_state_shadow_v1"
)
DEFAULT_VARIANT = "M1_STYLE_STATE"
DEFAULT_WINDOWS = ("1626", "1217", "1226", "recent_2526", "turn_202512_202604")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(path: str | Path) -> Path:
    raw = Path(path)
    if raw.is_absolute():
        return raw.resolve()
    return (_repo_root() / raw).resolve()


def normalize_symbol(value: Any) -> str:
    text = str(value or "").strip().lower().replace(".", "")
    if not text:
        return ""
    if len(text) == 8 and text[:2] in {"sh", "sz", "bj"}:
        return text
    if len(text) == 8 and text[-2:] in {"sh", "sz", "bj"}:
        return text[-2:] + text[:6]
    if len(text) == 6 and text[0] in {"0", "2", "3"}:
        return "sz" + text
    if len(text) == 6 and text[0] in {"6", "5", "9"}:
        return "sh" + text
    return text


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
        frame = frame.loc[frame["date"].notna()].copy()
    return frame


def _explode_held_symbols(held_industry: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if held_industry.empty:
        return pd.DataFrame()
    for row in held_industry.itertuples(index=False):
        symbols = [normalize_symbol(item) for item in str(getattr(row, "held_symbols", "") or "").split(";")]
        for symbol in [item for item in symbols if item]:
            rows.append(
                {
                    "date": pd.Timestamp(getattr(row, "date")).normalize(),
                    "symbol": symbol,
                    "industry_index_code": str(getattr(row, "industry_index_code", "") or ""),
                    "industry_name": str(getattr(row, "industry_name", "") or ""),
                    "industry_health_label": str(getattr(row, "industry_health_label", "") or ""),
                    "industry_ret20": getattr(row, "ret20", pd.NA),
                    "industry_ret60": getattr(row, "ret60", pd.NA),
                }
            )
    return pd.DataFrame(rows)


def _build_industry_weak_duration(industry_daily: pd.DataFrame) -> pd.DataFrame:
    if industry_daily.empty:
        return pd.DataFrame(columns=["date", "industry_index_code", "industry_weak_duration"])
    frame = industry_daily.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.loc[frame["date"].notna()].copy()
    frame["industry_index_code"] = frame["industry_index_code"].astype(str)
    frame["is_weak"] = frame["industry_health_label"].astype(str).eq("weak")
    out: list[pd.DataFrame] = []
    for _, group in frame.sort_values(["industry_index_code", "date"]).groupby("industry_index_code"):
        weak = group["is_weak"].astype(bool)
        reset = (~weak).cumsum()
        duration = weak.groupby(reset).cumsum().astype(int)
        tmp = group.loc[:, ["date", "industry_index_code"]].copy()
        tmp["industry_weak_duration"] = duration.where(weak, 0).astype(int)
        out.append(tmp)
    if not out:
        return pd.DataFrame(columns=["date", "industry_index_code", "industry_weak_duration"])
    return pd.concat(out, ignore_index=True)


def _load_ohlcv_from_provider(symbols: list[str], start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame()
    access = load_runtime_data_access(asset_scope="cn_a_equity")
    return access.provider.load_ohlcv_daily(
        sorted(set(symbols)),
        start.date(),
        end.date(),
        source="weak_industry_stock_state_shadow",
    )


def _prepare_price_features(ohlcv: pd.DataFrame) -> pd.DataFrame:
    if ohlcv.empty:
        return pd.DataFrame()
    frame = ohlcv.copy()
    if "trade_date" in frame.columns and "date" not in frame.columns:
        frame.rename(columns={"trade_date": "date"}, inplace=True)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["symbol"] = frame["symbol"].map(normalize_symbol)
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    if "high" not in frame.columns:
        frame["high"] = frame["close"]
    if "low" not in frame.columns:
        frame["low"] = frame["close"]
    frame["high"] = pd.to_numeric(frame["high"], errors="coerce").fillna(frame["close"])
    frame["low"] = pd.to_numeric(frame["low"], errors="coerce").fillna(frame["close"])
    frame = frame.loc[frame["date"].notna() & frame["symbol"].ne("") & frame["close"].gt(0)].copy()
    frame.sort_values(["symbol", "date"], inplace=True)

    parts: list[pd.DataFrame] = []
    for _, group in frame.groupby("symbol", sort=False):
        group = group.copy().reset_index(drop=True)
        close = group["close"]
        group["ret5"] = close / close.shift(5) - 1.0
        group["ret10"] = close / close.shift(10) - 1.0
        group["ret20"] = close / close.shift(20) - 1.0
        ma20 = close.rolling(20, min_periods=10).mean()
        group["close_vs_ma20"] = close / ma20 - 1.0
        group["drawdown20"] = close / close.rolling(20, min_periods=10).max() - 1.0
        for horizon in (5, 20):
            future_close = close.shift(-horizon)
            group[f"forward_ret{horizon}"] = future_close / close - 1.0
            future_high = pd.concat([group["high"].shift(-i) for i in range(1, horizon + 1)], axis=1).max(axis=1)
            future_low = pd.concat([group["low"].shift(-i) for i in range(1, horizon + 1)], axis=1).min(axis=1)
            group[f"mfe{horizon}"] = future_high / close - 1.0
            group[f"mae{horizon}"] = future_low / close - 1.0
        parts.append(group)
    return pd.concat(parts, ignore_index=True)


def build_position_state_detail(
    *,
    held_industry: pd.DataFrame,
    industry_daily: pd.DataFrame,
    ohlcv: pd.DataFrame,
) -> pd.DataFrame:
    positions = _explode_held_symbols(held_industry)
    if positions.empty:
        return pd.DataFrame()
    duration = _build_industry_weak_duration(industry_daily)
    positions = positions.merge(duration, on=["date", "industry_index_code"], how="left")
    prices = _prepare_price_features(ohlcv)
    if prices.empty:
        return positions
    keep_cols = [
        "date",
        "symbol",
        "close",
        "ret5",
        "ret10",
        "ret20",
        "close_vs_ma20",
        "drawdown20",
        "forward_ret5",
        "forward_ret20",
        "mfe5",
        "mae5",
        "mfe20",
        "mae20",
    ]
    positions = positions.merge(prices.loc[:, keep_cols], on=["date", "symbol"], how="left")
    positions["industry_is_weak"] = positions["industry_health_label"].astype(str).eq("weak")
    positions["stock_strong_flag"] = (
        pd.to_numeric(positions.get("ret20"), errors="coerce").gt(0.0)
        & pd.to_numeric(positions.get("close_vs_ma20"), errors="coerce").gt(0.0)
    )
    positions["stock_weak_confirmed_flag"] = (
        pd.to_numeric(positions.get("ret10"), errors="coerce").lt(0.0)
        & pd.to_numeric(positions.get("ret20"), errors="coerce").lt(0.0)
        & pd.to_numeric(positions.get("close_vs_ma20"), errors="coerce").lt(0.0)
    )
    positions["industry_just_weak_flag"] = (
        positions["industry_is_weak"] & pd.to_numeric(positions.get("industry_weak_duration"), errors="coerce").between(1, 3)
    )
    positions["industry_persistent_weak_flag"] = (
        positions["industry_is_weak"] & pd.to_numeric(positions.get("industry_weak_duration"), errors="coerce").ge(10)
    )
    positions["weak_then_repaired_flag"] = (
        positions["industry_is_weak"]
        & (
            pd.to_numeric(positions.get("forward_ret20"), errors="coerce").gt(0.0)
            | pd.to_numeric(positions.get("mfe20"), errors="coerce").gt(0.08)
        )
    )
    positions["stage_label"] = "not_industry_weak"
    positions.loc[positions["industry_is_weak"] & positions["stock_strong_flag"], "stage_label"] = "G1_INDUSTRY_WEAK_STOCK_STRONG"
    positions.loc[positions["industry_is_weak"] & positions["stock_weak_confirmed_flag"], "stage_label"] = "G2_INDUSTRY_WEAK_STOCK_WEAK"
    positions.loc[
        positions["industry_is_weak"] & ~(positions["stock_strong_flag"] | positions["stock_weak_confirmed_flag"]),
        "stage_label",
    ] = "G0_INDUSTRY_WEAK_STOCK_MIXED"
    positions["date"] = pd.to_datetime(positions["date"]).dt.strftime("%Y-%m-%d")
    return positions


def _summary_by(frame: pd.DataFrame, label_col: str) -> pd.DataFrame:
    if frame.empty or label_col not in frame.columns:
        return pd.DataFrame()
    work = frame.copy()
    work[label_col] = work[label_col].fillna("unknown").astype(str)
    numeric_cols = ["ret20", "close_vs_ma20", "forward_ret5", "forward_ret20", "mfe20", "mae20"]
    agg: dict[str, tuple[str, str]] = {
        "rows": ("symbol", "count"),
        "unique_symbols": ("symbol", "nunique"),
        "avg_industry_weak_duration": ("industry_weak_duration", "mean"),
    }
    for col in numeric_cols:
        if col in work.columns:
            agg[f"avg_{col}"] = (col, "mean")
            agg[f"median_{col}"] = (col, "median")
    out = work.groupby(label_col, dropna=False).agg(**agg).reset_index().rename(columns={label_col: "label"})
    return out.sort_values(["avg_forward_ret20", "rows"], ascending=[True, False]).reset_index(drop=True)


def build_flag_summary(detail: pd.DataFrame) -> pd.DataFrame:
    if detail.empty:
        return pd.DataFrame()
    flag_cols = [
        "industry_just_weak_flag",
        "industry_persistent_weak_flag",
        "stock_strong_flag",
        "stock_weak_confirmed_flag",
        "weak_then_repaired_flag",
    ]
    rows: list[dict[str, Any]] = []
    for flag in flag_cols:
        if flag not in detail.columns:
            continue
        sub = detail.loc[detail[flag].fillna(False).astype(bool)].copy()
        if sub.empty:
            rows.append({"flag": flag, "rows": 0, "unique_symbols": 0})
            continue
        rows.append(
            {
                "flag": flag,
                "rows": int(len(sub)),
                "unique_symbols": int(sub["symbol"].nunique()),
                "avg_ret20": float(pd.to_numeric(sub["ret20"], errors="coerce").mean()),
                "avg_forward_ret5": float(pd.to_numeric(sub["forward_ret5"], errors="coerce").mean()),
                "avg_forward_ret20": float(pd.to_numeric(sub["forward_ret20"], errors="coerce").mean()),
                "avg_mfe20": float(pd.to_numeric(sub["mfe20"], errors="coerce").mean()),
                "avg_mae20": float(pd.to_numeric(sub["mae20"], errors="coerce").mean()),
            }
        )
    return pd.DataFrame(rows)


def _records(frame: pd.DataFrame, limit: int = 12) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return json.loads(frame.head(limit).to_json(orient="records", force_ascii=False))


def _write_csv(path: Path, frame: pd.DataFrame) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Weak Industry + Stock State Shadow V1",
        "",
        "## Scope",
        "",
        "- research_only: true",
        "- baseline_mutation: false",
        "- nav_recompute: false",
        "- question: is weak industry exposure an early warning or post-loss attribution?",
        "",
    ]
    for window in summary["windows"]:
        lines.extend([f"## {window['window_key']}", ""])
        lines.append(f"- rows: {window['rows']}")
        lines.append(f"- weak rows: {window['weak_rows']}")
        lines.append(f"- missing price rows: {window['missing_price_rows']}")
        lines.append("")
        lines.append("Stage summary:")
        for row in window["stage_summary"]:
            lines.append(
                "- {label}: rows={rows}, avg_fwd20={avg_forward_ret20}, avg_mfe20={avg_mfe20}, avg_mae20={avg_mae20}".format(
                    **{k: row.get(k) for k in row}
                )
            )
        lines.append("")
        lines.append("Flag summary:")
        for row in window["flag_summary"]:
            lines.append(
                "- {flag}: rows={rows}, avg_fwd20={avg_forward_ret20}, avg_mfe20={avg_mfe20}, avg_mae20={avg_mae20}".format(
                    **{k: row.get(k) for k in row}
                )
            )
        lines.append("")
    lines.extend(
        [
            "## Guardrails",
            "",
            "- This is a position-state audit, not an executable sell rule.",
            "- Forward return, MFE, and MAE are outcome fields used only for evaluation.",
            "- A runtime AB is only justified if G2 is consistently worse than G1/G5 across windows.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_weak_industry_stock_state_shadow(
    *,
    input_root: Path = DEFAULT_INPUT_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    windows: tuple[str, ...] = DEFAULT_WINDOWS,
    variant: str = DEFAULT_VARIANT,
    ohlcv_csv: Path | None = None,
) -> dict[str, Any]:
    input_root = _resolve(input_root)
    output_root = _resolve(output_root)
    summary: dict[str, Any] = {
        "research_only": True,
        "baseline_mutation": False,
        "nav_recompute": False,
        "input_root": str(input_root),
        "variant": variant,
        "windows": [],
        "outputs": {},
    }
    csv_ohlcv = _read_csv(_resolve(ohlcv_csv)) if ohlcv_csv else pd.DataFrame()
    for window_key in windows:
        machine = input_root / window_key / variant / "machine"
        held_industry = _read_csv(machine / "rotation_pressure_held_industry_daily.csv")
        industry_daily = _read_csv(machine / "industry_health_by_industry_daily.csv")
        positions = _explode_held_symbols(held_industry)
        if positions.empty:
            detail = pd.DataFrame()
        else:
            start = pd.to_datetime(positions["date"]).min() - timedelta(days=120)
            end = pd.to_datetime(positions["date"]).max() + timedelta(days=45)
            symbols = sorted(positions["symbol"].dropna().map(normalize_symbol).unique().tolist())
            if csv_ohlcv.empty:
                ohlcv = _load_ohlcv_from_provider(symbols, start, end)
            else:
                ohlcv = csv_ohlcv.copy()
            detail = build_position_state_detail(held_industry=held_industry, industry_daily=industry_daily, ohlcv=ohlcv)
        stage_summary = _summary_by(detail, "stage_label")
        flag_summary = build_flag_summary(detail)
        window_dir = output_root / window_key
        summary["outputs"][f"{window_key}/position_state_detail"] = _write_csv(window_dir / "position_state_detail.csv", detail)
        summary["outputs"][f"{window_key}/stage_summary"] = _write_csv(window_dir / "stage_summary.csv", stage_summary)
        summary["outputs"][f"{window_key}/flag_summary"] = _write_csv(window_dir / "flag_summary.csv", flag_summary)
        summary["windows"].append(
            {
                "window_key": window_key,
                "rows": int(len(detail)),
                "weak_rows": int(detail["industry_is_weak"].sum()) if "industry_is_weak" in detail else 0,
                "missing_price_rows": int(detail["close"].isna().sum()) if "close" in detail else int(len(detail)),
                "stage_summary": _records(stage_summary, 12),
                "flag_summary": _records(flag_summary, 12),
            }
        )
    output_root.mkdir(parents=True, exist_ok=True)
    summary_path = output_root / "summary.json"
    report_path = output_root / "summary.md"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_render_report(summary), encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    summary["report_path"] = str(report_path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Weak industry + stock state shadow audit")
    parser.add_argument("--input-root", default=str(DEFAULT_INPUT_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--variant", default=DEFAULT_VARIANT)
    parser.add_argument("--windows", default=",".join(DEFAULT_WINDOWS))
    parser.add_argument("--ohlcv-csv", default="")
    args = parser.parse_args()
    result = run_weak_industry_stock_state_shadow(
        input_root=Path(args.input_root),
        output_root=Path(args.output_root),
        windows=tuple(item.strip() for item in args.windows.split(",") if item.strip()),
        variant=args.variant,
        ohlcv_csv=Path(args.ohlcv_csv) if args.ohlcv_csv else None,
    )
    print(json.dumps({"summary_path": result["summary_path"], "report_path": result["report_path"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
