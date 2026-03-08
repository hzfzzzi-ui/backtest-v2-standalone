from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = ROOT / "outputs" / "ops"
DEFAULT_CONFIG_PATH = ROOT / "backend" / "configs" / "pams_cn_pg.json"


@dataclass(slots=True)
class DbSettings:
    host: str
    port: int
    dbname: str
    user: str
    password: str


def _load_env_file() -> dict[str, str]:
    env_path = ROOT / ".env"
    out: dict[str, str] = {}
    if not env_path.exists():
        return out
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def _load_db_settings() -> DbSettings:
    file_env = _load_env_file()
    cfg = {}
    if DEFAULT_CONFIG_PATH.exists():
        cfg = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8-sig"))
    db_cfg = dict(cfg.get("db") or {})
    return DbSettings(
        host=str(os.environ.get("PGHOST") or os.environ.get("PAMS_PG_HOST") or db_cfg.get("host") or "pams-postgres"),
        port=int(os.environ.get("PGPORT") or os.environ.get("PAMS_PG_PORT") or db_cfg.get("port") or 5432),
        dbname=str(os.environ.get("PGDATABASE") or os.environ.get("PAMS_PG_DBNAME") or db_cfg.get("dbname") or "pams"),
        user=str(os.environ.get("PGUSER") or os.environ.get("PAMS_PG_USER") or db_cfg.get("user") or "pams"),
        password=str(
            os.environ.get("PGPASSWORD")
            or os.environ.get("PAMS_PG_PASSWORD")
            or file_env.get("POSTGRES_PASSWORD")
            or db_cfg.get("password")
            or ""
        ),
    )


def _connect():
    if psycopg is None:  # pragma: no cover
        raise RuntimeError("psycopg is required")
    db = _load_db_settings()
    return psycopg.connect(
        host=db.host,
        port=db.port,
        dbname=db.dbname,
        user=db.user,
        password=db.password,
        autocommit=False,
    )


def _read_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise RuntimeError(f"input csv is empty: {path}")
    required = {"symbol", "market", "trade_date", "fill_price", "fill_adj_factor", "proof_status"}
    missing = required - set(rows[0].keys())
    if missing:
        raise RuntimeError(f"input csv missing columns: {sorted(missing)}")
    out: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("proof_status") or "").strip().lower() != "proven":
            continue
        out.append(
            {
                "symbol": str(row.get("symbol") or "").strip().lower(),
                "market": str(row.get("market") or "").strip(),
                "trade_date": str(row.get("trade_date") or "").strip(),
                "fill_price": float(row.get("fill_price") or 0.0),
                "fill_adj_factor": float(row.get("fill_adj_factor") or 0.0),
                "proof_detail": str(row.get("proof_detail") or "").strip(),
            }
        )
    if not out:
        raise RuntimeError(f"no proven rows found in {path}")
    return out


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Insert only proven suspension backfill rows into pams_ohlcv_daily")
    parser.add_argument("--input-csv", required=True, help="proven_rows.csv from prove_price_gap_suspensions.py")
    parser.add_argument("--apply", action="store_true", help="actually write rows into database")
    parser.add_argument("--output-dir", default="", help="output directory")
    args = parser.parse_args()

    rows = _read_rows(Path(args.input_csv))
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output_dir) if str(args.output_dir).strip() else (DEFAULT_OUTPUT_ROOT / f"price_gap_apply_{ts}")
    out_dir.mkdir(parents=True, exist_ok=True)

    check_sql = """
select symbol, market, trade_date, coalesce(is_suspended, false) as is_suspended
from pams_ohlcv_daily
where symbol = %s and market = %s and trade_date = %s::date
"""
    insert_sql = """
insert into pams_ohlcv_daily (
    symbol, market, trade_date, open, high, low, close, volume, turnover, adj_factor, limit_up, limit_down, is_suspended
) values (
    %s, %s, %s::date, %s, %s, %s, %s, 0, 0, %s, null, null, true
)
on conflict (symbol, market, trade_date) do nothing
returning symbol, market, trade_date
"""

    inserted: list[dict[str, Any]] = []
    already_present: list[dict[str, Any]] = []
    skipped_conflict: list[dict[str, Any]] = []

    with _connect() as conn:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(check_sql, [row["symbol"], row["market"], row["trade_date"]])
                exists = cur.fetchone()
                if exists is not None:
                    already_present.append(
                        {
                            "symbol": row["symbol"],
                            "market": row["market"],
                            "trade_date": row["trade_date"],
                            "proof_detail": row["proof_detail"],
                            "is_suspended": bool(exists[3]),
                        }
                    )
                    continue
                cur.execute(
                    insert_sql,
                    [
                        row["symbol"],
                        row["market"],
                        row["trade_date"],
                        row["fill_price"],
                        row["fill_price"],
                        row["fill_price"],
                        row["fill_price"],
                        row["fill_adj_factor"],
                    ],
                )
                created = cur.fetchone()
                if created is None:
                    skipped_conflict.append(
                        {
                            "symbol": row["symbol"],
                            "market": row["market"],
                            "trade_date": row["trade_date"],
                            "proof_detail": row["proof_detail"],
                        }
                    )
                else:
                    inserted.append(
                        {
                            "symbol": row["symbol"],
                            "market": row["market"],
                            "trade_date": row["trade_date"],
                            "proof_detail": row["proof_detail"],
                        }
                    )
            if args.apply:
                conn.commit()
            else:
                conn.rollback()

    summary = {
        "input_csv": str(Path(args.input_csv)),
        "rows_total": len(rows),
        "already_present": len(already_present),
        "inserted": len(inserted),
        "skipped_conflict": len(skipped_conflict),
        "mode": "apply" if args.apply else "dry_run",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(out_dir / "inserted_rows.csv", inserted)
    _write_csv(out_dir / "already_present_rows.csv", already_present)
    _write_csv(out_dir / "skipped_conflict_rows.csv", skipped_conflict)
    print(json.dumps({"output_dir": str(out_dir), **summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
