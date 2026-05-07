from __future__ import annotations

import json
from typing import Any

from backend.api.shared.json_utils import sanitize_json
from backend.research.mainline_breakout_runtime_context import load_mainline_breakout_research_context
from backend.research.mainline_factor_surface_common import (
    analyze_fragility_surface,
    build_forward_return_snapshot,
    parse_factor_ids,
    parse_factor_weights,
    parse_horizons,
    parse_symbols,
    study_run_dir,
    subset_columns,
    write_human_summary,
)
from backend.research.stock_lifecycle_fragility_catalog import (
    build_stock_lifecycle_fragility_catalog,
    list_stock_lifecycle_fragility_factor_ids,
)
from backend.research.stock_lifecycle_fragility_snapshots import (
    build_stock_lifecycle_fragility_factor_score_snapshot,
    build_stock_lifecycle_fragility_snapshots,
)
from backend.research.study_definition import StudyDefinition


def run_stock_lifecycle_fragility_study(
    *,
    study: StudyDefinition,
    plan: list[dict[str, Any]],
    write_dual_output: bool = True,
    append_to_baseline: bool = True,
) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    for item in list(plan or []):
        payload = dict(item.get('request_payload') or {})
        factor_ids = parse_factor_ids(payload, default_factor_ids=list_stock_lifecycle_fragility_factor_ids())
        factor_weights = parse_factor_weights(payload, factor_ids=factor_ids)
        horizons = parse_horizons(payload, default=[5, 10, 20])
        symbols = parse_symbols(payload)
        start = str(payload.get('start_date') or '')
        end = str(payload.get('end_date') or '')
        context = load_mainline_breakout_research_context(payload, start=start, end=end)
        selected_symbols, selected_idx = subset_columns(context.symbols, symbols)
        factor_snapshot = build_stock_lifecycle_fragility_snapshots(context, factor_ids=factor_ids, symbols=selected_symbols)
        factor_score_snapshot = build_stock_lifecycle_fragility_factor_score_snapshot(
            factor_snapshot,
            factor_ids=factor_ids,
            factor_weights=factor_weights,
        )
        forward_returns = build_forward_return_snapshot(
            dates=context.dates,
            symbols=selected_symbols,
            close_matrix=context.close_matrix[:, selected_idx],
            horizons=horizons,
        )
        analysis = analyze_fragility_surface(
            factor_snapshot=factor_snapshot,
            factor_score_snapshot=factor_score_snapshot,
            forward_returns=forward_returns,
            horizons=horizons,
        )
        run_dir = study_run_dir(
            study,
            window_key=str(item.get('window_key') or ''),
            variant_name=str(item.get('variant_name') or ''),
        )
        machine_dir = (run_dir / 'machine').resolve()
        human_dir = (run_dir / 'human').resolve()
        machine_dir.mkdir(parents=True, exist_ok=True)
        human_dir.mkdir(parents=True, exist_ok=True)
        (machine_dir / 'factor_catalog.json').write_text(
            json.dumps(build_stock_lifecycle_fragility_catalog(), ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        factor_snapshot.to_csv(machine_dir / 'factor_snapshot.csv', index=False, encoding='utf-8-sig')
        factor_score_snapshot.to_csv(machine_dir / 'factor_score_snapshot.csv', index=False, encoding='utf-8-sig')
        (machine_dir / 'analysis.json').write_text(
            json.dumps(
                sanitize_json(
                    {
                        **analysis,
                        'meta': {
                            'study_kind': 'stock_lifecycle_fragility_surface',
                            'runtime_mode': 'RESEARCH_ONLY',
                            'window_key': str(item.get('window_key') or ''),
                            'variant_name': str(item.get('variant_name') or ''),
                            'factor_ids': list(factor_ids),
                            'horizons': list(horizons),
                            'symbol_count': int(len(selected_symbols)),
                            'lineage': dict(context.meta),
                        },
                    }
                ),
                ensure_ascii=False,
                indent=2,
            ),
            encoding='utf-8',
        )
        write_human_summary(
            human_dir / 'summary.md',
            title='Stock lifecycle fragility study',
            study_kind='stock_lifecycle_fragility_surface',
            analysis=analysis,
            horizons=horizons,
        )
        runs.append(
            sanitize_json(
                {
                    'window_key': str(item.get('window_key') or ''),
                    'variant_name': str(item.get('variant_name') or ''),
                    'results_dir': str(run_dir),
                    'factor_count': int(len(factor_ids)),
                    'symbol_count': int(len(selected_symbols)),
                    'verdict': 'RESEARCH_ONLY',
                }
            )
        )
    return {
        'status': 'OK',
        'runner_mode': 'stock_lifecycle_fragility_surface',
        'runs': runs,
    }
