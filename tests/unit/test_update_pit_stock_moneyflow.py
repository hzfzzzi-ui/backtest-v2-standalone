from __future__ import annotations

from datetime import date

import pandas as pd

from backend.cli.managed import update_pit_stock_moneyflow as updater


def test_normalize_moneyflow_frame_keeps_bucket_fields() -> None:
    raw = pd.DataFrame(
        [
            {
                "ts_code": "600519.SH",
                "trade_date": "20260316",
                "buy_sm_vol": 1,
                "sell_sm_vol": 2,
                "buy_md_vol": 3,
                "sell_md_vol": 4,
                "buy_lg_vol": 5,
                "sell_lg_vol": 6,
                "buy_elg_vol": 7,
                "sell_elg_vol": 8,
                "net_mf_vol": -4,
                "buy_sm_amount": 1.1,
                "sell_sm_amount": 2.2,
                "buy_md_amount": 3.3,
                "sell_md_amount": 4.4,
                "buy_lg_amount": 5.5,
                "sell_lg_amount": 6.6,
                "buy_elg_amount": 7.7,
                "sell_elg_amount": 8.8,
                "net_mf_amount": -1.2,
            }
        ]
    )

    normalized = updater._normalize_moneyflow_frame(raw)

    assert normalized.loc[0, "symbol"] == "sh600519"
    assert normalized.loc[0, "trade_date"].isoformat() == "2026-03-16"
    assert int(normalized.loc[0, "buy_elg_vol"]) == 7
    assert float(normalized.loc[0, "net_mf_amount"]) == -1.2
    assert normalized.loc[0, "source"] == updater.SOURCE_LABEL


def test_build_update_args_for_moneyflow_side_table() -> None:
    args = updater.build_update_args(end="2026-03-16", symbols_csv="600519.SH", apply=False)

    assert args.end == "2026-03-16"
    assert args.symbols_csv == "600519.SH"
    assert args.apply is False
    assert args.table == updater.DEFAULT_TABLE


def test_run_update_moneyflow_uses_trade_date_batches(monkeypatch, tmp_path) -> None:
    class _DummyPro:
        def trade_cal(self, **kwargs):
            return pd.DataFrame([{"exchange": "SSE", "cal_date": "20260316", "is_open": "1"}])

        def moneyflow(self, **kwargs):
            assert kwargs["trade_date"] == "20260316"
            return pd.DataFrame(
                [
                    {
                        "ts_code": "600519.SH",
                        "trade_date": "20260316",
                        "buy_sm_vol": 1,
                        "sell_sm_vol": 2,
                        "buy_md_vol": 3,
                        "sell_md_vol": 4,
                        "buy_lg_vol": 5,
                        "sell_lg_vol": 6,
                        "buy_elg_vol": 7,
                        "sell_elg_vol": 8,
                        "net_mf_vol": -4,
                        "buy_sm_amount": 1.1,
                        "sell_sm_amount": 2.2,
                        "buy_md_amount": 3.3,
                        "sell_md_amount": 4.4,
                        "buy_lg_amount": 5.5,
                        "sell_lg_amount": 6.6,
                        "buy_elg_amount": 7.7,
                        "sell_elg_amount": 8.8,
                        "net_mf_amount": -1.2,
                    }
                ]
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
