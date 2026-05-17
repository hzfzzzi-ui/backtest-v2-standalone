## Why

Recent shadow studies point to a portfolio-level issue: stale stock holdings can occupy slots while stronger current candidates are blocked by cash or max-position constraints. The next test should be a real stock-leg runtime AB, not another shadow layer.

## What Changes

- Add a research-only study `cn_stock_etf/cn_stock_v4_relative_replacement_stock_ab_v1`.
- Use the current promoted stock baseline runtime config from `outputs/baselines/baseline_V10_1/run_config.json`.
- Compare same-window B0 replay against one replacement variant that enables the existing atomic runtime rotation-replacement hook.
- Keep universe, ranking, entry, exit, sizing base, execution timing, costs, and ETF sleeve unchanged.

## Impact

- Adds one declarative study YAML.
- Adds one focused study-runner contract test.
- Runtime outputs are written only under `outputs/experiments` and study output directories.
