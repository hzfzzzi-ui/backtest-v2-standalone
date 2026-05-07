from backend.research.stock_lifecycle_fragility_catalog import (
    build_stock_lifecycle_fragility_catalog,
    list_stock_lifecycle_fragility_factor_ids,
)


def test_stock_lifecycle_fragility_catalog_exposes_expected_factor_ids() -> None:
    catalog = build_stock_lifecycle_fragility_catalog()
    factor_ids = {item['factor_id'] for item in catalog}
    assert factor_ids == {
        'early_fade_risk',
        'weak_carry_risk',
        'break_floor_risk',
        'pre_profit_failure_context_risk',
        'low10_exit_context_risk',
        'risk_off_exit_context_risk',
    }


def test_stock_lifecycle_fragility_factor_ids_are_stable() -> None:
    assert list_stock_lifecycle_fragility_factor_ids()[0] == 'early_fade_risk'
