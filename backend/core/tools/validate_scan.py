from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def _is_json(v: str) -> bool:
    try:
        json.loads(v)
        return True
    except Exception:
        return False


def validate_matrix(path: str | Path) -> list[str]:
    p = Path(path)
    if not p.exists():
        return [f"matrix missing: {p}"]
    try:
        df = pd.read_csv(p)
    except Exception as exc:
        return [f"matrix unreadable: {exc}"]

    errs: list[str] = []
    if len(df) != 48:
        errs.append(f"row count != 48, got {len(df)}")
    if int(df["group_id"].nunique()) != len(df):
        errs.append("group_id not unique")

    mode_counts = df["mode"].astype(str).value_counts().to_dict() if "mode" in df.columns else {}
    if mode_counts.get("M1", 0) != 6 or mode_counts.get("M2", 0) != 6 or mode_counts.get("M3", 0) != 36:
        errs.append(f"mode distribution invalid: {mode_counts}")

    for col in ["score", "atr_exit_rate"]:
        if col not in df.columns:
            errs.append(f"missing column: {col}")
        elif df[col].isna().any():
            errs.append(f"column has NaN: {col}")

    for col in ["exit_reason_counts_json", "exit_reason_pcts_json", "atr_triggered_trade_ids_json"]:
        if col not in df.columns:
            errs.append(f"missing column: {col}")
            continue
        bad = df[col].astype(str).map(_is_json).eq(False)
        if bad.any():
            errs.append(f"invalid json in {col}, first row={df.loc[bad.idxmax(), 'group_id']}")

    m1 = df[df["mode"].astype(str) == "M1"] if "mode" in df.columns else pd.DataFrame()
    if not m1.empty:
        trail_na = m1["atr_trail_k"].isna() | m1["atr_trail_k"].astype(str).eq("NA")
        trail_off = m1["enable_atr_trail"].astype(str).str.lower().eq("false")
        bad = ~trail_na | ~trail_off
        if bad.any():
            errs.append("M1 rows invalid atr_trail_k/enable_atr_trail")

    m2 = df[df["mode"].astype(str) == "M2"] if "mode" in df.columns else pd.DataFrame()
    if not m2.empty:
        stop_na = m2["atr_stop_k"].isna() | m2["atr_stop_k"].astype(str).eq("NA")
        stop_off = m2["enable_atr_stop"].astype(str).str.lower().eq("false")
        bad = ~stop_na | ~stop_off
        if bad.any():
            errs.append("M2 rows invalid atr_stop_k/enable_atr_stop")

    return errs


def main() -> None:
    parser = argparse.ArgumentParser(description="validate ATR scan matrix")
    parser.add_argument("--matrix", required=True)
    args = parser.parse_args()
    errs = validate_matrix(args.matrix)
    if errs:
        print(errs[0])
        raise SystemExit(1)
    print("OK")


if __name__ == "__main__":
    main()
