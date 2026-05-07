from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.api.shared.json_utils import sanitize_json
from backend.research.study_definition import StudyDefinition


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def outputs_root() -> Path:
    return (repo_root() / 'outputs' / 'studies').resolve()


def study_run_dir(study: StudyDefinition, *, window_key: str, variant_name: str) -> Path:
    parts = [part for part in str(study.study_id or '').replace('\\', '/').split('/') if part]
    return (outputs_root().joinpath(*parts, window_key, variant_name)).resolve()


def parse_symbols(payload: dict[str, Any]) -> list[str]:
    run_params = payload.get('run_params')
    run_params = run_params if isinstance(run_params, dict) else {}
    symbols = [str(item).strip().lower() for item in list(run_params.get('symbols') or []) if str(item).strip()]
    return list(dict.fromkeys(symbols))


def parse_factor_ids(payload: dict[str, Any], *, default_factor_ids: list[str]) -> list[str]:
    run_params = payload.get('run_params')
    run_params = run_params if isinstance(run_params, dict) else {}
    factor_ids = [str(item).strip().lower() for item in list(run_params.get('factor_ids') or []) if str(item).strip()]
    return factor_ids or list(default_factor_ids)


def parse_factor_weights(payload: dict[str, Any], *, factor_ids: list[str]) -> dict[str, float]:
    run_params = payload.get('run_params')
    run_params = run_params if isinstance(run_params, dict) else {}
    raw = run_params.get('factor_weights')
    if not isinstance(raw, dict) or not raw:
        return {factor_id: 1.0 for factor_id in factor_ids}
    out: dict[str, float] = {}
    for factor_id in factor_ids:
        value = raw.get(factor_id)
        out[factor_id] = float(value) if value is not None else 0.0
    return out


def parse_horizons(payload: dict[str, Any], *, default: list[int] | None = None) -> list[int]:
    run_params = payload.get('run_params')
    run_params = run_params if isinstance(run_params, dict) else {}
    raw = run_params.get('horizons')
    if isinstance(raw, list) and raw:
        horizons = [int(item) for item in raw if int(item) > 0]
        if horizons:
            return horizons
    single = run_params.get('horizon_days')
    if single is not None:
        return [int(single)]
    return list(default or [1, 5, 10, 20])


def subset_columns(symbols_all: list[str], requested_symbols: list[str]) -> tuple[list[str], list[int]]:
    if not requested_symbols:
        return list(symbols_all), list(range(len(symbols_all)))
    wanted = set(item.lower() for item in requested_symbols)
    selected_symbols: list[str] = []
    selected_idx: list[int] = []
    for idx, symbol in enumerate(symbols_all):
        if str(symbol).lower() in wanted:
            selected_symbols.append(str(symbol).lower())
            selected_idx.append(idx)
    if not selected_symbols:
        raise ValueError('requested symbols are absent from the mainline breakout runtime context')
    return selected_symbols, selected_idx


def _zscore(values: pd.Series) -> pd.Series:
    valid = values.dropna()
    if valid.empty:
        return pd.Series(np.nan, index=values.index, dtype=float)
    std = float(valid.std(ddof=0))
    if std <= 0.0 or pd.isna(std):
        out = pd.Series(0.0, index=valid.index, dtype=float)
    else:
        out = (valid - float(valid.mean())) / std
    return out.reindex(values.index)


def build_factor_snapshot(*, dates: pd.DatetimeIndex, symbols: list[str], factor_matrices: dict[str, np.ndarray], tradable_matrix: np.ndarray) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for factor_id, matrix in factor_matrices.items():
        factor_frame = pd.DataFrame(np.asarray(matrix, dtype=float), index=dates, columns=symbols)
        tradable_frame = pd.DataFrame(np.asarray(tradable_matrix, dtype=bool), index=dates, columns=symbols)
        long_frame = factor_frame.reset_index(names='date').melt(id_vars='date', var_name='symbol', value_name='raw_value')
        long_frame['date'] = pd.to_datetime(long_frame['date']).dt.strftime('%Y-%m-%d')
        tradable_long = tradable_frame.reset_index(names='date').melt(id_vars='date', var_name='symbol', value_name='tradable')
        long_frame['tradable'] = tradable_long['tradable'].astype(bool).values
        long_frame['factor_id'] = factor_id
        long_frame['available'] = long_frame['tradable'] & long_frame['raw_value'].notna()
        frames.append(long_frame)
    snapshot = pd.concat(frames, ignore_index=True)
    snapshot['normalized_value'] = np.nan
    snapshot['rank_value'] = np.nan
    for _, idx in snapshot.groupby(['factor_id', 'date']).groups.items():
        day = snapshot.loc[list(idx)].copy()
        available_mask = day['available'].astype(bool)
        if not available_mask.any():
            continue
        normalized = _zscore(day.loc[available_mask, 'raw_value'])
        ranks = day.loc[available_mask, 'raw_value'].rank(method='average', pct=True)
        snapshot.loc[day.loc[available_mask].index, 'normalized_value'] = normalized.values
        snapshot.loc[day.loc[available_mask].index, 'rank_value'] = ranks.values
    return snapshot.loc[:, ['date', 'symbol', 'factor_id', 'raw_value', 'normalized_value', 'rank_value', 'available']].reset_index(drop=True)


