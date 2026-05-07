from backend.research.final_score_composition_catalog import build_final_score_composition_catalog, list_final_score_component_ids


def test_final_score_composition_catalog_exposes_core_components() -> None:
    catalog = build_final_score_composition_catalog()
    factor_ids = {item['factor_id'] for item in catalog}
    assert 'final_score' in factor_ids
    assert 'residual_strength_score' in factor_ids
    assert 'conditional_tiebreak_score' in factor_ids
    assert 'industry_second_stage_score' in factor_ids


def test_list_final_score_component_ids_excludes_aggregate_when_requested() -> None:
    ids = list_final_score_component_ids(include_aggregate=False)
    assert 'final_score' not in ids
    assert 'residual_strength_score' in ids
