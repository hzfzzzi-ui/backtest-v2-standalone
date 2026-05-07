from backend.research.exit_fragility_factor_catalog import build_exit_fragility_factor_catalog, list_exit_fragility_factor_ids


def test_exit_fragility_factor_catalog_exposes_failure_context() -> None:
    catalog = build_exit_fragility_factor_catalog()
    factor_ids = {item['factor_id'] for item in catalog}
    assert factor_ids == {
        'breakout_margin_raw',
        'breakout_margin_score',
        'breakout_fade_raw',
        'breakout_open_gap_raw',
        'breakout_quality_score',
    }


def test_exit_fragility_factor_ids_are_stable() -> None:
    assert list_exit_fragility_factor_ids()[0] == 'breakout_margin_raw'
