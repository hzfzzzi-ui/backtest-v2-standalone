from backend.research.positive_quality_factor_catalog import build_positive_quality_factor_catalog, list_positive_quality_factor_ids


def test_positive_quality_catalog_exposes_only_current_positive_items() -> None:
    factor_ids = {item["factor_id"] for item in build_positive_quality_factor_catalog()}
    assert factor_ids == {"volume_price_quality_score", "breakout_quality_score"}


def test_positive_quality_factor_ids_are_stable() -> None:
    assert list_positive_quality_factor_ids() == ["volume_price_quality_score", "breakout_quality_score"]