def build_factor_score_snapshot(factor_snapshot: pd.DataFrame, *, factor_ids: list[str], factor_weights: dict[str, float], invert_for_score: set[str] | None = None, score_id: str = 'factor_score') -> pd.DataFrame:
    invert_for_score = set(invert_for_score or set())
    subset = factor_snapshot.loc[factor_snapshot['factor_id'].isin(factor_ids)].copy()
    if subset.empty:
        return pd.DataFrame(columns=['date', 'symbol', 'score_id', 'raw_value', 'normalized_value', 'rank_value', 'available'])
    subset['weight'] = subset['factor_id'].map(lambda item: float(factor_weights.get(item, 0.0)))
    subset['oriented_value'] = subset['normalized_value']
    invert_mask = subset['factor_id'].isin(invert_for_score)
    subset.loc[invert_mask, 'oriented_value'] = -subset.loc[invert_mask, 'normalized_value']
    scored = (
        subset.loc[subset['available'] & subset['weight'].ne(0.0)]
        .assign(weighted=lambda frame: frame['oriented_value'] * frame['weight'])
        .groupby(['date', 'symbol'], as_index=False)
        .agg(raw_value=('weighted', 'sum'), weight_sum=('weight', 'sum'), factor_count=('factor_id', 'size'))
    )
    if scored.empty:
        return pd.DataFrame(columns=['date', 'symbol', 'score_id', 'raw_value', 'normalized_value', 'rank_value', 'available'])
    scored['raw_value'] = scored['raw_value'] / scored['weight_sum']
    scored['available'] = scored['factor_count'] > 0
    scored['normalized_value'] = np.nan
    scored['rank_value'] = np.nan
    for _, idx in scored.groupby('date').groups.items():
        day = scored.loc[list(idx)].copy()
        normalized = _zscore(day['raw_value'])
        ranks = day['raw_value'].rank(method='average', pct=True)
        scored.loc[day.index, 'normalized_value'] = normalized.values
        scored.loc[day.index, 'rank_value'] = ranks.values
    scored['score_id'] = score_id
    return scored.loc[:, ['date', 'symbol', 'score_id', 'raw_value', 'normalized_value', 'rank_value', 'available']].reset_index(drop=True)


def build_forward_return_snapshot(*, dates: pd.DatetimeIndex, symbols: list[str], close_matrix: np.ndarray, horizons: list[int]) -> pd.DataFrame:
    close_df = pd.DataFrame(np.asarray(close_matrix, dtype=float), index=dates, columns=symbols)
    frames: list[pd.DataFrame] = []
    for horizon in horizons:
        forward = close_df.shift(-horizon) / close_df - 1.0
        frame = forward.reset_index(names='date').melt(id_vars='date', var_name='symbol', value_name=f'forward_return_{horizon}d')
        frame['date'] = pd.to_datetime(frame['date']).dt.strftime('%Y-%m-%d')
        frames.append(frame)
    out = frames[0]
    for extra in frames[1:]:
        out = out.merge(extra, on=['date', 'symbol'], how='outer')
    return out.reset_index(drop=True)


def _safe_spearman(frame: pd.DataFrame, *, value_col: str, forward_col: str) -> float | None:
    subset = frame.loc[frame[value_col].notna() & frame[forward_col].notna(), [value_col, forward_col]]
    if len(subset) < 3:
        return None
    if subset[value_col].nunique() <= 1 or subset[forward_col].nunique() <= 1:
        return None
    value_ranks = subset[value_col].rank(method='average')
    forward_ranks = subset[forward_col].rank(method='average')
    value = value_ranks.corr(forward_ranks, method='pearson')
    if pd.isna(value):
        return None
    return float(value)


def _safe_top_bottom_spread(frame: pd.DataFrame, *, value_col: str, forward_col: str) -> float | None:
    subset = frame.loc[frame[value_col].notna() & frame[forward_col].notna(), [value_col, forward_col]].copy()
    if len(subset) < 4:
        return None
    subset = subset.sort_values(value_col).reset_index(drop=True)
    half = len(subset) // 2
    if half <= 0:
        return None
    bottom = float(subset.iloc[:half][forward_col].mean())
    top = float(subset.iloc[-half:][forward_col].mean())
    return top - bottom


