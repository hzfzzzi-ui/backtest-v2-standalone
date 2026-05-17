## Context

The previous formal study (`cn_stock_etf_theme_protected_replacement_v1`) was explicitly research-only. It did not create orders, did not recompute NAV, and did not qualify as a baseline promotion test.

The current runtime already has a governed replacement hook in the candidate plan:

- `sizing.rotation_replace_enabled`
- `sizing.rotation_replace_only_strong_risk_on`
- `sizing.rotation_replace_max_swaps_per_day`
- `sizing.rotation_replace_candidate_top_n`
- `sizing.rotation_replace_min_score_gap`

That hook creates real sell/buy orders from the current day account state. It is therefore the lowest-risk path to a real B1 AB.

## Goals

- Run a true runtime AB in Docker.
- Preserve one-variable attribution: only replacement controls change.
- Use `runtime_config_json` rather than `config_json` so the backend runtime config is treated as runtime truth, not frontend semantic config.
- Produce same-window B0 and B1 experiments for main, guardrail, and full-audit windows.

## Non-Goals

- Do not inject `b01_shadow_daily_plan.csv` into runtime.
- Do not implement exact theme-protected replacement in this change.
- Do not modify signal timing, fill timing, stock pool, ETF pool, ranking formula, or exit rules.
- Do not promote a new baseline from this run alone.

## Decision

This B1 is a control runtime AB, not the final theme-protected B1. The exact theme-protected version needs governed runtime inputs for stock themes, ETF theme proxy strength, and protected holding tags before it can be executed without precomputed shadow leakage.

## Risks

- The B1 control may understate the B0.1 shadow idea because it uses score gap rather than theme alignment.
- It can increase turnover because replacement creates an extra sell and buy.
- It may sell positions that the later theme-protected rule would protect.
- Registry comparison to `baseline_V10_1` is secondary; the real decision evidence is same-window B0 vs B1.

## Rollback

Disable B1 by not running the B1 variant or by keeping `sizing.rotation_replace_enabled=false`. No baseline or shared runtime default is changed.
