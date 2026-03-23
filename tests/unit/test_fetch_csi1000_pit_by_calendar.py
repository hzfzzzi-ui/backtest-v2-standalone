from __future__ import annotations

from backend.cli.managed.csi1000_rebalance_calendar import RebalanceCalendarEntry
from backend.cli.managed.fetch_csi1000_pit_by_calendar import (
    DEFAULT_STATIC_FALLBACK_SOURCE,
    DEFAULT_TUSHARE_SOURCE,
    build_calendar_snapshots,
)


def _entries() -> list[RebalanceCalendarEntry]:
    return [
        RebalanceCalendarEntry(
            effective_date="2016-03-01",
            event_type="scheduled",
            source="csindex_seed_schedule",
            version="seed-v1",
            generated_at="2026-03-11T00:00:00+08:00",
            source_note="seed row",
        )
    ]


def test_build_calendar_snapshots_uses_tushare_snapshot(monkeypatch) -> None:
    symbols = [f"{idx:06d}.SZ" for idx in range(500)] + [f"{600000 + idx:06d}.SH" for idx in range(500)]
    monkeypatch.setattr(
        "backend.cli.managed.fetch_csi1000_pit_by_calendar._fetch_tushare_snapshot",
        lambda effective_date, *, token, lookahead_days: (symbols, "2016-03-01"),
    )

    snapshots, summary = build_calendar_snapshots(
        _entries(),
        provider="tushare",
        token="token",
        allow_static_fallback=False,
        expected_count=1000,
        strict_count=True,
    )

    spec, symbols = snapshots[0]
    assert spec.source == DEFAULT_TUSHARE_SOURCE
    assert spec.event_type == "scheduled"
    assert spec.version == "seed-v1"
    assert spec.snapshot_trade_date == "2016-03-01"
    assert spec.rebalance_calendar_source == "csindex_seed_schedule"
    assert spec.rebalance_calendar_generated_at == "2026-03-11T00:00:00+08:00"
    assert len(symbols) == 1000
    assert summary["provider_counts"][DEFAULT_TUSHARE_SOURCE] == 1
    assert summary["snapshot_trade_dates"]["2016-03-01"] == "2016-03-01"
    assert summary["provider_floor_date"] == "2016-03-01"


def test_build_calendar_snapshots_falls_back_to_static_when_enabled(monkeypatch) -> None:
    symbols = [f"{idx:06d}.SZ" for idx in range(500)] + [f"{600000 + idx:06d}.SH" for idx in range(500)]

    def _raise(*args, **kwargs):
        raise RuntimeError("missing tushare event")

    monkeypatch.setattr("backend.cli.managed.fetch_csi1000_pit_by_calendar._fetch_tushare_snapshot", _raise)
    monkeypatch.setattr(
        "backend.cli.managed.fetch_csi1000_pit_by_calendar._fetch_akshare_static_snapshot",
        lambda: symbols,
    )

    snapshots, summary = build_calendar_snapshots(
        _entries(),
        provider="tushare",
        token="token",
        allow_static_fallback=True,
        expected_count=1000,
        strict_count=True,
    )

    spec, symbols = snapshots[0]
    assert spec.source == DEFAULT_STATIC_FALLBACK_SOURCE
    assert spec.snapshot_trade_date == ""
    assert "static_fallback_reason=" in spec.source_note
    assert len(symbols) == 1000
    assert summary["fallback_event_count"] == 1
    assert summary["fallback_effective_dates"] == ["2016-03-01"]
    assert summary["provider_floor_date"] is None
