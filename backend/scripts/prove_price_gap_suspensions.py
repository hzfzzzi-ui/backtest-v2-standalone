from __future__ import annotations

import argparse
import contextlib
import csv
import io
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import akshare as ak
except ImportError:  # pragma: no cover
    ak = None


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = ROOT / "outputs" / "ops"


@dataclass(slots=True)
class SuspensionEvent:
    code: str
    name: str
    suspend_start: date
    suspend_end: date
    suspend_expire: str
    suspend_reason: str
    market: str
    expected_resume: date | None


@dataclass(slots=True)
class SupplementalProofEvent:
    code: str
    symbol: str
    suspend_start: date
    suspend_end: date
    proof_source: str
    proof_detail: str
    source_url: str


def _parse_date(value: str | None) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw[:10]).date()
    except ValueError:
        return None


def _load_plan_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [dict(row) for row in reader]
    if not rows:
        raise RuntimeError(f"plan csv is empty: {path}")
    required = {"symbol", "trade_date", "prev_date", "next_date", "gap_days"}
    missing = required - set(rows[0].keys())
    if missing:
        raise RuntimeError(f"plan csv missing columns: {sorted(missing)}")
    return rows


def _load_supplemental_events(path: Path) -> list[SupplementalProofEvent]:
    with path.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return []
    required = {"symbol", "start_date", "end_date", "proof_source", "proof_detail"}
    missing = required - set(rows[0].keys())
    if missing:
        raise RuntimeError(f"supplemental evidence missing columns: {sorted(missing)}")
    events: list[SupplementalProofEvent] = []
    for row in rows:
        symbol = str(row.get("symbol") or "").strip().lower()
        start_day = _parse_date(str(row.get("start_date") or ""))
        end_day = _parse_date(str(row.get("end_date") or ""))
        if not symbol or start_day is None or end_day is None:
            continue
        events.append(
            SupplementalProofEvent(
                code=_symbol_to_code(symbol),
                symbol=symbol,
                suspend_start=start_day,
                suspend_end=end_day,
                proof_source=str(row.get("proof_source") or "supplemental_evidence").strip() or "supplemental_evidence",
                proof_detail=str(row.get("proof_detail") or "").strip(),
                source_url=str(row.get("source_url") or "").strip(),
            )
        )
    return events


def _symbol_to_code(symbol: str) -> str:
    raw = str(symbol or "").strip().lower()
    if len(raw) >= 8 and raw[:2] in {"sh", "sz", "bj"}:
        return raw[2:8]
    if len(raw) >= 6 and raw[-6:].isdigit():
        return raw[-6:]
    return raw


def _tx_symbol(symbol: str) -> str:
    raw = str(symbol or "").strip().lower()
    if raw.startswith(("sh", "sz", "bj")):
        return raw
    code = _symbol_to_code(raw)
    if code.startswith(("6", "9")):
        return f"sh{code}"
    return f"sz{code}"


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, tuple):
        return [_jsonable(v) for v in obj]
    if hasattr(obj, "item"):
        try:
            return obj.item()
        except Exception:
            pass
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    return obj


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


@contextlib.contextmanager
def _suppress_output():
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        yield


def _fetch_em_suspensions(source_date: str) -> list[SuspensionEvent]:
    if ak is None:  # pragma: no cover
        raise RuntimeError("akshare is required")
    with _suppress_output():
        df = ak.stock_tfp_em(date=source_date)
    code_col = "\u4ee3\u7801"
    name_col = "\u540d\u79f0"
    start_col = "\u505c\u724c\u65f6\u95f4"
    end_col = "\u505c\u724c\u622a\u6b62\u65f6\u95f4"
    expire_col = "\u505c\u724c\u671f\u9650"
    reason_col = "\u505c\u724c\u539f\u56e0"
    market_col = "\u6240\u5c5e\u5e02\u573a"
    resume_col = "\u9884\u8ba1\u590d\u724c\u65f6\u95f4"
    for col in [code_col, start_col]:
        if col not in df.columns:
            raise RuntimeError(f"unexpected Eastmoney suspension columns: {list(df.columns)}")
    events: list[SuspensionEvent] = []
    for row in df.to_dict(orient="records"):
        start = _parse_date(str(row.get(start_col) or ""))
        if start is None:
            continue
        end = _parse_date(str(row.get(end_col) or ""))
        expected_resume = _parse_date(str(row.get(resume_col) or ""))
        effective_end = end
        if effective_end is None and expected_resume is not None:
            effective_end = expected_resume - timedelta(days=1)
        if effective_end is None or effective_end < start:
            effective_end = start
        events.append(
            SuspensionEvent(
                code=str(row.get(code_col) or "").strip().zfill(6),
                name=str(row.get(name_col) or "").strip(),
                suspend_start=start,
                suspend_end=effective_end,
                suspend_expire=str(row.get(expire_col) or "").strip(),
                suspend_reason=str(row.get(reason_col) or "").strip(),
                market=str(row.get(market_col) or "").strip(),
                expected_resume=expected_resume,
            )
        )
    return events


