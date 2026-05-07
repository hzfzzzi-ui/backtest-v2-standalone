from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from backend.api.shared.json_utils import sanitize_json
from backend.research.execution_pressure_factor_catalog import build_execution_pressure_factor_catalog, list_execution_pressure_factor_ids
from backend.research.execution_pressure_factor_snapshots import build_execution_pressure_factor_score_snapshot, build_execution_pressure_factor_snapshots, load_execution_pressure_frame
from backend.research.study_definition import StudyDefinition


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _study_run_dir(study: StudyDefinition, *, window_key: str, variant_name: str) -> Path:
    parts = [part for part in str(study.study_id or '').replace('\\', '/').split('/') if part]
    return (_repo_root() / 'outputs' / 'studies').joinpath(*parts, window_key, variant_name).resolve()


def _parse_factor_ids(payload: dict[str, Any]) -> list[str]:
    run_params = payload.get('run_params')
    run_params = run_params if isinstance(run_params, dict) else {}
    factor_ids = [str(item).strip().lower() for item in list(run_params.get('factor_ids') or []) if str(item).strip()]
    return factor_ids or list_execution_pressure_factor_ids()


def _parse_factor_weights(payload: dict[str, Any], *, factor_ids: list[str]) -> dict[str, float]:
    run_params = payload.get('run_params')
    run_params = run_params if isinstance(run_params, dict) else {}
    raw = run_params.get('factor_weights')
    if not isinstance(raw, dict) or not raw:
        return {factor_id: 1.0 for factor_id in factor_ids}
    return {factor_id: float(raw.get(factor_id, 0.0)) for factor_id in factor_ids}


def _parse_horizons(payload: dict[str, Any]) -> list[int]:
    run_params = payload.get('run_params')
    run_params = run_params if isinstance(run_params, dict) else {}
    raw = run_params.get('horizons')
    if isinstance(raw, list) and raw:
        values = [int(item) for item in raw if int(item) > 0]
        if values:
            return values
    return [5, 10, 20]


def _attach_forward_returns(frame: pd.DataFrame, *, horizons: list[int]) -> pd.DataFrame:
    out = frame.loc[:, ['date', 'nav']].copy()
    out['date'] = pd.to_datetime(out['date'])
    out = out.sort_values('date').reset_index(drop=True)
    for horizon in horizons:
        out[f'forward_return_{horizon}d'] = out['nav'].shift(-horizon) / out['nav'] - 1.0
    out['date'] = out['date'].dt.strftime('%Y-%m-%d')
    return out.drop(columns=['nav'])


def _safe_spearman(frame: pd.DataFrame, *, value_col: str, forward_col: str) -> float | None:
    subset = frame.loc[frame[value_col].notna() & frame[forward_col].notna(), [value_col, forward_col]]
    if len(subset) < 10:
        return None
    if subset[value_col].nunique() <= 1 or subset[forward_col].nunique() <= 1:
        return None
    value = subset[value_col].rank(method='average').corr(subset[forward_col].rank(method='average'), method='pearson')
    if pd.isna(value):
        return None
    return float(value)


def _summarize(frame: pd.DataFrame, *, value_col: str, forward_col: str) -> dict[str, Any]:
    usable = frame.loc[frame['availability_flag'] & frame[value_col].notna() & frame[forward_col].notna()].copy()
    if usable.empty:
        return sanitize_json({'coverage_ratio': float(frame['availability_flag'].mean()) if len(frame) else 0.0, 'usable_days': 0, 'mean_score': None, 'score_forward_corr': None, 'top20_mean_forward_return': None, 'bottom20_mean_forward_return': None, 'top20_negative_rate': None, 'bottom20_negative_rate': None, 'veto_top20_improvement': None})
    upper = float(usable[value_col].quantile(0.8))
    lower = float(usable[value_col].quantile(0.2))
    top = usable.loc[usable[value_col] >= upper, forward_col]
    bottom = usable.loc[usable[value_col] <= lower, forward_col]
    keep = usable.loc[usable[value_col] < upper, forward_col]
    all_mean = float(usable[forward_col].mean())
    return sanitize_json({'coverage_ratio': float(frame['availability_flag'].mean()) if len(frame) else 0.0, 'usable_days': int(usable['date'].nunique()), 'mean_score': float(usable[value_col].mean()), 'score_forward_corr': _safe_spearman(usable, value_col=value_col, forward_col=forward_col), 'top20_mean_forward_return': float(top.mean()) if len(top) else None, 'bottom20_mean_forward_return': float(bottom.mean()) if len(bottom) else None, 'top20_negative_rate': float((top < 0).mean()) if len(top) else None, 'bottom20_negative_rate': float((bottom < 0).mean()) if len(bottom) else None, 'veto_top20_improvement': float(keep.mean() - all_mean) if len(keep) else None})


