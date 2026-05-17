from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from psycopg.rows import dict_row

from backend.api.shared.json_utils import sanitize_json
from backend.core.data import pg_env
from backend.research.csi1000_negative_attribution import normalize_symbol


STUDY_ID = "cn_stock/v4_fundamental_quality_shadow_v1"
DEFAULT_SOURCE_DIR = Path("outputs/baselines/baseline_V10_1")
DEFAULT_OUTPUT_DIR = Path("outputs/studies/cn_stock/v4_fundamental_quality_shadow_v1")
DEFAULT_START = "2016-01-01"
DEFAULT_END = "2026-03-20"

TABLE_PATTERNS = (
    "%fina%",
    "%fundamental%",
    "%finance%",
    "%income%",
    "%balance%",
    "%cashflow%",
    "%daily_basic%",
)

OBSERVATION_COLUMNS = ("ann_date", "publish_date", "pub_date", "disclosure_date")
SNAPSHOT_OBSERVATION_COLUMNS = ("as_of",)
PERIOD_COLUMNS = ("end_date", "report_date", "period", "fiscal_period")
SYMBOL_COLUMNS = ("symbol", "ts_code", "code")

QUALITY_ALIASES: dict[str, tuple[str, ...]] = {
    "roe": ("roe", "roe_dt", "roe_avg", "roe_yearly"),
    "roa": ("roa", "roa2_yearly", "roa_dp"),
    "gross_margin": ("gross_margin", "grossprofit_margin", "grossprofit_margin_ttm"),
    "net_margin": ("net_margin", "netprofit_margin", "netprofit_margin_ttm"),
    "cashflow_to_profit": ("ocf_to_np", "op_cashflow_to_net_profit", "cashflow_to_profit"),
    "leverage": ("debt_ratio", "debt_to_assets", "asset_liab_ratio"),
}


@dataclass(frozen=True)
class TableAudit:
    table_name: str
    row_count: int
    columns: tuple[str, ...]
    symbol_column: str | None
    observation_column: str | None
    period_column: str | None
    quality_columns: dict[str, str]
    pit_safe: bool
    usable: bool
    block_reasons: tuple[str, ...]
    min_observation_date: str | None
    max_observation_date: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "table_name": self.table_name,
            "row_count": self.row_count,
            "columns": list(self.columns),
            "symbol_column": self.symbol_column,
            "observation_column": self.observation_column,
            "period_column": self.period_column,
            "quality_columns": dict(self.quality_columns),
            "pit_safe": self.pit_safe,
            "usable": self.usable,
            "block_reasons": list(self.block_reasons),
            "min_observation_date": self.min_observation_date,
            "max_observation_date": self.max_observation_date,
        }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_path(path: str | Path) -> Path:
    raw = Path(path)
    if raw.is_absolute():
        return raw
    return (_repo_root() / raw).resolve()


