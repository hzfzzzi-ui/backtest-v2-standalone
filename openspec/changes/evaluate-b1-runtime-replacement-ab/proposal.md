## Why

B0.1 showed that cash shortage plus stale holdings can hide stronger stock candidates, but that evidence was shadow-only. The next step must be a real runtime AB where orders, cash, fills, NAV, and metrics are produced by the same execution chain.

This change creates the first B1 runtime replacement control study. It deliberately starts with the existing runtime rotation-replacement hook instead of injecting the B0.1 shadow plan, because replaying precomputed shadow rows would break the same-NAV/account-truth contract.

## What Changes

- Add a declarative study `cn_stock_etf/cn_stock_etf_b1_runtime_replacement_ab_v1`.
- Run B0 and B1 through Docker using `runtime_config_json` sourced from the latest V3 stock component run.
- Keep the stock universe, ranking, entry rules, exit rules, costs, execution timing, and ETF leg unchanged.
- Enable only the existing runtime replacement controls for B1.
- Compare B1 against the same-window B0 replay before considering any combo-level promotion.

## Impact

- New OpenSpec change artifacts under `openspec/changes/evaluate-b1-runtime-replacement-ab/`.
- New study YAML under `research/studies/cn_stock_etf/`.
- A focused unit test for the B1 study execution plan.
- Runtime outputs are written under `outputs/experiments` and study/conclusion outputs through the existing study runner.