def analyze_rank_surface(*, factor_snapshot: pd.DataFrame, factor_score_snapshot: pd.DataFrame, forward_returns: pd.DataFrame, horizons: list[int]) -> dict[str, Any]:
    merged_factor = factor_snapshot.merge(forward_returns, on=['date', 'symbol'], how='left')
    merged_score = factor_score_snapshot.merge(forward_returns, on=['date', 'symbol'], how='left')
    analysis: dict[str, Any] = {'factors': {}, 'factor_score': {}}
    for factor_id, frame in merged_factor.groupby('factor_id'):
        row: dict[str, Any] = {
            'coverage_ratio': float(frame['available'].mean()) if len(frame) else 0.0,
            'usable_rows': int(frame['available'].sum()),
            'usable_days': int(frame.loc[frame['available'], 'date'].nunique()),
        }
        for horizon in horizons:
            forward_col = f'forward_return_{horizon}d'
            daily_ic = []
            daily_spread = []
            for _, day in frame.groupby('date'):
                value = _safe_spearman(day, value_col='rank_value', forward_col=forward_col)
                if value is not None:
                    daily_ic.append(value)
                spread = _safe_top_bottom_spread(day, value_col='rank_value', forward_col=forward_col)
                if spread is not None:
                    daily_spread.append(spread)
            row[f'mean_observation_ic_{horizon}d'] = float(np.mean(daily_ic)) if daily_ic else None
            row[f'ic_ir_{horizon}d'] = float(np.mean(daily_ic) / np.std(daily_ic, ddof=0)) if len(daily_ic) > 1 and float(np.std(daily_ic, ddof=0)) > 0.0 else None
            row[f'mean_top_bottom_spread_{horizon}d'] = float(np.mean(daily_spread)) if daily_spread else None
        analysis['factors'][factor_id] = sanitize_json(row)
    score_row: dict[str, Any] = {
        'coverage_ratio': float(merged_score['available'].mean()) if len(merged_score) else 0.0,
        'usable_rows': int(merged_score['available'].sum()),
        'usable_days': int(merged_score.loc[merged_score['available'], 'date'].nunique()) if len(merged_score) else 0,
    }
    for horizon in horizons:
        forward_col = f'forward_return_{horizon}d'
        daily_ic = []
        daily_spread = []
        for _, day in merged_score.groupby('date'):
            value = _safe_spearman(day, value_col='rank_value', forward_col=forward_col)
            if value is not None:
                daily_ic.append(value)
            spread = _safe_top_bottom_spread(day, value_col='rank_value', forward_col=forward_col)
            if spread is not None:
                daily_spread.append(spread)
        score_row[f'mean_observation_ic_{horizon}d'] = float(np.mean(daily_ic)) if daily_ic else None
        score_row[f'ic_ir_{horizon}d'] = float(np.mean(daily_ic) / np.std(daily_ic, ddof=0)) if len(daily_ic) > 1 and float(np.std(daily_ic, ddof=0)) > 0.0 else None
        score_row[f'mean_top_bottom_spread_{horizon}d'] = float(np.mean(daily_spread)) if daily_spread else None
    analysis['factor_score'] = sanitize_json(score_row)
    return sanitize_json(analysis)