def _fetch_tx_trade_dates(symbol: str, start: date, end: date) -> tuple[set[str], str]:
    if ak is None:  # pragma: no cover
        raise RuntimeError("akshare is required")
    tx_symbol = _tx_symbol(symbol)
    try:
        with _suppress_output():
            df = ak.stock_zh_a_hist_tx(
                symbol=tx_symbol,
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                adjust="",
            )
    except Exception as exc:
        return set(), f"error:{type(exc).__name__}"
    if "date" not in df.columns:
        return set(), "missing_date_column"
    dates = {str(v).strip()[:10] for v in df["date"].tolist() if str(v).strip()}
    return dates, "ok"


def _segment_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("symbol") or "").lower(),
        str(row.get("prev_date") or ""),
        str(row.get("next_date") or ""),
        str(row.get("gap_days") or ""),
    )


def _event_to_detail(event: SuspensionEvent) -> str:
    return (
        f"{event.code}:{event.suspend_start.isoformat()}~{event.suspend_end.isoformat()}"
        f"|{event.suspend_expire or '-'}|{event.suspend_reason or '-'}"
    )


def _supplemental_to_detail(event: SupplementalProofEvent) -> str:
    detail = (
        f"{event.code}:{event.suspend_start.isoformat()}~{event.suspend_end.isoformat()}"
        f"|{event.proof_detail or '-'}"
    )
    if event.source_url:
        detail = f"{detail}|{event.source_url}"
    return detail


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prove whether price-gap repair candidates are true suspension rows using external evidence."
    )
    parser.add_argument("--plan-csv", required=True, help="repair_plan_sample.csv or equivalent per-row gap plan")
    parser.add_argument("--source-date", default="20100101", help="Eastmoney history snapshot seed date, e.g. 20100101")
    parser.add_argument("--supplemental-evidence-csv", default="", help="optional supplemental proof csv with official/manual evidence")
    parser.add_argument("--output-dir", default="", help="output directory")
    args = parser.parse_args()

    plan_path = Path(args.plan_csv)
    plan_rows = _load_plan_rows(plan_path)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output_dir) if str(args.output_dir).strip() else (DEFAULT_OUTPUT_ROOT / f"price_gap_proof_{ts}")
    out_dir.mkdir(parents=True, exist_ok=True)

    events = _fetch_em_suspensions(str(args.source_date))
    events_by_code: dict[str, list[SuspensionEvent]] = defaultdict(list)
    for event in events:
        events_by_code[event.code].append(event)

    supplemental_events: list[SupplementalProofEvent] = []
    if str(args.supplemental_evidence_csv).strip():
        supplemental_events = _load_supplemental_events(Path(args.supplemental_evidence_csv))
    supplemental_by_code: dict[str, list[SupplementalProofEvent]] = defaultdict(list)
    for event in supplemental_events:
        supplemental_by_code[event.code].append(event)

    symbol_ranges: dict[str, tuple[date, date]] = {}
    for row in plan_rows:
        symbol = str(row.get("symbol") or "").lower()
        trade_day = _parse_date(str(row.get("trade_date") or ""))
        if trade_day is None:
            continue
        cur = symbol_ranges.get(symbol)
        if cur is None:
            symbol_ranges[symbol] = (trade_day, trade_day)
        else:
            symbol_ranges[symbol] = (min(cur[0], trade_day), max(cur[1], trade_day))

    tx_dates_by_symbol: dict[str, set[str]] = {}
    tx_status_by_symbol: dict[str, str] = {}
    for symbol, (start_day, end_day) in sorted(symbol_ranges.items()):
        dates, status = _fetch_tx_trade_dates(symbol, start_day - timedelta(days=7), end_day + timedelta(days=7))
        tx_dates_by_symbol[symbol] = dates
        tx_status_by_symbol[symbol] = status

    classified_rows: list[dict[str, Any]] = []
    for row in plan_rows:
        symbol = str(row.get("symbol") or "").lower()
        code = _symbol_to_code(symbol)
        trade_day = _parse_date(str(row.get("trade_date") or ""))
        if trade_day is None:
            continue
        trade_day_str = trade_day.isoformat()
        tx_dates = tx_dates_by_symbol.get(symbol, set())
        tx_status = tx_status_by_symbol.get(symbol, "missing")
        matched_events = [
            event for event in events_by_code.get(code, []) if event.suspend_start <= trade_day <= event.suspend_end
        ]
        supplemental_matches = [
            event for event in supplemental_by_code.get(code, []) if event.suspend_start <= trade_day <= event.suspend_end
        ]
        if matched_events:
            proof_status = "proven"
            proof_source = "eastmoney_suspend_history"
            proof_detail = " ; ".join(_event_to_detail(event) for event in matched_events[:5])
        elif supplemental_matches:
            proof_status = "proven"
            proof_source = str(supplemental_matches[0].proof_source or "supplemental_evidence")
            proof_detail = " ; ".join(_supplemental_to_detail(event) for event in supplemental_matches[:5])
        elif trade_day_str in tx_dates:
            proof_status = "rejected"
            proof_source = "tx_daily_history"
            proof_detail = f"{code}:{trade_day_str} present in tx daily history"
        else:
            proof_status = "uncertain"
            proof_source = "none"
            if tx_status != "ok":
                proof_detail = f"no suspension match; tx fetch {tx_status}"
            else:
                proof_detail = "no Eastmoney suspension match; no tx daily bar on gap day"

        classified_rows.append(
            {
                **row,
                "code": code,
                "proof_status": proof_status,
                "proof_source": proof_source,
                "proof_detail": proof_detail,
                "tx_fetch_status": tx_status,
                "tx_trade_date_present": trade_day_str in tx_dates,
                "em_match_count": len(matched_events),
                "supplemental_match_count": len(supplemental_matches),
            }
        )

    segments: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in classified_rows:
        segments[_segment_key(row)].append(row)

    segment_rows: list[dict[str, Any]] = []
    for key, rows in sorted(segments.items()):
        status_counts = defaultdict(int)
        for row in rows:
            status_counts[str(row["proof_status"])] += 1
        if status_counts.get("proven", 0) == len(rows):
            segment_status = "proven"
        elif status_counts.get("rejected", 0) == len(rows):
            segment_status = "rejected"
        elif status_counts.get("proven", 0) > 0 and status_counts.get("uncertain", 0) > 0:
            segment_status = "partial"
        elif status_counts.get("rejected", 0) > 0 and status_counts.get("uncertain", 0) > 0:
            segment_status = "partial"
        elif status_counts.get("proven", 0) > 0 and status_counts.get("rejected", 0) > 0:
            segment_status = "conflict"
        else:
            segment_status = "uncertain"
        sample_detail = next((str(r["proof_detail"]) for r in rows if str(r["proof_status"]) != "uncertain"), str(rows[0]["proof_detail"]))
        segment_rows.append(
            {
                "symbol": key[0],
                "prev_date": key[1],
                "next_date": key[2],
                "gap_days": key[3],
                "missing_rows": len(rows),
                "segment_status": segment_status,
                "proven_rows": status_counts.get("proven", 0),
                "uncertain_rows": status_counts.get("uncertain", 0),
                "rejected_rows": status_counts.get("rejected", 0),
                "sample_detail": sample_detail,
            }
        )

    proven_rows = [row for row in classified_rows if row["proof_status"] == "proven"]
    uncertain_rows = [row for row in classified_rows if row["proof_status"] == "uncertain"]
    rejected_rows = [row for row in classified_rows if row["proof_status"] == "rejected"]

    summary = {
        "scope": {
            "plan_csv": str(plan_path),
            "source_date": str(args.source_date),
            "supplemental_evidence_csv": str(args.supplemental_evidence_csv or ""),
            "rows_total": len(classified_rows),
            "symbols_total": len(symbol_ranges),
            "segments_total": len(segment_rows),
        },
        "row_status_counts": {
            "proven": len(proven_rows),
            "uncertain": len(uncertain_rows),
            "rejected": len(rejected_rows),
        },
        "segment_status_counts": dict(pd.Series([row["segment_status"] for row in segment_rows]).value_counts()) if segment_rows else {},
        "tx_fetch_status_counts": dict(pd.Series(list(tx_status_by_symbol.values())).value_counts()) if tx_status_by_symbol else {},
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    (out_dir / "summary.json").write_text(json.dumps(_jsonable(summary), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(out_dir / "proven_rows.csv", proven_rows)
    _write_csv(out_dir / "uncertain_rows.csv", uncertain_rows)
    _write_csv(out_dir / "rejected_rows.csv", rejected_rows)
    _write_csv(out_dir / "segment_proof.csv", segment_rows)

    print(json.dumps(_jsonable({"output_dir": str(out_dir), **summary}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
