from backend.api.backtest_v2.protocol import (
    ARTIFACT_FILENAMES,
    ARTIFACT_HISTORICAL_ALIASES,
    candidate_artifact_names,
    normalize_counters,
)


def test_protocol_constants_and_aliases() -> None:
    assert ARTIFACT_FILENAMES["reason_codes"] == "reason_codes.csv"
    assert ARTIFACT_FILENAMES["trades"] == "portfolio_trades.csv"
    assert ARTIFACT_HISTORICAL_ALIASES == {}
    names = candidate_artifact_names("reason_codes")
    assert names == ["reason_codes.csv"]


def test_normalize_counters_keeps_canonical_fields_only() -> None:
    out, hits = normalize_counters(
        {
            "raw_signal": 10,
            "blocked": 3,
            "orders": 7,
            "skipped": 1,
            "closed_trades": 6,
        }
    )
    assert hits == 0
    assert out["raw_signal"] == 10
    assert out["blocked"] == 3
    assert out["orders"] == 7
    assert out["skipped"] == 1
    assert out["closed_trades"] == 6
