from unittest.mock import MagicMock

import pytest

from backend.core.services import market_data_sync_service as sync


@pytest.fixture
def sync_connection(monkeypatch):
    conn = MagicMock()
    conn.__enter__.return_value = conn
    cursor = conn.cursor.return_value.__enter__.return_value
    monkeypatch.setattr(sync, "_connect", lambda: conn)
    monkeypatch.setattr(sync, "_status_table", lambda: "pams_data_sync_runs")
    return conn, cursor


def test_sync_schema_preflight_only_reads_existing_columns(sync_connection):
    conn, cursor = sync_connection
    cursor.fetchall.return_value = [(name,) for name in sync._SYNC_REQUIRED_COLUMNS]
    sync.ensure_sync_runs_table()
    assert cursor.execute.call_count == 1
    assert cursor.execute.call_args.args[0].lstrip().upper().startswith("SELECT ")
    conn.commit.assert_not_called()


@pytest.mark.parametrize("missing", ["id", "summary_json"])
def test_sync_schema_missing_columns_stop_job_without_ddl(sync_connection, missing):
    conn, cursor = sync_connection
    cursor.fetchall.return_value = [(name,) for name in sync._SYNC_REQUIRED_COLUMNS if name != missing]
    with pytest.raises(RuntimeError, match="required sync schema.*provision it separately") as exc:
        sync.ensure_sync_runs_table()
    assert missing in str(exc.value)
    assert cursor.execute.call_count == 1
    assert cursor.execute.call_args.args[0].lstrip().upper().startswith("SELECT ")
    conn.commit.assert_not_called()


def test_etf_schema_preflight_only_reads_existing_columns():
    etf = sync.etf_daily_refresher
    cursor = MagicMock()
    cursor.fetchall.side_effect = [[(name,) for name in required] for required in etf._REQUIRED_COLUMNS.values()]
    etf._ensure_tables(cursor)
    assert cursor.execute.call_count == len(etf._REQUIRED_COLUMNS)
    assert all(call.args[0].lstrip().upper().startswith("SELECT ") for call in cursor.execute.call_args_list)


def test_etf_missing_adjustment_column_stops_job_without_ddl():
    etf = sync.etf_daily_refresher
    cursor = MagicMock()
    cursor.fetchall.return_value = [(name,) for name in etf._REQUIRED_COLUMNS[etf.DAILY_TABLE] if name != "adj_factor"]
    with pytest.raises(RuntimeError, match="required ETF schema.*adj_factor.*provision it separately"):
        etf._ensure_tables(cursor)
    assert cursor.execute.call_count == 1
    assert cursor.execute.call_args.args[0].lstrip().upper().startswith("SELECT ")