def _first_present(columns: set[str], candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def _quality_columns(columns: set[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for component, aliases in QUALITY_ALIASES.items():
        match = _first_present(columns, aliases)
        if match:
            out[component] = match
    return out


def _query_table_names(conn: Any) -> list[str]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name ILIKE ANY(%s)
            ORDER BY table_name
            """,
            (list(TABLE_PATTERNS),),
        )
        return [str(row["table_name"]) for row in cur.fetchall()]


def _query_columns(conn: Any, table_name: str) -> tuple[str, ...]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
            """,
            (table_name,),
        )
        return tuple(str(row["column_name"]) for row in cur.fetchall())


def _count_and_date_range(conn: Any, table_name: str, observation_column: str | None) -> tuple[int, str | None, str | None]:
    with conn.cursor(row_factory=dict_row) as cur:
        if observation_column:
            cur.execute(
                f"""
                SELECT count(*) AS row_count,
                       min({observation_column}) AS min_observation_date,
                       max({observation_column}) AS max_observation_date
                FROM public.{table_name}
                """
            )
        else:
            cur.execute(f"SELECT count(*) AS row_count FROM public.{table_name}")
        row = dict(cur.fetchone() or {})
    return (
        int(row.get("row_count") or 0),
        str(row.get("min_observation_date")) if row.get("min_observation_date") is not None else None,
        str(row.get("max_observation_date")) if row.get("max_observation_date") is not None else None,
    )


def audit_fundamental_tables(conn: Any) -> list[TableAudit]:
    audits: list[TableAudit] = []
    for table_name in _query_table_names(conn):
        columns = _query_columns(conn, table_name)
        column_set = set(columns)
        symbol_column = _first_present(column_set, SYMBOL_COLUMNS)
        observation_column = _first_present(column_set, OBSERVATION_COLUMNS)
        snapshot_observation_column = _first_present(column_set, SNAPSHOT_OBSERVATION_COLUMNS)
        if observation_column is None:
            observation_column = snapshot_observation_column
        period_column = _first_present(column_set, PERIOD_COLUMNS)
        quality_columns = _quality_columns(column_set)
        row_count, min_date, max_date = _count_and_date_range(conn, table_name, observation_column)

        block_reasons: list[str] = []
        if symbol_column is None:
            block_reasons.append("missing_symbol_column")
        if observation_column is None:
            block_reasons.append("missing_observation_date")
        if observation_column in SNAPSHOT_OBSERVATION_COLUMNS:
            block_reasons.append("snapshot_observation_only")
        if period_column is None:
            block_reasons.append("missing_financial_period")
        if len(quality_columns) < 2:
            block_reasons.append("less_than_two_quality_components")
        if row_count <= 0:
            block_reasons.append("empty_table")

        pit_safe = (
            symbol_column is not None
            and observation_column is not None
            and observation_column not in SNAPSHOT_OBSERVATION_COLUMNS
            and period_column is not None
        )
        usable = pit_safe and len(quality_columns) >= 2 and row_count > 0
        audits.append(
            TableAudit(
                table_name=table_name,
                row_count=row_count,
                columns=columns,
                symbol_column=symbol_column,
                observation_column=observation_column,
                period_column=period_column,
                quality_columns=quality_columns,
                pit_safe=pit_safe,
                usable=usable,
                block_reasons=tuple(block_reasons),
                min_observation_date=min_date,
                max_observation_date=max_date,
            )
        )
    return audits


def _parse_meta_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or "{}"))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def load_buy_entries(source_dir: Path, start: str, end: str) -> pd.DataFrame:
    trades_path = source_dir / "portfolio_trades.csv"
    if not trades_path.exists():
        trades_path = source_dir / "orders.csv"
    if not trades_path.exists():
        raise FileNotFoundError(f"missing portfolio_trades.csv/orders.csv under {source_dir}")

    trades = pd.read_csv(trades_path)
    if trades.empty:
        return pd.DataFrame()
    trades["date"] = pd.to_datetime(trades["date"], errors="coerce")
    if "entry_date" in trades.columns:
        trades["entry_date"] = pd.to_datetime(trades["entry_date"], errors="coerce")
    else:
        trades["entry_date"] = pd.NaT
    trades["fill_price"] = pd.to_numeric(trades.get("fill_price"), errors="coerce")
    trades["price"] = pd.to_numeric(trades.get("price"), errors="coerce")
    trades["symbol"] = trades["symbol"].map(normalize_symbol)
    trades["side"] = trades["side"].astype(str).str.upper()
    entries = trades.loc[trades["side"].eq("BUY")].copy()
    if "meta_json" in entries.columns:
        meta = entries["meta_json"].map(_parse_meta_json)
        entries["signal_date"] = meta.map(lambda item: item.get("signal_date"))
        entries["final_score_rank"] = meta.map(lambda item: item.get("final_score_rank"))
        entries["final_score_value"] = meta.map(lambda item: item.get("final_score_value") or item.get("final_score"))
    else:
        entries["signal_date"] = None
        entries["final_score_rank"] = None
        entries["final_score_value"] = None
    entries["signal_date"] = pd.to_datetime(entries["signal_date"], errors="coerce").fillna(entries["date"])
    entries["entry_date"] = entries["date"]
    entries["entry_fill_price"] = entries["fill_price"].fillna(entries["price"])
    start_ts = pd.to_datetime(start)
    end_ts = pd.to_datetime(end)
    entries = entries.loc[(entries["entry_date"] >= start_ts) & (entries["entry_date"] <= end_ts)].copy()

    sells = trades.loc[trades["side"].eq("SELL") & trades["entry_date"].notna()].copy()
    if not sells.empty:
        sells["exit_fill_price"] = sells["fill_price"].fillna(sells["price"])
        sells = (
            sells.sort_values(["symbol", "entry_date", "date"])
            .drop_duplicates(subset=["symbol", "entry_date"], keep="last")
            .rename(columns={"date": "exit_date", "reason_code": "exit_reason_code"})
        )
        entries = entries.merge(
            sells[["symbol", "entry_date", "exit_date", "exit_fill_price", "exit_reason_code"]],
            on=["symbol", "entry_date"],
            how="left",
        )
        entries["exit_return_pct"] = entries["exit_fill_price"] / entries["entry_fill_price"] - 1.0
        entries["hold_days"] = (entries["exit_date"] - entries["entry_date"]).dt.days
    else:
        entries["exit_date"] = pd.NaT
        entries["exit_fill_price"] = np.nan
        entries["exit_reason_code"] = None
        entries["exit_return_pct"] = np.nan
        entries["hold_days"] = np.nan
    keep = [
        "symbol",
        "signal_date",
        "entry_date",
        "exit_date",
        "price",
        "entry_fill_price",
        "exit_fill_price",
        "exit_return_pct",
        "hold_days",
        "value",
        "reason_code",
        "exit_reason_code",
        "final_score_rank",
        "final_score_value",
    ]
    return entries.loc[:, [col for col in keep if col in entries.columns]].reset_index(drop=True)


