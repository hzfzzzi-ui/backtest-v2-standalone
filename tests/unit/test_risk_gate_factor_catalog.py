from backend.research.risk_gate_factor_catalog import build_risk_gate_factor_catalog, list_risk_gate_factor_ids


def test_risk_gate_catalog_exposes_expected_ids() -> None:
    factor_ids = {item["factor_id"] for item in build_risk_gate_factor_catalog()}
    assert "benchmark_regime_off_risk" in factor_ids
    assert "breakout_quality_fail_risk" in factor_ids
    assert "bull_quality_margin_shortfall_risk" in factor_ids


def test_list_risk_gate_factor_ids_is_stable() -> None:
    ids = list_risk_gate_factor_ids()
    assert ids[0] == "benchmark_regime_off_risk"
    assert "regime_blocked_breakout_risk" in ids
