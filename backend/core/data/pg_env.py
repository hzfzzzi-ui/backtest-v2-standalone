from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None


@dataclass(slots=True)
class PgSettings:
    host: str
    port: int
    dbname: str
    user: str
    password: str


def repo_root(anchor: Path | None = None) -> Path:
    if anchor is not None:
        for parent in [anchor, *anchor.parents]:
            if (parent / ".env").exists() and (parent / "backend").exists():
                return parent
    return Path(__file__).resolve().parents[3]


def read_env_file(root: Path | None = None) -> dict[str, str]:
    env_path = repo_root(root) / ".env"
    payload: dict[str, str] = {}
    if not env_path.exists():
        return payload
    for raw in env_path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        payload[key.strip()] = value.strip()
    return payload


def env_or_file(
    name: str,
    *,
    file_env: dict[str, str] | None = None,
    default: str = "",
) -> str:
    value = str(os.getenv(name) or "").strip()
    if value:
        return value
    payload = file_env or read_env_file()
    value = str(payload.get(name) or "").strip()
    if value:
        return value
    if name in {"PAMS_PG_PASSWORD", "PGPASSWORD"}:
        return str(payload.get("POSTGRES_PASSWORD") or "").strip()
    return str(default or "").strip()


def load_db_settings(
    *,
    config_path: str | Path | None = None,
    root: Path | None = None,
    default_host: str = "pams-postgres",
    default_port: int = 5432,
    default_dbname: str = "pams",
    default_user: str = "pams",
) -> PgSettings:
    file_env = read_env_file(root)
    cfg: dict[str, Any] = {}
    if config_path is not None:
        path = Path(config_path)
        if path.exists():
            cfg = json.loads(path.read_text(encoding="utf-8-sig"))
    db_cfg = dict(cfg.get("db") or {})
    return PgSettings(
        host=str(env_or_file("PAMS_PG_HOST", file_env=file_env) or env_or_file("PGHOST", file_env=file_env) or db_cfg.get("host") or default_host),
        port=int(env_or_file("PAMS_PG_PORT", file_env=file_env) or env_or_file("PGPORT", file_env=file_env) or db_cfg.get("port") or default_port),
        dbname=str(env_or_file("PAMS_PG_DBNAME", file_env=file_env) or env_or_file("PGDATABASE", file_env=file_env) or db_cfg.get("dbname") or default_dbname),
        user=str(env_or_file("PAMS_PG_USER", file_env=file_env) or env_or_file("PGUSER", file_env=file_env) or db_cfg.get("user") or default_user),
        password=str(env_or_file("PAMS_PG_PASSWORD", file_env=file_env) or env_or_file("PGPASSWORD", file_env=file_env) or db_cfg.get("password") or ""),
    )


def connect(
    *,
    config_path: str | Path | None = None,
    root: Path | None = None,
    default_host: str = "pams-postgres",
    default_port: int = 5432,
    default_dbname: str = "pams",
    default_user: str = "pams",
    autocommit: bool = False,
    row_factory: Any | None = None,
    connect_timeout: int | None = None,
):
    if psycopg is None:  # pragma: no cover
        raise RuntimeError("psycopg is required")
    settings = load_db_settings(
        config_path=config_path,
        root=root,
        default_host=default_host,
        default_port=default_port,
        default_dbname=default_dbname,
        default_user=default_user,
    )
    kwargs: dict[str, Any] = {
        "host": settings.host,
        "port": settings.port,
        "dbname": settings.dbname,
        "user": settings.user,
        "password": settings.password,
        "autocommit": autocommit,
    }
    if row_factory is not None:
        kwargs["row_factory"] = row_factory
    if connect_timeout is not None:
        kwargs["connect_timeout"] = connect_timeout
    return psycopg.connect(**kwargs)
