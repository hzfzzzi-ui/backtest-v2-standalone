# V2 Shrink Summary (2026-03-07)

This summary records the shrink results after the first `v2-shrink-pass`
implementation batches.

## Removed or folded surfaces

- deleted `backend/core/engine_vector/strategy_adapter.py`
- folded `backend/core/engine_vector/runtime_surface.py` into
  `backend/core/engine_vector/portfolio_simulator_strict.py`
- deleted `backend/core/strategies/adaptive_regime.py`
- removed the live `adaptive_regime` compatibility branch from
  `backend/core/strategies/registry.py` and
  `backend/api/endpoints/_experiment_runner_api.py`
- removed read-only legacy artifact aliases for `reason_code_counts.csv` and
  `*_count` funnel counters from `backtest_v2_protocol.py`, `backtest_v2.py`,
  `frontend/assets/js/backtest_v2.js`, and `frontend/assets/js/artifacts.js`
- updated `backend/scripts/build_candidates.py` to read the canonical
  `reason_codes.csv` artifact only
- removed the unused `legacy_hits` run-meta field from
  `backend/api/endpoints/backtest_v2_artifacts.py`
- normalized baseline gate conflict-policy comparisons in
  `backend/scripts/baseline_regression_check.py` to current config-governance
  semantics

## Relocated ops-only assets

- moved `backend/scripts/universe_data_audit.py` to
  `backend/scripts/ops/universe_data_audit.py`
- moved cleanup and audit documentation under `docs/ops/`

## Intentionally retained surfaces

- `backend/api/endpoints/_config_governance.py`
  - steady-state config identity boundary
- `backend/scripts/baseline_regression_check.py`
  - steady-state baseline guardrail
- `backend/core/universe/lineage.py`
  - retained as a shared runtime/API/audit contract boundary instead of a
    temporary helper

## Net reduction

Measured backend runtime reduction versus `main` from currently diffable files:
- `backend/core/engine_vector/strategy_adapter.py`: `-72`
- `backend/core/strategies/adaptive_regime.py`: `-357`
- `backend/core/engine_vector/portfolio_simulator_strict.py`: `+8` net

Minimum measured net reduction: `-421` backend lines.

Note:
- the real shrink-pass reduction is larger than `421` lines because
  `runtime_surface.py` was added and later removed within the same branch, so
  it no longer appears in the `main` diff even though the temporary helper was
  eliminated

## Verification

- baseline self-check: `PASS`
- rerun results:
  - `outputs/execution/baseline_regression_rerun_v2_shrink_pass_step1_20260307.json`
  - `outputs/execution/baseline_regression_rerun_v2_shrink_pass_step2_20260307.json`
  - `outputs/execution/baseline_regression_rerun_v2_shrink_pass_step3_ops_20260307.json`
  - `outputs/execution/baseline_regression_rerun_v2_shrink_pass_step4_adaptive_20260307.json`
  - `outputs/execution/baseline_regression_rerun_v2_shrink_pass_step5_adaptive_alias_20260307.json`
  - `outputs/execution/baseline_regression_rerun_v2_shrink_pass_step6_dead_branch_20260307.json`
  - `outputs/execution/baseline_regression_rerun_v2_shrink_pass_step7_artifact_fallbacks_20260307.json`
  - `outputs/execution/baseline_regression_rerun_v2_shrink_pass_step8_conflict_policy_20260307.json`
  - `outputs/execution/baseline_regression_rerun_v2_shrink_pass_step9_legacy_hits_20260307.json`
- rerun gate now passes cleanly with `blocking=0 warning=0 total=0`

## Remaining work

- shrink-pass compatibility cleanup is now materially complete for live runtime
  and active artifact readers
- any further reduction should focus on historical spec/archive references or on
  optional operator-script consolidation rather than live runtime cleanup
