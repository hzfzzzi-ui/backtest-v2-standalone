from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_INPUT_ROOT = Path("outputs/studies/cn_stock_etf/watch_lagging_deep_dive_shadow_v1")
DEFAULT_OUTPUT_ROOT = Path("outputs/studies/cn_stock_etf/watch_lagging_deconcentration_shadow_v1")
DEFAULT_WINDOWS = ("1626", "1217", "1226", "recent_2526", "turn_202512_202604")


EXCLUSION_CASES: dict[str, dict[str, set[str]]] = {
    "ALL": {"years": set(), "industries": set()},
    "EX_YEAR_2015": {"years": {"2015"}, "industries": set()},
    "EX_INDUSTRY_REAL_ESTATE": {"years": set(), "industries": {"房地产"}},
    "EX_INDUSTRY_COMPUTER": {"years": set(), "industries": {"计算机"}},
    "EX_REAL_ESTATE_COMPUTER": {"years": set(), "industries": {"房地产", "计算机"}},
    "EX_2015_REAL_ESTATE_COMPUTER": {"years": {"2015"}, "industries": {"房地产", "计算机"}},
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(path: str | Path) -> Path:
    raw = Path(path)
    if raw.is_absolute():
        return raw.resolve()
    return (_repo_root() / raw).resolve()


def _read_watch(input_root: Path, window_key: str) -> pd.DataFrame:
    path = input_root / window_key / "watch_lagging_detail.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    frame["year"] = frame.get("year", frame["date"].str.slice(0, 4)).astype(str)
    frame["industry_name"] = frame.get("industry_name", "").fillna("").astype(str)
    for col in ["forward_ret5", "forward_ret20", "mfe20", "mae20", "ret5", "ret20", "close_vs_ma20", "drawdown20"]:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame


def apply_exclusion(frame: pd.DataFrame, *, years: set[str], industries: set[str]) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    mask = pd.Series(True, index=frame.index)
    if years:
        mask &= ~frame["year"].astype(str).isin(years)
    if industries:
        mask &= ~frame["industry_name"].astype(str).isin(industries)
    return frame.loc[mask].copy()


def summarize_case(frame: pd.DataFrame, *, window_key: str, case_name: str, years: set[str], industries: set[str], original_rows: int) -> dict[str, Any]:
    if frame.empty:
        return {
            "window_key": window_key,
            "case": case_name,
            "excluded_years": ";".join(sorted(years)),
            "excluded_industries": ";".join(sorted(industries)),
            "original_rows": original_rows,
            "rows": 0,
            "row_retention_ratio": 0.0,
            "unique_symbols": 0,
            "unique_industries": 0,
            "avg_forward_ret5": None,
            "avg_forward_ret20": None,
            "median_forward_ret20": None,
            "avg_mfe20": None,
            "avg_mae20": None,
            "negative_fwd20_ratio": None,
            "verdict": "inconclusive_empty",
        }
    fwd20 = pd.to_numeric(frame["forward_ret20"], errors="coerce")
    avg = float(fwd20.mean()) if fwd20.notna().any() else None
    neg_ratio = float(fwd20.lt(0.0).mean()) if len(fwd20) else None
    if len(frame) < 30:
        verdict = "inconclusive_small_sample"
    elif avg is not None and avg < -0.02:
        verdict = "still_negative"
    elif avg is not None and avg < 0.0:
        verdict = "weak_negative"
    else:
        verdict = "not_negative_after_exclusion"
    return {
        "window_key": window_key,
        "case": case_name,
        "excluded_years": ";".join(sorted(years)),
        "excluded_industries": ";".join(sorted(industries)),
        "original_rows": original_rows,
        "rows": int(len(frame)),
        "row_retention_ratio": float(len(frame) / original_rows) if original_rows else 0.0,
        "unique_symbols": int(frame["symbol"].nunique()) if "symbol" in frame else 0,
        "unique_industries": int(frame["industry_name"].nunique()) if "industry_name" in frame else 0,
        "avg_forward_ret5": float(pd.to_numeric(frame["forward_ret5"], errors="coerce").mean()) if "forward_ret5" in frame else None,
        "avg_forward_ret20": avg,
        "median_forward_ret20": float(fwd20.median()) if fwd20.notna().any() else None,
        "avg_mfe20": float(pd.to_numeric(frame["mfe20"], errors="coerce").mean()) if "mfe20" in frame else None,
        "avg_mae20": float(pd.to_numeric(frame["mae20"], errors="coerce").mean()) if "mae20" in frame else None,
        "negative_fwd20_ratio": neg_ratio,
        "verdict": verdict,
    }


def build_case_summary(frame: pd.DataFrame, *, window_key: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    original_rows = int(len(frame))
    for case_name, spec in EXCLUSION_CASES.items():
        filtered = apply_exclusion(frame, years=spec["years"], industries=spec["industries"])
        rows.append(
            summarize_case(
                filtered,
                window_key=window_key,
                case_name=case_name,
                years=spec["years"],
                industries=spec["industries"],
                original_rows=original_rows,
            )
        )
    return pd.DataFrame(rows)


def _records(frame: pd.DataFrame, limit: int = 16) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return json.loads(frame.head(limit).to_json(orient="records", force_ascii=False))


def _write_csv(path: Path, frame: pd.DataFrame) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Watch Lagging Deconcentration Shadow V1",
        "",
        "## Scope",
        "",
        "- research_only: true",
        "- baseline_mutation: false",
        "- nav_recompute: false",
        "- target_state: watch_lagging",
        "",
    ]
    for window in summary["windows"]:
        lines.extend([f"## {window['window_key']}", ""])
        for row in window["case_summary"]:
            lines.append(
                "- {case}: rows={rows}/{original_rows}, avg_fwd20={avg_forward_ret20}, verdict={verdict}".format(
                    **{k: row.get(k) for k in row}
                )
            )
        lines.append("")
    lines.extend(
        [
            "## Guardrails",
            "",
            "- If a negative result disappears after excluding one year or two industries, it is not robust enough for AB.",
            "- This is a concentration audit, not a trading rule.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_watch_lagging_deconcentration(
    *,
    input_root: Path = DEFAULT_INPUT_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    windows: tuple[str, ...] = DEFAULT_WINDOWS,
) -> dict[str, Any]:
    input_root = _resolve(input_root)
    output_root = _resolve(output_root)
    summary: dict[str, Any] = {
        "research_only": True,
        "baseline_mutation": False,
        "nav_recompute": False,
        "target_state": "watch_lagging",
        "input_root": str(input_root),
        "windows": [],
        "outputs": {},
    }
    matrix_rows: list[pd.DataFrame] = []
    for window_key in windows:
        watch = _read_watch(input_root, window_key)
        case_summary = build_case_summary(watch, window_key=window_key)
        matrix_rows.append(case_summary)
        window_dir = output_root / window_key
        summary["outputs"][f"{window_key}/case_summary"] = _write_csv(window_dir / "case_summary.csv", case_summary)
        summary["windows"].append(
            {
                "window_key": window_key,
                "case_summary": _records(case_summary, 12),
            }
        )
    matrix = pd.concat(matrix_rows, ignore_index=True) if matrix_rows else pd.DataFrame()
    summary["outputs"]["matrix"] = _write_csv(output_root / "matrix.csv", matrix)
    output_root.mkdir(parents=True, exist_ok=True)
    summary_path = output_root / "summary.json"
    report_path = output_root / "summary.md"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_render_report(summary), encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    summary["report_path"] = str(report_path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch lagging deconcentration shadow")
    parser.add_argument("--input-root", default=str(DEFAULT_INPUT_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--windows", default=",".join(DEFAULT_WINDOWS))
    args = parser.parse_args()
    result = run_watch_lagging_deconcentration(
        input_root=Path(args.input_root),
        output_root=Path(args.output_root),
        windows=tuple(item.strip() for item in args.windows.split(",") if item.strip()),
    )
    print(json.dumps({"summary_path": result["summary_path"], "report_path": result["report_path"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
