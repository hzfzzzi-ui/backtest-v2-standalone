from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from ._paths import _experiments_root

router = APIRouter(tags=["backtest_v2"])


def _read_index() -> list[dict[str, Any]]:
    index_path = _experiments_root() / "index.json"
    if not index_path.exists():
        return []
    try:
        entries = json.loads(index_path.read_text(encoding="utf-8"))
        return entries if isinstance(entries, list) else []
    except Exception:
        return []


def _write_index(entries: list[dict[str, Any]]) -> None:
    index_path = _experiments_root() / "index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _read_nav_rows(path, limit: int = 5000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        import pandas as pd

        df = pd.read_csv(path)
    except Exception:
        return []
    if df.empty:
        return []
    if "date" not in df.columns:
        return []
    nav_col = None
    for c in ("nav", "strategy_nav", "equity", "portfolio_value"):
        if c in df.columns:
            nav_col = c
            break
    if nav_col is None:
        return []
    out: list[dict[str, Any]] = []
    for r in df[["date", nav_col]].tail(int(limit)).itertuples(index=False):
        try:
            out.append({"date": str(r[0])[:10], "nav": float(r[1])})
        except Exception:
            continue
    return out


@router.get("/api/backtest_v2/experiments")
def list_experiments():
    """Return experiment list (newest first), with lazy orphan cleanup."""
    entries = _read_index()
    exp_root = _experiments_root()
    valid = [e for e in entries if (exp_root / str(e.get("exp_id", ""))).is_dir()]
    if len(valid) != len(entries):
        _write_index(valid)
    valid.sort(key=lambda e: str(e.get("created_at", "")), reverse=True)
    return valid


@router.get("/api/backtest_v2/experiments/{exp_id}/report")
def get_experiment_report(exp_id: str):
    """Return report.html as text/html."""
    report_path = _experiments_root() / exp_id / "report.html"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="report not found")
    html = report_path.read_text(encoding="utf-8")
    return HTMLResponse(content=html)


@router.delete("/api/backtest_v2/experiments/{exp_id}")
def delete_experiment(exp_id: str):
    """Delete a single experiment directory and remove from index."""
    import shutil
    exp_dir = _experiments_root() / exp_id
    if not exp_dir.is_dir():
        raise HTTPException(status_code=404, detail="experiment not found")
    shutil.rmtree(exp_dir, ignore_errors=True)
    entries = _read_index()
    entries = [e for e in entries if e.get("exp_id") != exp_id]
    _write_index(entries)
    return {"status": "deleted"}


@router.delete("/api/backtest_v2/experiments")
def clear_all_experiments():
    """Delete all experiment directories and reset index."""
    import shutil
    exp_root = _experiments_root()
    count = 0
    if exp_root.exists():
        for d in exp_root.iterdir():
            if d.is_dir() and d.name.startswith("exp_"):
                shutil.rmtree(d, ignore_errors=True)
                count += 1
    _write_index([])
    return {"status": "cleared", "count": count}


@router.post("/api/backtest_v2/experiments/compare")
def compare_experiments(body: dict[str, Any]):
    exp_ids = [str(x).strip() for x in (body or {}).get("exp_ids", []) if str(x).strip()]
    if len(exp_ids) < 2:
        raise HTTPException(status_code=400, detail="at least 2 exp_ids are required")
    if len(exp_ids) > 8:
        raise HTTPException(status_code=400, detail="at most 8 experiments can be compared at once")

    index_map = {str(x.get("exp_id") or ""): x for x in _read_index()}
    root = _experiments_root()
    items: list[dict[str, Any]] = []
    for exp_id in exp_ids:
        exp_dir = root / exp_id
        if not exp_dir.is_dir():
            continue
        perf = _read_json(exp_dir / "perf.json")
        nav_rows = _read_nav_rows(exp_dir / "nav.csv")
        idx_row = dict(index_map.get(exp_id) or {})
        items.append(
            {
                "exp_id": exp_id,
                "label": str(idx_row.get("label") or exp_id),
                "created_at": str(idx_row.get("created_at") or ""),
                "perf": {
                    "total_return": perf.get("total_return"),
                    "cagr": perf.get("cagr"),
                    "sharpe": perf.get("sharpe"),
                    "max_drawdown": perf.get("max_drawdown"),
                    "trades": perf.get("trades"),
                },
                "nav": nav_rows,
            }
        )

    if len(items) < 2:
        raise HTTPException(status_code=404, detail="not enough comparable experiments found")
    return {"items": items}
