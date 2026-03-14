from __future__ import annotations

import json

import pandas as pd

from backend.core.services.market_snapshot_service import (
    _write_snapshot_files,
    build_market_snapshot_from_frames,
    render_market_brief,
)
from tests.unit.test_market_snapshot_builder import (
    _build_index_histories,
    _build_market_history,
    _build_sentiment_history,
)


def test_market_snapshot_artifacts_are_written_idempotently(tmp_path) -> None:
    market_history = _build_market_history()
    trade_date = pd.Timestamp(market_history["date"].max())
    snapshot = build_market_snapshot_from_frames(
        requested_trade_date=trade_date.date(),
        market_history=market_history,
        index_histories=_build_index_histories(trade_date, include_csi1000=True),
        sentiment_history=_build_sentiment_history(trade_date),
        provider_query_audit=[],
    )
    brief_markdown = render_market_brief(snapshot)
    output_dir = tmp_path / "market_snapshots" / trade_date.date().isoformat()

    first_snapshot_path, first_brief_path = _write_snapshot_files(snapshot, brief_markdown, output_dir)
    second_snapshot_path, second_brief_path = _write_snapshot_files(snapshot, brief_markdown, output_dir)

    assert first_snapshot_path == second_snapshot_path
    assert first_brief_path == second_brief_path
    assert first_snapshot_path.exists()
    assert first_brief_path.exists()
    payload = json.loads(first_snapshot_path.read_text(encoding="utf-8"))
    assert payload["trade_date"] == trade_date.date().isoformat()
    assert "## 今日结论" in first_brief_path.read_text(encoding="utf-8")
    assert not (output_dir / "run_meta.json").exists()