def analyze_fragility_surface(*, factor_snapshot: pd.DataFrame, factor_score_snapshot: pd.DataFrame, forward_returns: pd.DataFrame, horizons: list[int]) -> dict[str, Any]:
    merged_factor = factor_snapshot.merge(forward_returns, on=['date', 'symbol'], how='left')
    merged_score = factor_score_snapshot.merge(forward_returns, on=['date', 'symbol'], how='left')
    analysis: dict[str, Any] = {'factors': {}, 'factor_score': {}}

    def _bucket_stats(frame: pd.DataFrame, *, value_col: str, forward_col: str) -> dict[str, float | None]:
        subset = frame.loc[frame[value_col].notna() & frame[forward_col].notna(), [value_col, forward_col]].copy()
        if len(subset) < 10:
            return {
                'all_mean_return': None,
                'high20_mean_return': None,
                'low20_mean_return': None,
                'high20_negative_rate': None,
                'low20_negative_rate': None,
                'veto_top20_improvement': None,
            }
        low_cut = float(subset[value_col].quantile(0.2))
        high_cut = float(subset[value_col].quantile(0.8))
        low_bucket = subset.loc[subset[value_col] <= low_cut, forward_col]
        high_bucket = subset.loc[subset[value_col] >= high_cut, forward_col]
        keep_bucket = subset.loc[subset[value_col] < high_cut, forward_col]
        all_mean = float(subset[forward_col].mean())
        return {
            'all_mean_return': all_mean,
            'high20_mean_return': float(high_bucket.mean()) if len(high_bucket) else None,
            'low20_mean_return': float(low_bucket.mean()) if len(low_bucket) else None,
            'high20_negative_rate': float((high_bucket < 0).mean()) if len(high_bucket) else None,
            'low20_negative_rate': float((low_bucket < 0).mean()) if len(low_bucket) else None,
            'veto_top20_improvement': float(keep_bucket.mean() - all_mean) if len(keep_bucket) else None,
        }

    for factor_id, frame in merged_factor.groupby('factor_id'):
        row: dict[str, Any] = {
            'coverage_ratio': float(frame['available'].mean()) if len(frame) else 0.0,
            'usable_rows': int(frame['available'].sum()),
            'usable_days': int(frame.loc[frame['available'], 'date'].nunique()),
        }
        for horizon in horizons:
            forward_col = f'forward_return_{horizon}d'
            horizon_stats = []
            for _, day in frame.groupby('date'):
                horizon_stats.append(_bucket_stats(day, value_col='rank_value', forward_col=forward_col))
            row[f'horizon_{horizon}d'] = sanitize_json({
                key: float(np.mean([item[key] for item in horizon_stats if item[key] is not None])) if any(item[key] is not None for item in horizon_stats) else None
                for key in ('all_mean_return', 'high20_mean_return', 'low20_mean_return', 'high20_negative_rate', 'low20_negative_rate', 'veto_top20_improvement')
            })
        analysis['factors'][factor_id] = sanitize_json(row)

    score_row: dict[str, Any] = {
        'coverage_ratio': float(merged_score['available'].mean()) if len(merged_score) else 0.0,
        'usable_rows': int(merged_score['available'].sum()),
        'usable_days': int(merged_score.loc[merged_score['available'], 'date'].nunique()) if len(merged_score) else 0,
    }
    for horizon in horizons:
        forward_col = f'forward_return_{horizon}d'
        horizon_stats = []
        for _, day in merged_score.groupby('date'):
            horizon_stats.append(_bucket_stats(day, value_col='rank_value', forward_col=forward_col))
        score_row[f'horizon_{horizon}d'] = sanitize_json({
            key: float(np.mean([item[key] for item in horizon_stats if item[key] is not None])) if any(item[key] is not None for item in horizon_stats) else None
            for key in ('all_mean_return', 'high20_mean_return', 'low20_mean_return', 'high20_negative_rate', 'low20_negative_rate', 'veto_top20_improvement')
        })
    analysis['factor_score'] = sanitize_json(score_row)
    return sanitize_json(analysis)


def write_human_summary(path: Path, *, title: str, study_kind: str, analysis: dict[str, Any], horizons: list[int]) -> None:
    lines = [f'# {title}', '', f'- study_kind: `{study_kind}`', '- runtime_mode: `RESEARCH_ONLY`', '']
    factors = dict(analysis.get('factors') or {})
    for factor_id, row in factors.items():
        lines.append(f'## {factor_id}')
        lines.append('')
        lines.append(f"- coverage_ratio: `{row.get('coverage_ratio')}`")
        for horizon in horizons:
            rank_ic = row.get(f'mean_observation_ic_{horizon}d')
            if rank_ic is not None:
                lines.append(f"- mean_observation_ic_{horizon}d: `{rank_ic}`")
                lines.append(f"- mean_top_bottom_spread_{horizon}d: `{row.get(f'mean_top_bottom_spread_{horizon}d')}`")
            else:
                bucket = row.get(f'horizon_{horizon}d')
                if isinstance(bucket, dict):
                    lines.append(f"- horizon_{horizon}d.veto_top20_improvement: `{bucket.get('veto_top20_improvement')}`")
                    lines.append(f"- horizon_{horizon}d.high20_mean_return: `{bucket.get('high20_mean_return')}`")
        lines.append('')
    score = dict(analysis.get('factor_score') or {})
    lines.extend(['## factor_score', '', f"- coverage_ratio: `{score.get('coverage_ratio')}`"])
    for horizon in horizons:
        rank_ic = score.get(f'mean_observation_ic_{horizon}d')
        if rank_ic is not None:
            lines.append(f"- mean_observation_ic_{horizon}d: `{rank_ic}`")
            lines.append(f"- mean_top_bottom_spread_{horizon}d: `{score.get(f'mean_top_bottom_spread_{horizon}d')}`")
        else:
            bucket = score.get(f'horizon_{horizon}d')
            if isinstance(bucket, dict):
                lines.append(f"- horizon_{horizon}d.veto_top20_improvement: `{bucket.get('veto_top20_improvement')}`")
                lines.append(f"- horizon_{horizon}d.high20_mean_return: `{bucket.get('high20_mean_return')}`")
    path.write_text('\n'.join(lines), encoding='utf-8')
