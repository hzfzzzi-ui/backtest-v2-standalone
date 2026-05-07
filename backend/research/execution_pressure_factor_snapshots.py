from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from backend.api.shared.json_utils import sanitize_json
from backend.research.execution_pressure_factor_catalog import list_execution_pressure_factor_ids


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_repo_path(path_text: str) -> Path:
    raw = Path(str(path_text or '').strip())
    if raw.is_absolute():
        return raw.resolve()
    return (_repo_root() / raw).resolve()


def _default_portfolio_daily_path() -> Path:
    return (_repo_root() / 'outputs' / 'experiments' / 'exp_20260409_052948616_a4c5' / 'portfolio_daily.csv').resolve()


def load_execution_pressure_frame(payload: dict[str, object], *, start: str, end: str) -> tuple[pd.DataFrame, dict[str, object]]:
    path_text = str(payload.get('portfolio_daily_path') or '').strip()
    path = _resolve_repo_path(path_text) if path_text else _default_portfolio_daily_path()
    frame = pd.read_csv(path, encoding='utf-8-sig')
    frame['date'] = pd.to_datetime(frame['date'])
    frame = frame.loc[(frame['date'] >= pd.Timestamp(start)) & (frame['date'] <= pd.Timestamp(end))].copy()
    if frame.empty:
        raise ValueError(f'execution pressure source has no rows in window: {path}')
    return frame.reset_index(drop=True), {'portfolio_daily_path': str(path), 'window_start': start, 'window_end': end, 'row_count': int(len(frame))}


def _safe_ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    den_safe = den.astype(float).replace(0.0, np.nan)
    return (num.astype(float) / den_safe).fillna(0.0).clip(lower=0.0)


def _asof_timestamp(date_text: str) -> str:
    return f'{date_text}T15:00:00+08:00'


def build_execution_pressure_factor_snapshots(frame: pd.DataFrame, *, factor_ids: list[str] | None = None) -> pd.DataFrame:
    selected = [str(item).strip().lower() for item in list(factor_ids or []) if str(item).strip()] or list_execution_pressure_factor_ids()
    work = frame.copy()
    work['cash_ratio'] = (work['cash'].astype(float) / work['nav'].astype(float).replace(0.0, np.nan)).fillna(0.0).clip(lower=0.0)
    work['slot_overhang_pressure'] = _safe_ratio(np.maximum(work['buy_candidate_count'].astype(float) - work['after_slot_filter_count'].astype(float), 0.0), np.maximum(work['buy_candidate_count'].astype(float), 1.0)).clip(upper=1.0)
    work['cash_lot_pressure'] = _safe_ratio(np.maximum(work['after_slot_filter_count'].astype(float) - work['after_cash_lot_count'].astype(float), 0.0), np.maximum(work['after_slot_filter_count'].astype(float), 1.0)).clip(upper=1.0)
    work['budget_reject_pressure'] = _safe_ratio(work['sleeve_budget_reject_count'].astype(float), np.maximum(work['buy_candidate_count'].astype(float), 1.0)).clip(upper=1.0)
    work['deployment_gap_pressure'] = _safe_ratio(np.maximum(work['buy_slots_calculated'].astype(float) - work['selected_count'].astype(float), 0.0), np.maximum(work['buy_slots_calculated'].astype(float), 1.0)).clip(upper=1.0)
    work['underexposure_pressure'] = np.maximum(1.0 - work['gross_exposure'].astype(float), 0.0).clip(upper=1.0)
    work['cash_drag_pressure'] = work['cash_ratio'].clip(upper=1.0)
    rows: list[dict[str, object]] = []
    for _, record in work.iterrows():
        date_text = pd.Timestamp(record['date']).strftime('%Y-%m-%d')
        for factor_id in selected:
            raw_value = float(record[factor_id])
            rows.append(sanitize_json({'date': date_text, 'factor_id': factor_id, 'scope': 'stock_sleeve_account', 'raw_value': raw_value, 'normalized_value': float(np.clip(raw_value, 0.0, 1.0)), 'availability_flag': True, 'asof_timestamp': _asof_timestamp(date_text), 'source_trace': json.dumps({'source': 'stock_sleeve_portfolio_daily', 'inputs': ['buy_candidate_count', 'after_slot_filter_count', 'after_cash_lot_count', 'selected_count', 'buy_slots_calculated', 'sleeve_budget_reject_count', 'gross_exposure', 'cash', 'nav']}, ensure_ascii=False, sort_keys=True)}))
    return pd.DataFrame(rows)


def build_execution_pressure_factor_score_snapshot(factor_snapshot: pd.DataFrame, *, factor_ids: list[str], factor_weights: dict[str, float]) -> pd.DataFrame:
    subset = factor_snapshot.loc[factor_snapshot['factor_id'].isin(factor_ids)].copy()
    if subset.empty:
        return pd.DataFrame(columns=['date', 'factor_id', 'scope', 'raw_value', 'normalized_value', 'availability_flag', 'asof_timestamp', 'source_trace'])
    subset['weight'] = subset['factor_id'].map(lambda item: float(factor_weights.get(item, 0.0)))
    scored = (subset.loc[subset['weight'].ne(0.0)].assign(weighted=lambda frame: frame['normalized_value'] * frame['weight']).groupby('date', as_index=False).agg(raw_value=('weighted', 'sum'), weight_sum=('weight', 'sum'), factor_count=('factor_id', 'size')))
    if scored.empty:
        return pd.DataFrame(columns=['date', 'factor_id', 'scope', 'raw_value', 'normalized_value', 'availability_flag', 'asof_timestamp', 'source_trace'])
    scored['normalized_value'] = (scored['raw_value'] / scored['weight_sum']).fillna(0.0).clip(lower=0.0, upper=1.0)
    rows = [sanitize_json({'date': str(row['date']), 'factor_id': 'execution_pressure_score', 'scope': 'stock_sleeve_account', 'raw_value': float(row['normalized_value']), 'normalized_value': float(row['normalized_value']), 'availability_flag': bool(row['factor_count'] > 0), 'asof_timestamp': _asof_timestamp(str(row['date'])), 'source_trace': json.dumps({'components': list(factor_ids), 'weights': {factor_id: float(factor_weights.get(factor_id, 0.0)) for factor_id in factor_ids}}, ensure_ascii=False, sort_keys=True)}) for _, row in scored.iterrows()]
    return pd.DataFrame(rows)
