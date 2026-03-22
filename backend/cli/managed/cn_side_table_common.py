from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_ROOT = ROOT / "outputs" / "ops"
DEFAULT_CONFIG_PATH = ROOT / "backend" / "configs" / "pams_cn_pg.json"
DEFAULT_BACKFILL_START = date(2007, 1, 4)
DEFAULT_TIMEZONE = "Asia/Shanghai"
DEFAULT_SYNC_TIME = "18:30"
IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(slots=True)
class DbSettings:
    host: str
    port: int
    dbname: str
    user: str
    password: str


def safe_ident(name: str) -> str:
    if not IDENT_RE.match(name):
        raise ValueError(f"invalid SQL identifier: {name}")
    return name


def normalize_stock_symbol(symbol: str) -> str:
    text = str(symbol or "").strip()
    if "." in text:
        code, exch = text.split(".", 1)
        exch_u = exch.upper()
        if exch_u == "SH":
            return f"sh{code}"
        if exch_u == "SZ":
            return f"sz{code}"
        if exch_u == "BJ":
            return f"bj{code}"
    lower = text.lower()
    if lower.startswith(("sh", "sz", "bj")):
        return lower
    if text and text[0] in {"6", "5", "9"}:
        return f"sh{text}"
    if text.startswith(("4", "8")):
        return f"bj{text}"
    return f"sz{text}"


def parse_symbols_csv(symbols_csv: str) -> set[str]:
    return {
        normalize_stock_symbol(part).lower()
        for part in [item.strip() for item in str(symbols_csv or "").split(",")]
        if part
    }


def load_env_file() -> dict[str, str]:
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


def load_db_settings() -> DbSettings:
    file_env = load_env_file()
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


def connect():
    if psycopg is None:  # pragma: no cover
        raise RuntimeError("psycopg is required")
    db = load_db_settings()
    return psycopg.connect(
        host=db.host,
        port=db.port,
        dbname=db.dbname,
        user=db.user,
        password=db.password,
        autocommit=False,
    )


def load_tushare_client(token: str):
    if not token:
        raise RuntimeError("TUSHARE_TOKEN is required via --token or env TUSHARE_TOKEN")
    import tushare as ts

    ts.set_token(token)
    return ts.pro_api(token)


def resolve_tushare_token(explicit: str = "") -> str:
    file_env = load_env_file()
    return str(explicit or os.environ.get("TUSHARE_TOKEN") or file_env.get("TUSHARE_TOKEN") or "").strip()


def _schedule_cutoff() -> dt_time:
    raw = str(os.environ.get("CN_DAILY_SYNC_TIME") or DEFAULT_SYNC_TIME).strip() or DEFAULT_SYNC_TIME
    try:
        hour_text, minute_text = raw.split(":", 1)
        return dt_time(hour=int(hour_text), minute=int(minute_text))
    except Exception:
        return dt_time(hour=18, minute=30)


def _now_local(now: datetime | None = None) -> datetime:
    tz = ZoneInfo(DEFAULT_TIMEZONE)
    if now is None:
        return datetime.now(tz)
    if now.tzinfo is None:
        return now.replace(tzinfo=tz)
    return now.astimezone(tz)


def load_open_trade_dates(pro: Any, start: date, end: date) -> list[date]:
    if start > end:
        return []
    raw = pro.trade_cal(
        exchange="SSE",
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
        fields="exchange,cal_date,is_open",
    )
    if raw is None or raw.empty:
        return []
    out: list[date] = []
    for row in raw.itertuples(index=False):
        cal_date = str(getattr(row, "cal_date", "")).strip()
        is_open = str(getattr(row, "is_open", "")).strip().lower()
        if not cal_date or is_open not in {"1", "true", "t", "yes", "y"}:
            continue
        out.append(datetime.strptime(cal_date, "%Y%m%d").date())
    return sorted(set(d for d in out if start <= d <= end))


def resolve_latest_trade_date(pro: Any, *, now: datetime | None = None) -> date | None:
    local_now = _now_local(now)
    cutoff_date = local_now.date()
    if local_now.time() < _schedule_cutoff():
        cutoff_date = cutoff_date - timedelta(days=1)
    window_start = cutoff_date - timedelta(days=60)
    open_days = load_open_trade_dates(pro, window_start, cutoff_date)
    if not open_days:
        return None
    return max(open_days)


def get_latest_trade_date(table: str) -> date | None:
    table_name = safe_ident(table)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", (f"public.{table_name}",))
            if cur.fetchone()[0] is None:
                return None
            cur.execute(f"SELECT MAX(trade_date) FROM public.{table_name}")
            row = cur.fetchone()
    value = row[0] if row else None
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def infer_start_date(requested_start: str, table: str) -> tuple[date, date | None]:
    latest = get_latest_trade_date(table)
    if str(requested_start or "").strip():
        return date.fromisoformat(str(requested_start).strip()), latest
    if latest is None:
        return DEFAULT_BACKFILL_START, None
    return latest + timedelta(days=1), latest


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_sample_rows(sample_frames: list[Any], frame, limit: int = 200) -> None:
    current = sum(int(len(item)) for item in sample_frames)
    remaining = max(limit - current, 0)
    if remaining <= 0 or frame is None or frame.empty:
        return
    sample_frames.append(frame.head(remaining).copy())
