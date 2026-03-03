from backend.api.endpoints.backtest_v2_protocol import (
    ARTIFACT_FILENAMES,
    ARTIFACT_LEGACY_ALIASES,
    COUNTER_LEGACY_ALIASES,
    candidate_artifact_names,
    normalize_counters,
)


def test_protocol_constants_and_aliases() -> None:
    assert ARTIFACT_FILENAMES["reason_codes"] == "reason_codes.csv"
    assert "reason_code_counts.csv" in ARTIFACT_LEGACY_ALIASES["reason_codes"]
    names = candidate_artifact_names("reason_codes")
    assert names[0] == "reason_codes.csv"
    assert "reason_code_counts.csv" in names


def test_normalize_counters_accepts_legacy_names() -> None:
    out, hits = normalize_counters(
        {
            "raw_signal_count": 10,
            "blocked_count": 3,
            "orders_count": 7,
            "skipped_count": 1,
            "closed_trades_count": 6,
        }
    )
    assert hits == len(COUNTER_LEGACY_ALIASES)
    assert out["raw_signal"] == 10
    assert out["blocked"] == 3
    assert out["orders"] == 7
    assert out["skipped"] == 1
    assert out["closed_trades"] == 6
