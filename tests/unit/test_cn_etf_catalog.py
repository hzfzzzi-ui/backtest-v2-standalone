from __future__ import annotations

from backend.core.data.cn_etf_catalog import (
    FIRST_WAVE_ALL,
    TEMPLATE_A_A1_CANDIDATES,
    expand_etf_preset,
    get_catalog_entry,
    supported_etf_ts_codes,
)


def test_template_a_a1_symbols_are_supported_but_not_in_first_wave_all() -> None:
    supported = set(supported_etf_ts_codes())

    assert "159845.SZ" in supported
    assert "510880.SH" in supported

    first_wave_all = set(expand_etf_preset(FIRST_WAVE_ALL))
    assert "159845.SZ" not in first_wave_all
    assert "510880.SH" not in first_wave_all

    a1_candidates = set(expand_etf_preset(TEMPLATE_A_A1_CANDIDATES))
    assert a1_candidates == {"159845.SZ", "510880.SH"}


def test_new_standard_etf_entries_are_resolvable() -> None:
    csi1000_entry = get_catalog_entry("159845.SZ")
    dividend_entry = get_catalog_entry("510880.SH")

    assert csi1000_entry is not None
    assert csi1000_entry.symbol == "sz159845"
    assert csi1000_entry.batch_id == "template_a_a1"

    assert dividend_entry is not None
    assert dividend_entry.symbol == "sh510880"
    assert dividend_entry.batch_id == "template_a_a1"
