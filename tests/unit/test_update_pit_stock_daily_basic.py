from __future__ import annotations

from datetime import date

import pandas as pd

from backend.cli.managed import update_pit_stock_daily_basic as updater


def test_normalize_daily_basic_frame_keeps_explicit_turnover_fields() -> None:
    raw = pd.DataFrame(
        [
            {
                "ts_code": "600519.SH",
                "trade_date": "20260316",
                "turnover_rate": "0.55",
                "turnover_rate_f": "0.88",
            }
        ]
    )

    normalized = updater._normalize_daily_basic_frame(raw)

    assert normalized.loc[0, "symbol"] == "sh600519"
    assert normalized.loc[0, "trade_date"].isoformat() == "2026-03-16"
    assert float(normalized.loc[0, "turnover_rate"]) == 0.55
    assert float(normalized.loc[0, "turnover_rate_f"]) == 0.88
    assert normalized.loc[0, "source"] == updater.SOURCE_LABEL


def test_build_update_args_for_daily_basic_side_table() -> None:
    args = updater.build_update_args(end="2026-03-16", symbols_csv="600519.SH", apply=False)

    assert args.end == "2026-03-16"
    assert args.symbols_csv == "600519.SH"
    assert args.apply is False
    assert args.table == updater.DEFAULT_TABLE


def test_run_update_daily_basic_uses_trade_date_batches(monkeypatch, tmp_path) -> None:
    class _DummyPro:
        def trade_cal(self, **kwargs):
            return pd.DataFrame([{"exchange": "SSE", "cal_date": "20260316", "is_open": "1"}])

        def daily_basic(self, **kwargs):
            assert kwargs["trade_date"] == "20260316"
            return pd.DataFrame(
                [{"ts_code": "600519.SH", "trade_date": "20260316", "turnover_rate": "0.55", "turnover_rate_f": "0.88"}]
            )

    class _DummyConn:
        def cursor(self):
            return self

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, *args, **kwargs):
            return None

        def executemany(self, *args, **kwargs):
            return None

        def commit(self):
            return None

        def rollback(self):
            return None

    monkeypatch.setattr(updater.common, "load_tushare_client", lambda token: _DummyPro())
    monkeypatch.setattr(updater.common, "infer_start_date", lambda start, table: (date(2026, 3, 16), None))
    monkeypatch.setattr(updater.common, "get_latest_trade_date", lambda table: date(2026, 3, 16))
    monkeypatch.setattr(updater.common, "connect", lambda: _DummyConn())
    monkeypatch.setattr(updater, "_ensure_target_table", lambda cur, table: None)
    monkeypatch.setattr(updater, "_init_temp_table", lambda cur: None)
    monkeypatch.setattr(updater, "_load_batch_into_temp", lambda cur, batch: None)
    monkeypatch.setattr(updater, "_count_batch_state", lambda cur, table: (1, 0))
    monkeypatch.setattr(updater, "_upsert_batch", lambda cur, table: 1)

    summary = updater.run_update(
        updater.build_update_args(
            start="2026-03-16",
            end="2026-03-16",
            token="dummy-token",
            output_dir=str(tmp_path),
            apply=False,
        )
    )

    assert summary["fetched_rows"] == 1
    assert summary["normalized_rows"] == 1
    assert summary["insert_rows"] == 1
    assert summary["upserted_rows"] == 1
    assert summary["status"] == "dry_run"
    assert summary["per_trade_date"] == [{"trade_date": "2026-03-16", "raw_rows": 1, "rows": 1}]
