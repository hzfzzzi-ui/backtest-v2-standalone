## Summary

This change implemented a sleeve-local governed exposure policy for broad-based CN ETF research without changing Governor truth, stock alpha logic, or the ETF candidate pool. The work added canonical config/schema fields, provider-side exposure translation, audit evidence, and a dedicated broad-based-only study entry.

The study conclusion is clear:

- `GBP_CTRL_TD_CASH` produced the highest `CAGR` in this round (`2.88%`) but also expanded `MaxDD` to `-23.07%` and removed fallback continuity.
- `GBP_LIGHT_ACC_BOND` was effectively identical to the control group.
- `GBP_CTRL_TD_BOND` and `GBP_CTRL_TD_BOND_LOWMIN` underperformed the control.
- No variant reached the standalone ETF target range of `6%-9% CAGR`.
- The current ETF main research line should remain the prior A0 winner semantics, not this governed exposure policy line.

## What Changed

### Config / Contract

- Added broad-based governed exposure policy fields to the semantic config schema:
  - `exposure_policy_family`
  - `policy_scope`
  - `broad_based_only`
  - `layering_policy`
  - `target_selected_count_by_state_5`
  - `fallback_allowed_by_state_5`
- Extended the ETF beta contract owner to normalize and project:
  - policy family / scope
  - layering band / layering activation
  - target selected count source
  - fallback allowed source

Files:
- [semantic_config_schema.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/backtest_v2/semantic_config_schema.py)
- [etf_beta_contract.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/config/etf_beta_contract.py)

### Provider

- Implemented broad-based governed exposure translation in the ETF provider while keeping Governor truth unchanged.
- Added `LIGHT` / `CONTROLLED_TRANS_DOWN` layering semantics and state-based selected-count / fallback resolution.
- Exposed policy and layering diagnostics into day-level signal metadata.

File:
- [cn_etf_beta_signal_provider.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/cn_etf_beta_signal_provider.py)

### Audit

- Added audit evidence and metrics for:
  - `target/actual/fallback`
  - `layering_band`
  - `under_deploy_reason_codes`
  - policy family / scope / sources

File:
- [research_audit.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/audit/research_audit.py)

### Research Entry

- Added a dedicated broad-based-only study entry:
  - [cn_broad_based_governed_exposure_policy.study.yaml](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_broad_based_governed_exposure_policy.study.yaml)

This entry explicitly excludes sector ETF research and keeps the round scoped to broad-based ETF sleeve semantics only.

## Minimal AB

Study:
- `etf/cn_broad_based_governed_exposure_policy`

Variants:
- `CTRL_A0_TOP2_BOND`
- `GBP_LIGHT_ACC_BOND`
- `GBP_CTRL_TD_BOND`
- `GBP_CTRL_TD_CASH`
- `GBP_CTRL_TD_BOND_LOWMIN`

Runs:
- `CTRL_A0_TOP2_BOND` -> `exp_20260326_073152192_7855`
- `GBP_LIGHT_ACC_BOND` -> `exp_20260326_073201629_bf92`
- `GBP_CTRL_TD_BOND` -> `exp_20260326_073209333_dc44`
- `GBP_CTRL_TD_CASH` -> `exp_20260326_073216777_52c7`
- `GBP_CTRL_TD_BOND_LOWMIN` -> `exp_20260326_073224142_7ed7`

Compare outputs:
- [variant_compare.csv](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/study_cn_broad_based_etf_governed_exposure_policy_20260326/variant_compare.csv)
- [summary.json](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/study_cn_broad_based_etf_governed_exposure_policy_20260326/summary.json)

## Results

Control:
- `CTRL_A0_TOP2_BOND`
  - `CAGR 1.99%`
  - `MaxDD -19.46%`
  - `Sharpe 0.240`
  - `avg_actual_exposure 27.25%`

Best CAGR:
- `GBP_CTRL_TD_CASH`
  - `CAGR 2.88%`
  - `MaxDD -23.07%`
  - `Sharpe 0.309`
  - `avg_actual_exposure 22.64%`
  - `avg_actual_fallback_exposure 0.00%`

Other findings:
- `GBP_LIGHT_ACC_BOND`
  - same performance as control in practice
- `GBP_CTRL_TD_BOND`
  - lower `CAGR` than control
- `GBP_CTRL_TD_BOND_LOWMIN`
  - identical to `GBP_CTRL_TD_BOND` in this window; lowering `min_deployable` did not change realized behavior

## Interpretation

Facts:
- Broad-based governed exposure policy can be wired cleanly without changing Governor truth.
- The new policy fields are visible in `run_meta`, `audit`, and day-level diagnostics.
- `CONTROLLED_TRANS_DOWN` and fallback differences are observable in research outputs.

Inference:
- This change improved explainability, not strategy quality.
- `GBP_CTRL_TD_CASH` only improved `CAGR` by accepting worse drawdown and eliminating fallback exposure.
- The broad-based ETF sleeve is still materially underdeployed relative to a standalone ETF target.
- This line does not yet justify promotion to a new ETF main research route.

## Risks

- It is easy to overread the `GBP_CTRL_TD_CASH` result as a new winner; that would be a mistake because the risk trade-off worsened and the standalone CAGR target is still missed.
- The new policy fields add contract surface area. Future ETF changes should reuse the same canonical fields rather than invent parallel names.
- This round still uses the A0 pool and proxy symbols; it does not settle the future asset-pool question.

## Validation

Executed:

```powershell
pytest tests/unit/test_etf_beta_contract.py tests/unit/test_semantic_config_compiler.py tests/unit/test_cn_etf_beta_signal_provider.py tests/unit/test_research_audit_contract.py -q
python -m backend.cli study_run etf/cn_broad_based_governed_exposure_policy --dry-run
docker exec backtest-v2-standalone python -m backend.cli study_run etf/cn_broad_based_governed_exposure_policy
openspec validate study-cn-broad-based-etf-governed-exposure-policy --type change --strict
openspec instructions apply --change "study-cn-broad-based-etf-governed-exposure-policy"
```

## Rollback

Core rollback files:
- [semantic_config_schema.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/backtest_v2/semantic_config_schema.py)
- [etf_beta_contract.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/config/etf_beta_contract.py)
- [cn_etf_beta_signal_provider.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/cn_etf_beta_signal_provider.py)
- [research_audit.py](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/audit/research_audit.py)
- [cn_broad_based_governed_exposure_policy.study.yaml](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_broad_based_governed_exposure_policy.study.yaml)

Output-only artifacts under `outputs/ops/study_cn_broad_based_etf_governed_exposure_policy_20260326/` and the corresponding experiment directories can be deleted after rollback if they are no longer needed.
