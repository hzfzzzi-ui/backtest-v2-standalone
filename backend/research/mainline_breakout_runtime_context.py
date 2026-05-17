from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
from typing import Any

import numpy as np
import pandas as pd

from backend.core.config.loader import load_config
from backend.core.engine_vector.breakout_signal_provider import BreakoutTrendProvider
from backend.core.stage_pipeline.adapters.route_runtime import precompute_signal_provider
from backend.core.strategies.registry import build_strategy
from backend.core.tools.data_bundle_builder import build_data_bundle


@dataclass(frozen=True, slots=True)
class MainlineBreakoutResearchContext:
    runtime_config: dict[str, Any]
    cfg_obj: Any
    data_bundle: Any
    provider: BreakoutTrendProvider
    dates: pd.DatetimeIndex
    symbols: list[str]
    close_matrix: np.ndarray
    high_matrix: np.ndarray
    low_matrix: np.ndarray
    tradable_matrix: np.ndarray
    risk_on_arr: np.ndarray
    strong_risk_on_arr: np.ndarray
    effective_state_5_arr: np.ndarray
    meta: dict[str, Any]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_runtime_config_path() -> Path:
    return (
        _repo_root()
        / 'outputs'
        / 'experiments'
        / 'exp_20260409_052948616_a4c5'
        / 'run_config.json'
    ).resolve()


def _default_backend_runtime_config_path() -> Path:
    return (_repo_root() / 'backend' / 'configs' / 'pams_cn_pg.json').resolve()


def _resolve_repo_path(path_text: str) -> Path:
    raw = Path(str(path_text or '').strip())
    if raw.is_absolute():
        return raw.resolve()
    return (_repo_root() / raw).resolve()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding='utf-8-sig'))
    return dict(payload) if isinstance(payload, dict) else {}


def _load_runtime_payload(payload: dict[str, Any], *, start: str, end: str) -> dict[str, Any]:
    runtime_config = payload.get('runtime_config_json')
    if isinstance(runtime_config, dict):
        runtime = dict(runtime_config)
    else:
        runtime_path = str(payload.get('runtime_config_path') or '').strip()
        resolved_runtime_path = _resolve_repo_path(runtime_path) if runtime_path else _default_runtime_config_path()
        runtime = _load_json(resolved_runtime_path)
    backend_cfg_path = str(payload.get('config_path') or '').strip()
    backend_cfg = _load_json(_resolve_repo_path(backend_cfg_path)) if backend_cfg_path else _load_json(_default_backend_runtime_config_path())
    for key in ('db', 'db_runtime', 'data_source', 'schema_mapping', 'data_scope'):
        if key in backend_cfg:
            runtime[key] = backend_cfg[key]
    universe = runtime.get('universe')
    if not isinstance(universe, dict):
        universe = {}
        runtime['universe'] = universe
    universe['start'] = start
    universe['end'] = end
    return runtime


def _extract_max_positions(payload: dict[str, Any]) -> int:
    run_params = payload.get('run_params')
    run_params = run_params if isinstance(run_params, dict) else {}
    return int(run_params.get('max_positions') or 10)


def load_mainline_breakout_research_context(
    payload: dict[str, Any],
    *,
    start: str,
    end: str,
) -> MainlineBreakoutResearchContext:
    runtime = _load_runtime_payload(payload, start=start, end=end)
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_path = Path(tmp_dir) / 'runtime_config.json'
        cfg_path.write_text(json.dumps(runtime, ensure_ascii=False, indent=2), encoding='utf-8')
        cfg_obj, _ = load_config(cfg_path)
        bundle = build_data_bundle(
            cfg_obj=cfg_obj,
            cfg_merged=runtime,
            overrides={
                'universe_mode': runtime.get('universe_mode'),
                'asset_scope': runtime.get('asset_scope'),
            },
            rules_path=_repo_root() / 'backend' / 'configs' / 'instrument_rules_cn.csv',
        )
        strategy = build_strategy(cfg_obj.strategy)
        if hasattr(strategy, 'set_context'):
            strategy.set_context({'run_id': 'research_only', 'results_dir': ''})
        strategy.state['universe_filters'] = {
            'min_price': float(bundle.universe_filters_raw.get('price_min', bundle.universe_filters_raw.get('min_price', 0.0)) or 0.0),
            'min_list_days': int(bundle.universe_filters_raw.get('min_list_days', 0) or 0),
            'min_avg_turnover_20d': float(bundle.universe_filters_raw.get('min_avg_turnover_20d', 0.0) or 0.0),
            'min_avg_turnover_rate_20d': float(bundle.universe_filters_raw.get('min_avg_turnover_rate_20d', 0.0) or 0.0),
            'turnover_rate_field': str(bundle.universe_filters_raw.get('turnover_rate_field', 'turnover_rate_f') or 'turnover_rate_f'),
            'exclude_star_market': bool(bundle.universe_filters_raw.get('exclude_star_market', False)),
            'csi1000_new_min_circ_mv_yi': float(bundle.universe_filters_raw.get('csi1000_new_min_circ_mv_yi', 0.0) or 0.0),
            'dynamic_all_a_entry': bool(bundle.dynamic_all_a_entry),
        }
        strategy.state['membership_history'] = bundle.membership_history
        provider = BreakoutTrendProvider()
        precompute_signal_provider(
            provider,
            data_bundle=bundle,
            strategy=strategy,
            exit_cfg=cfg_obj.exit,
            strength_ma=int(getattr(cfg_obj.strategy, 'params', {}).get('strength_ma', 20) or 20),
            initial_cash=float(cfg_obj.initial_capital),
            max_positions=_extract_max_positions(payload),
            history_lookback_days=int(runtime.get('history_lookback_days') or 0) or None,
            enable_multifactor_rank=bool(runtime.get('enable_multifactor_rank', False)),
            mf_rank_gate_mode=str(runtime.get('mf_rank_gate_mode', 'ALWAYS_ON')),
            market_filter_cfg=cfg_obj.market_filter,
            benchmark_regime_cfg=cfg_obj.benchmark_regime,
            regime_engine_cfg=cfg_obj.regime_engine,
            sizing_cfg=cfg_obj.sizing,
            risk_budget_cfg=cfg_obj.risk_budget,
            governed_a_share=runtime.get('governed_a_share') or {},
        )
        mx = provider._mx
        return MainlineBreakoutResearchContext(
            runtime_config=runtime,
            cfg_obj=cfg_obj,
            data_bundle=bundle,
            provider=provider,
            dates=pd.to_datetime(mx.dates),
            symbols=[str(item).lower() for item in list(mx.symbols)],
            close_matrix=np.asarray(mx.close, dtype=float),
            high_matrix=np.asarray(mx.high, dtype=float),
            low_matrix=np.asarray(mx.low, dtype=float),
            tradable_matrix=np.asarray(mx.tradable, dtype=bool),
            risk_on_arr=np.asarray(getattr(provider, '_risk_on', np.array([], dtype=bool)), dtype=bool),
            strong_risk_on_arr=np.asarray(getattr(provider, '_strong_risk_on', np.array([], dtype=bool)), dtype=bool),
            effective_state_5_arr=np.asarray(getattr(provider, '_effective_state_5_arr', np.array([], dtype=object)), dtype=object),
            meta={
                'runtime_config_path': str(payload.get('runtime_config_path') or ''),
                'window_start': start,
                'window_end': end,
                'symbol_count': int(len(mx.symbols)),
                'trading_day_count': int(len(mx.dates)),
                'universe_mode': str(runtime.get('universe_mode') or ''),
                'asset_scope': str(runtime.get('asset_scope') or ''),
            },
        )
