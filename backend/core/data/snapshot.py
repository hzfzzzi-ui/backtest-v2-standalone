from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import date
from typing import Any

import pandas as pd


@dataclass(slots=True)
class DataSnapshot:
    data_snapshot_id: str
    sources: list[str]
    symbols_hash: str
    date_start: str
    date_end: str
    sql_hash: str
    row_count: int
    min_date: str | None
    max_date: str | None
    checksum: str
    query_meta: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _hash_symbols(symbols: list[str]) -> str:
    payload = "|".join(sorted({s.strip().upper() for s in symbols}))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _df_checksum(df: pd.DataFrame) -> str:
    cols = ["date", "symbol", "close", "volume", "amount"]
    exist = [c for c in cols if c in df.columns]
    if not exist:
        return hashlib.sha256(b"empty").hexdigest()
    stable = df[exist].fillna("<NA>").astype(str)
    # deterministic row/col order
    stable = stable.sort_values(list(stable.columns)).reset_index(drop=True)
    data = stable.to_csv(index=False, header=True, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def build_snapshot(
    df: pd.DataFrame,
    symbols: list[str],
    start: date,
    end: date,
    source_tables: list[str],
    query_meta: list[dict[str, Any]],
) -> DataSnapshot:
    symbols_hash = _hash_symbols(symbols)
    sql_hash = hashlib.sha256(
        json.dumps(query_meta, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    checksum = _df_checksum(df)

    min_date = None
    max_date = None
    if not df.empty and "date" in df.columns:
        min_date = pd.Timestamp(df["date"].min()).date().isoformat()
        max_date = pd.Timestamp(df["date"].max()).date().isoformat()

    base = f"{','.join(sorted(source_tables))}|{symbols_hash}|{start.isoformat()}|{end.isoformat()}|{sql_hash}|{len(df)}|{checksum}"
    snapshot_id = hashlib.sha256(base.encode("utf-8")).hexdigest()

    return DataSnapshot(
        data_snapshot_id=snapshot_id,
        sources=sorted(source_tables),
        symbols_hash=symbols_hash,
        date_start=start.isoformat(),
        date_end=end.isoformat(),
        sql_hash=sql_hash,
        row_count=int(len(df)),
        min_date=min_date,
        max_date=max_date,
        checksum=checksum,
        query_meta=query_meta,
    )
