## Why

V3 can reduce A-share exposure through benchmark regime and account state, and it can exit individual stocks through stops and risk-off rules. It does not yet audit whether the theme behind current holdings is losing leadership before the market-level gate or single-name exit fires.

This change adds a research-only C1 theme health shadow study. It consumes the existing V3 industry/theme attribution bundle and produces auditable theme weakening labels for held stock themes. It does not change runtime behavior, NAV, baseline, stock pool, ETF pool, ranking factor, execution timing, or sell rules.

## What Changes

- Add `cn_stock_etf/cn_stock_etf_theme_health_shadow_v1` study definition.
- Add a research-only runner that reads the V3 attribution bundle, computes theme health flags, and writes machine/human outputs.
- Register the runner in `study_runner`.
- Add unit tests for input audit, scoring, runner delegation, and formal outputs.

## Non-Goals

- No runtime sell, buy, replacement, or exposure change.
- No NAV recomputation.
- No baseline promotion.
- No frontend-side research calculation.
- No change to benchmark regime or account state semantics.

## Impact

- Source implementation:
  - `backend/research/theme_health_shadow_study.py`
  - `backend/research/study_runner.py`
  - `research/studies/cn_stock_etf/cn_stock_etf_theme_health_shadow_v1.study.yaml`
  - `tests/unit/test_theme_health_shadow_study.py`
- Output artifacts:
  - `outputs/studies/cn_stock_etf/cn_stock_etf_theme_health_shadow_v1/**`
- Unchanged:
  - `CN_STOCK_ETF_COMBO_BASELINE_V3`
  - trading runtime, signal timing, fill timing, stock/ETF pools, allocation, exits, account state.
