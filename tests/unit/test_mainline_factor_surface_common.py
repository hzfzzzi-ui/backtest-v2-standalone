import pandas as pd

from backend.research.mainline_factor_surface_common import analyze_fragility_surface, analyze_rank_surface, build_factor_score_snapshot


def test_build_factor_score_snapshot_supports_direction_inversion() -> None:
    factor_snapshot = pd.DataFrame(
        [
            {'date': '2020-01-01', 'symbol': 'a', 'factor_id': 'x', 'raw_value': 1.0, 'normalized_value': 1.0, 'rank_value': 1.0, 'available': True},
            {'date': '2020-01-01', 'symbol': 'b', 'factor_id': 'x', 'raw_value': 0.0, 'normalized_value': -1.0, 'rank_value': 0.5, 'available': True},
            {'date': '2020-01-01', 'symbol': 'a', 'factor_id': 'y', 'raw_value': 0.0, 'normalized_value': -1.0, 'rank_value': 0.5, 'available': True},
            {'date': '2020-01-01', 'symbol': 'b', 'factor_id': 'y', 'raw_value': 1.0, 'normalized_value': 1.0, 'rank_value': 1.0, 'available': True},
        ]
    )
    scored = build_factor_score_snapshot(
        factor_snapshot,
        factor_ids=['x', 'y'],
        factor_weights={'x': 1.0, 'y': 1.0},
        invert_for_score={'y'},
        score_id='demo',
    )
    a = float(scored.loc[scored['symbol'] == 'a', 'raw_value'].iloc[0])
    b = float(scored.loc[scored['symbol'] == 'b', 'raw_value'].iloc[0])
    assert a > b


def test_analyze_rank_surface_returns_rank_metrics() -> None:
    factor_snapshot = pd.DataFrame(
        [
            {'date': '2020-01-01', 'symbol': 'a', 'factor_id': 'f', 'raw_value': 1.0, 'normalized_value': 1.0, 'rank_value': 1.0, 'available': True},
            {'date': '2020-01-01', 'symbol': 'b', 'factor_id': 'f', 'raw_value': 0.0, 'normalized_value': 0.0, 'rank_value': 0.67, 'available': True},
            {'date': '2020-01-01', 'symbol': 'c', 'factor_id': 'f', 'raw_value': -1.0, 'normalized_value': -1.0, 'rank_value': 0.33, 'available': True},
            {'date': '2020-01-02', 'symbol': 'a', 'factor_id': 'f', 'raw_value': -1.0, 'normalized_value': -1.0, 'rank_value': 0.33, 'available': True},
            {'date': '2020-01-02', 'symbol': 'b', 'factor_id': 'f', 'raw_value': 0.0, 'normalized_value': 0.0, 'rank_value': 0.67, 'available': True},
            {'date': '2020-01-02', 'symbol': 'c', 'factor_id': 'f', 'raw_value': 1.0, 'normalized_value': 1.0, 'rank_value': 1.0, 'available': True},
        ]
    )
    factor_score_snapshot = pd.DataFrame(
        [
            {'date': '2020-01-01', 'symbol': 'a', 'score_id': 'factor_score', 'raw_value': 1.0, 'normalized_value': 1.0, 'rank_value': 1.0, 'available': True},
            {'date': '2020-01-01', 'symbol': 'b', 'score_id': 'factor_score', 'raw_value': 0.0, 'normalized_value': 0.0, 'rank_value': 0.67, 'available': True},
            {'date': '2020-01-01', 'symbol': 'c', 'score_id': 'factor_score', 'raw_value': -1.0, 'normalized_value': -1.0, 'rank_value': 0.33, 'available': True},
            {'date': '2020-01-02', 'symbol': 'a', 'score_id': 'factor_score', 'raw_value': -1.0, 'normalized_value': -1.0, 'rank_value': 0.33, 'available': True},
            {'date': '2020-01-02', 'symbol': 'b', 'score_id': 'factor_score', 'raw_value': 0.0, 'normalized_value': 0.0, 'rank_value': 0.67, 'available': True},
            {'date': '2020-01-02', 'symbol': 'c', 'score_id': 'factor_score', 'raw_value': 1.0, 'normalized_value': 1.0, 'rank_value': 1.0, 'available': True},
        ]
    )
    forward_returns = pd.DataFrame(
        [
            {'date': '2020-01-01', 'symbol': 'a', 'forward_return_1d': 0.03},
            {'date': '2020-01-01', 'symbol': 'b', 'forward_return_1d': 0.02},
            {'date': '2020-01-01', 'symbol': 'c', 'forward_return_1d': 0.01},
            {'date': '2020-01-02', 'symbol': 'a', 'forward_return_1d': 0.01},
            {'date': '2020-01-02', 'symbol': 'b', 'forward_return_1d': 0.02},
            {'date': '2020-01-02', 'symbol': 'c', 'forward_return_1d': 0.03},
        ]
    )
    analysis = analyze_rank_surface(factor_snapshot=factor_snapshot, factor_score_snapshot=factor_score_snapshot, forward_returns=forward_returns, horizons=[1])
    assert 'f' in analysis['factors']
    assert analysis['factor_score']['mean_observation_ic_1d'] is not None


def test_analyze_fragility_surface_returns_veto_metrics() -> None:
    factor_snapshot = pd.DataFrame(
        [
            {'date': '2020-01-01', 'symbol': str(i), 'factor_id': 'frag', 'raw_value': float(i), 'normalized_value': float(i), 'rank_value': (i + 1) / 10.0, 'available': True}
            for i in range(10)
        ]
    )
    factor_score_snapshot = pd.DataFrame(
        [
            {'date': '2020-01-01', 'symbol': str(i), 'score_id': 'fragility_score', 'raw_value': float(i), 'normalized_value': float(i), 'rank_value': (i + 1) / 10.0, 'available': True}
            for i in range(10)
        ]
    )
    forward_returns = pd.DataFrame(
        [
            {'date': '2020-01-01', 'symbol': str(i), 'forward_return_5d': 0.05 - i * 0.01}
            for i in range(10)
        ]
    )
    analysis = analyze_fragility_surface(factor_snapshot=factor_snapshot, factor_score_snapshot=factor_score_snapshot, forward_returns=forward_returns, horizons=[5])
    bucket = analysis['factors']['frag']['horizon_5d']
    assert bucket['high20_mean_return'] < bucket['low20_mean_return']
