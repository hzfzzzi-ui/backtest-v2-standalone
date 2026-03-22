from __future__ import annotations

from datetime import date

import pandas as pd

from backend.cli.managed import audit_pit_stock_feature_coverage as audit


def test_build_audit_args_for_stock_feature_coverage() -> None:
    args = audit.build_audit_args(end="2026-03-16", market="CN_A", output_dir="tmp")

    assert args.end == "2026-03-16"
    assert args.market == "CN_A"
    assert args.reference_table == audit.DEFAULT_REFERENCE_TABLE
    assert args.daily_basic_table == audit.DEFAULT_DAILY_BASIC_TABLE
    assert args.moneyflow_table == audit.DEFAULT_MONEYFLOW_TABLE
    assert args.output_dir == "tmp"


def test_run_audit_summarizes_coverage(monkeypatch, tmp_path) -> None:
    class _DummyCursor:
        description = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, *args, **kwargs):
            return None

    class _DummyConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return _DummyCursor()

    coverage_frame = pd.DataFrame(
        [
            {
                "trade_date": date(2026, 3, 14),
                "reference_count": 10,
                "daily_basic_count": 9,
                "moneyflow_count": 8,
                "daily_basic_missing_count": 1,
                "daily_basic_excess_count": 0,
                "moneyflow_missing_count": 2,
                "moneyflow_excess_count": 0,
                "moneyflow_missing_vs_daily_basic_count": 1,
                "daily_basic_coverage_ratio": 0.9,
                "moneyflow_coverage_ratio": 0.8,
                "moneyflow_vs_daily_basic_ratio": 0.888889,
            },
            {
                "trade_date": date(2026, 3, 16),
                "reference_count": 12,
                "daily_basic_count": 13,
                "moneyflow_count": 6,
                "daily_basic_missing_count": 0,
                "daily_basic_excess_count": 1,
                "moneyflow_missing_count": 6,
                "moneyflow_excess_count": 0,
                "moneyflow_missing_vs_daily_basic_count": 6,
                "daily_basic_coverage_ratio": 1.083333,
                "moneyflow_coverage_ratio": 0.5,
                "moneyflow_vs_daily_basic_ratio": 0.461538,
            },
        ]
    )

    def _fake_gap_sample_frame(*, target_label: str, **kwargs):
        if target_label == "daily_basic_missing":
            return pd.DataFrame([{"coverage_type": target_label, "trade_date": date(2026, 3, 14), "symbol": "sz000001"}])
        if target_label == "daily_basic_excess":
            return pd.DataFrame([{"coverage_type": target_label, "trade_date": date(2026, 3, 16), "symbol": "sz300001"}])
        return pd.DataFrame([{"coverage_type": target_label, "trade_date": date(2026, 3, 16), "symbol": "bj920000"}])

    monkeypatch.setattr(audit.common, "connect", lambda: _DummyConn())
    monkeypatch.setattr(audit, "_ensure_required_table", lambda cur, table: None)
    monkeypatch.setattr(audit, "_resolve_reference_end_date", lambda cur, reference_table, market: date(2026, 3, 16))
    monkeypatch.setattr(audit, "_fetch_coverage_frame", lambda cur, **kwargs: coverage_frame.copy())
    monkeypatch.setattr(audit, "_fetch_gap_sample_frame", lambda cur, **kwargs: _fake_gap_sample_frame(**kwargs))

    summary = audit.run_audit(audit.build_audit_args(start="2026-03-14", end="2026-03-16", output_dir=str(tmp_path)))

    assert summary["status"] == "ok"
    assert summary["trade_date_count"] == 2
    assert summary["overall"]["reference_rows"] == 22
    assert summary["overall"]["daily_basic_rows"] == 22
    assert summary["overall"]["moneyflow_rows"] == 14
    assert summary["overall"]["daily_basic_missing_rows"] == 1
    assert summary["overall"]["daily_basic_excess_rows"] == 1
    assert summary["overall"]["daily_basic_coverage_ratio"] == 1.0
    assert summary["overall"]["moneyflow_coverage_ratio"] == 0.636364
    assert summary["worst_trade_dates"]["moneyflow_missing"][0]["trade_date"] == "2026-03-16"
    assert summary["worst_trade_dates"]["daily_basic_excess"][0]["trade_date"] == "2026-03-16"
    assert tmp_path.joinpath("pit_stock_feature_coverage_per_trade_date.csv").exists()
    assert tmp_path.joinpath("pit_stock_daily_basic_missing_sample.csv").exists()
    assert tmp_path.joinpath("pit_stock_daily_basic_excess_sample.csv").exists()
    assert tmp_path.joinpath("pit_stock_moneyflow_missing_sample.csv").exists()
    assert tmp_path.joinpath("pit_stock_moneyflow_excess_sample.csv").exists()
