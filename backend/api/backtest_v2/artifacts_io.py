from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


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


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _safe_read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return dict(payload) if isinstance(payload, dict) else None


def _write_canonical_csv(src: Path, dst: Path, empty_columns: list[str] | None = None) -> Path:
    df = _safe_read_csv(src)
    if df.empty and empty_columns is not None:
        df = pd.DataFrame(columns=list(empty_columns))
    df.to_csv(dst, index=False)
    return dst


def _coerce_bool_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return not math.isnan(float(value)) and float(value) != 0.0
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"", "0", "false", "no", "n", "off", "nan", "none", "null"}:
        return False
    return bool(text)


def _bool_series(df: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in df.columns:
        return pd.Series([bool(default)] * len(df), index=df.index, dtype=bool)
    return df[column].map(_coerce_bool_value).astype(bool)


__all__ = [
    "_bool_series",
    "_coerce_bool_value",
    "_resolve_runtime_path",
    "_safe_float",
    "_safe_int",
    "_safe_read_csv",
    "_safe_read_json",
    "_to_rel",
    "_write_canonical_csv",
]