def compute_quality_score(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    component_cols = [col for col in ("roe", "roa", "gross_margin", "net_margin", "cashflow_to_profit", "leverage") if col in out.columns]
    if not component_cols:
        out["quality_score"] = np.nan
        out["quality_component_count"] = 0
        return out
    score_cols: list[str] = []
    for col in component_cols:
        values = pd.to_numeric(out[col], errors="coerce")
        if col == "leverage":
            ranked = values.rank(pct=True, ascending=False)
        else:
            ranked = values.rank(pct=True, ascending=True)
        score_col = f"{col}_quality_pct"
        out[score_col] = ranked
        score_cols.append(score_col)
    out["quality_component_count"] = out[score_cols].notna().sum(axis=1)
    out["quality_score"] = out[score_cols].mean(axis=1)
    return out


def quality_bucket(value: Any) -> str:
    try:
        number = float(value)
    except Exception:
        return "missing"
    if not np.isfinite(number):
        return "missing"
    if number < 0.25:
        return "q1_low"
    if number < 0.50:
        return "q2_mid_low"
    if number < 0.75:
        return "q3_mid_high"
    return "q4_high"


def _load_usable_quality_rows(conn: Any, audit: TableAudit, symbols: list[str], start: str, end: str) -> pd.DataFrame:
    if not audit.usable or not audit.symbol_column or not audit.observation_column:
        return pd.DataFrame()
    selected: list[str] = [
        f"{audit.symbol_column} AS symbol",
        f"{audit.observation_column} AS observation_date",
    ]
    if audit.period_column:
        selected.append(f"{audit.period_column} AS period_date")
    for component, column in audit.quality_columns.items():
        selected.append(f"{column} AS {component}")
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT {", ".join(selected)}
            FROM public.{audit.table_name}
            WHERE {audit.symbol_column} = ANY(%s)
              AND {audit.observation_column} BETWEEN %s AND %s
            ORDER BY {audit.symbol_column}, {audit.observation_column}
            """,
            (symbols, start, end),
        )
        rows = cur.fetchall()
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["symbol"] = frame["symbol"].map(normalize_symbol)
    frame["observation_date"] = pd.to_datetime(frame["observation_date"], errors="coerce")
    return compute_quality_score(frame.dropna(subset=["symbol", "observation_date"]))


def _join_quality(entries: pd.DataFrame, quality: pd.DataFrame) -> pd.DataFrame:
    if entries.empty or quality.empty:
        return entries.copy()
    entries = entries.copy()
    quality = quality.copy()
    entries["signal_date"] = pd.to_datetime(entries["signal_date"], errors="coerce").astype("datetime64[ns]")
    quality["observation_date"] = pd.to_datetime(quality["observation_date"], errors="coerce").astype("datetime64[ns]")
    chunks: list[pd.DataFrame] = []
    for symbol, entry_group in entries.groupby("symbol", sort=False):
        quality_group = quality.loc[quality["symbol"].eq(symbol)].sort_values("observation_date")
        if quality_group.empty:
            group = entry_group.copy()
            group["quality_score"] = np.nan
            group["quality_bucket"] = "missing"
            chunks.append(group)
            continue
        merged = pd.merge_asof(
            entry_group.sort_values("signal_date"),
            quality_group,
            left_on="signal_date",
            right_on="observation_date",
            by="symbol",
            direction="backward",
        )
        chunks.append(merged)
    out = pd.concat(chunks, ignore_index=True) if chunks else entries.copy()
    out["quality_bucket"] = out["quality_score"].map(quality_bucket)
    return out


def _write_summary(path: Path, payload: dict[str, Any]) -> None:
    status = str(payload.get("status") or "")
    lines = [
        "# V4 fundamental quality shadow",
        "",
        f"- study_id: `{STUDY_ID}`",
        f"- status: `{status}`",
        f"- source: `{payload.get('source_dir')}`",
        f"- window: `{payload.get('start')}` to `{payload.get('end')}`",
        f"- buy_entries: `{payload.get('buy_entries')}`",
        "",
    ]
    if status == "DATA_BLOCKED":
        lines.extend(
            [
                "## Block reason",
                "",
                "No candidate table currently satisfies the PIT fundamental quality contract.",
                "The study did not compute a pseudo-factor from sparse snapshots.",
                "",
                "## Candidate tables",
                "",
            ]
        )
        for item in payload.get("table_audits", []):
            lines.append(
                f"- `{item['table_name']}` rows={item['row_count']} usable={item['usable']} "
                f"reasons={','.join(item['block_reasons']) or 'none'}"
            )
    else:
        lines.extend(
            [
                "## Result",
                "",
                f"- usable_table: `{payload.get('usable_table')}`",
                f"- quality_rows: `{payload.get('quality_rows')}`",
                f"- matched_entries: `{payload.get('matched_entries')}`",
            ]
        )
        bucket_summary = list(payload.get("bucket_summary") or [])
        if bucket_summary:
            lines.extend(
                [
                    "",
                    "## Bucket summary",
                    "",
                    "| bucket | entries | avg_exit_return | median_exit_return | win_rate | avg_hold_days |",
                    "| --- | ---: | ---: | ---: | ---: | ---: |",
                ]
            )
            for item in bucket_summary:
                lines.append(
                    "| {bucket} | {entries} | {avg:.4f} | {median:.4f} | {win:.4f} | {days:.1f} |".format(
                        bucket=item.get("quality_bucket"),
                        entries=item.get("entries"),
                        avg=float(item.get("avg_exit_return_pct") or 0.0),
                        median=float(item.get("median_exit_return_pct") or 0.0),
                        win=float(item.get("win_rate") or 0.0),
                        days=float(item.get("avg_hold_days") or 0.0),
                    )
                )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_shadow(
    *,
    source_dir: str | Path = DEFAULT_SOURCE_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
) -> dict[str, Any]:
    resolved_source = _resolve_path(source_dir)
    resolved_output = _resolve_path(output_dir)
    resolved_output.mkdir(parents=True, exist_ok=True)
    entries = load_buy_entries(resolved_source, start, end)

    with pg_env.connect(autocommit=True) as conn:
        audits = audit_fundamental_tables(conn)
        usable = next((item for item in audits if item.usable), None)
        if usable is None:
            payload = {
                "study_id": STUDY_ID,
                "status": "DATA_BLOCKED",
                "source_dir": str(resolved_source),
                "start": start,
                "end": end,
                "buy_entries": int(len(entries)),
                "unique_symbols": int(entries["symbol"].nunique()) if not entries.empty else 0,
                "table_audits": [item.to_dict() for item in audits],
            }
            (resolved_output / "coverage_audit.json").write_text(
                json.dumps(sanitize_json(payload), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            _write_summary(resolved_output / "summary.md", payload)
            return sanitize_json(payload)

        symbols = sorted(set(entries["symbol"].dropna().astype(str)))
        quality = _load_usable_quality_rows(conn, usable, symbols, "2007-01-01", end)
    joined = _join_quality(entries, quality)
    joined.to_csv(resolved_output / "entry_quality_shadow.csv", index=False, encoding="utf-8")
    bucket_summary = (
        joined.groupby("quality_bucket", dropna=False)
        .agg(
            entries=("symbol", "count"),
            symbols=("symbol", "nunique"),
            matched_entries=("quality_score", lambda item: int(item.notna().sum())),
            avg_quality_score=("quality_score", "mean"),
            avg_exit_return_pct=("exit_return_pct", "mean"),
            median_exit_return_pct=("exit_return_pct", "median"),
            win_rate=("exit_return_pct", lambda item: float((item > 0).mean()) if len(item.dropna()) else np.nan),
            avg_hold_days=("hold_days", "mean"),
        )
        .reset_index()
    )
    bucket_summary.to_csv(resolved_output / "bucket_summary.csv", index=False, encoding="utf-8")
    bucket_records = bucket_summary.replace({np.nan: None}).to_dict(orient="records")
    payload = {
        "study_id": STUDY_ID,
        "status": "READY",
        "source_dir": str(resolved_source),
        "start": start,
        "end": end,
        "buy_entries": int(len(entries)),
        "unique_symbols": int(entries["symbol"].nunique()) if not entries.empty else 0,
        "usable_table": usable.table_name,
        "quality_rows": int(len(quality)),
        "matched_entries": int(joined["quality_score"].notna().sum()),
        "bucket_summary": bucket_records,
        "table_audits": [item.to_dict() for item in audits],
    }
    (resolved_output / "coverage_audit.json").write_text(
        json.dumps(sanitize_json(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_summary(resolved_output / "summary.md", payload)
    return sanitize_json(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run V4 stock-leg fundamental quality shadow audit.")
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    args = parser.parse_args()
    payload = run_shadow(source_dir=args.source_dir, output_dir=args.output_dir, start=args.start, end=args.end)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