def _build_analysis(factor_snapshot: pd.DataFrame, factor_score_snapshot: pd.DataFrame, forward_returns: pd.DataFrame, *, factor_ids: list[str], horizons: list[int], window_key: str, variant_name: str, lineage: dict[str, Any]) -> dict[str, Any]:
    merged_factor = factor_snapshot.merge(forward_returns, on='date', how='left')
    merged_score = factor_score_snapshot.merge(forward_returns, on='date', how='left')
    factors: dict[str, Any] = {}
    for factor_id in factor_ids:
        frame = merged_factor.loc[merged_factor['factor_id'] == factor_id].copy()
        row: dict[str, Any] = {'coverage_ratio': float(frame['availability_flag'].mean()) if len(frame) else 0.0}
        for horizon in horizons:
            row[f'horizon_{horizon}d'] = _summarize(frame, value_col='normalized_value', forward_col=f'forward_return_{horizon}d')
        factors[factor_id] = sanitize_json(row)
    score_row: dict[str, Any] = {'coverage_ratio': float(merged_score['availability_flag'].mean()) if len(merged_score) else 0.0}
    for horizon in horizons:
        score_row[f'horizon_{horizon}d'] = _summarize(merged_score, value_col='normalized_value', forward_col=f'forward_return_{horizon}d')
    return sanitize_json({'factors': factors, 'factor_score': score_row, 'meta': {'study_kind': 'execution_pressure_factor_surface', 'runtime_mode': 'RESEARCH_ONLY', 'window_key': window_key, 'variant_name': variant_name, 'factor_ids': list(factor_ids), 'horizons': list(horizons), 'lineage': lineage}})


def _write_human_summary(path: Path, analysis: dict[str, Any], *, horizons: list[int]) -> None:
    lines = ['# Execution pressure factor study', '', '- runtime_mode: `RESEARCH_ONLY`', '']
    for factor_id, row in dict(analysis.get('factors') or {}).items():
        lines.append(f'## {factor_id}')
        lines.append('')
        lines.append(f"- coverage_ratio: `{row.get('coverage_ratio')}`")
        for horizon in horizons:
            bucket = row.get(f'horizon_{horizon}d') or {}
            lines.append(f"- horizon_{horizon}d.score_forward_corr: `{bucket.get('score_forward_corr')}`")
            lines.append(f"- horizon_{horizon}d.veto_top20_improvement: `{bucket.get('veto_top20_improvement')}`")
        lines.append('')
    score = dict(analysis.get('factor_score') or {})
    lines.extend(['## factor_score', '', f"- coverage_ratio: `{score.get('coverage_ratio')}`"])
    for horizon in horizons:
        bucket = score.get(f'horizon_{horizon}d') or {}
        lines.append(f"- horizon_{horizon}d.score_forward_corr: `{bucket.get('score_forward_corr')}`")
        lines.append(f"- horizon_{horizon}d.veto_top20_improvement: `{bucket.get('veto_top20_improvement')}`")
    path.write_text('\n'.join(lines), encoding='utf-8')


def run_execution_pressure_factor_study(*, study: StudyDefinition, plan: list[dict[str, Any]], write_dual_output: bool = True, append_to_baseline: bool = True) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    for item in list(plan or []):
        payload = dict(item.get('request_payload') or {})
        factor_ids = _parse_factor_ids(payload)
        factor_weights = _parse_factor_weights(payload, factor_ids=factor_ids)
        horizons = _parse_horizons(payload)
        start = str(payload.get('start_date') or '')
        end = str(payload.get('end_date') or '')
        frame, lineage = load_execution_pressure_frame(payload, start=start, end=end)
        factor_snapshot = build_execution_pressure_factor_snapshots(frame, factor_ids=factor_ids)
        factor_score_snapshot = build_execution_pressure_factor_score_snapshot(factor_snapshot, factor_ids=factor_ids, factor_weights=factor_weights)
        forward_returns = _attach_forward_returns(frame, horizons=horizons)
        analysis = _build_analysis(factor_snapshot, factor_score_snapshot, forward_returns, factor_ids=factor_ids, horizons=horizons, window_key=str(item.get('window_key') or ''), variant_name=str(item.get('variant_name') or ''), lineage=lineage)
        run_dir = _study_run_dir(study, window_key=str(item.get('window_key') or ''), variant_name=str(item.get('variant_name') or ''))
        machine_dir = (run_dir / 'machine').resolve()
        human_dir = (run_dir / 'human').resolve()
        machine_dir.mkdir(parents=True, exist_ok=True)
        human_dir.mkdir(parents=True, exist_ok=True)
        (machine_dir / 'factor_catalog.json').write_text(json.dumps(build_execution_pressure_factor_catalog(), ensure_ascii=False, indent=2), encoding='utf-8')
        factor_snapshot.to_csv(machine_dir / 'factor_snapshot.csv', index=False, encoding='utf-8-sig')
        factor_score_snapshot.to_csv(machine_dir / 'factor_score_snapshot.csv', index=False, encoding='utf-8-sig')
        (machine_dir / 'analysis.json').write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding='utf-8')
        _write_human_summary(human_dir / 'summary.md', analysis, horizons=horizons)
        runs.append(sanitize_json({'window_key': str(item.get('window_key') or ''), 'variant_name': str(item.get('variant_name') or ''), 'results_dir': str(run_dir), 'factor_count': int(len(factor_ids)), 'verdict': 'RESEARCH_ONLY'}))
    return sanitize_json({'status': 'OK', 'runner_mode': 'execution_pressure_factor_surface', 'runs': runs})
