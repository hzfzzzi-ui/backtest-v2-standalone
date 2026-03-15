from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal
from pathlib import Path
from typing import Any

try:
    import numpy as _np  # type: ignore
except Exception:  # pragma: no cover
    _np = None


def coerce_number(value: Any, *, integer: bool = False) -> int | float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return int(value) if integer else float(value)
    if isinstance(value, (int, float)):
        n = float(value)
        if math.isnan(n) or math.isinf(n):
            return None
        return int(n) if integer else n
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            n = float(text)
        except Exception:
            return None
        if math.isnan(n) or math.isinf(n):
            return None
        return int(n) if integer else n
    return None


def sanitize_json(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    if _np is not None and isinstance(obj, _np.generic):
        return sanitize_json(obj.item())
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, (str, int, bool)) or obj is None:
        return obj
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, tuple):
        return [sanitize_json(v) for v in obj]
    if isinstance(obj, list):
        return [sanitize_json(v) for v in obj]
    if isinstance(obj, dict):
        return {str(k): sanitize_json(v) for k, v in obj.items()}
    return str(obj)


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def hash_json(obj: Any) -> str:
    payload = json.dumps(sanitize_json(obj), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def sanitize_for_json(value: Any) -> Any:
    return sanitize_json(value)
