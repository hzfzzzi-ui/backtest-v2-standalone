# Implementation Notes

## Outcome

This change is implemented and study-complete.

Recommendation:

- Keep `CTRL_MAINLINE_A0` as the current broad-based ETF mainline control.
- Do **not** promote any of the new filter / pool / selection variants.

The control variant remained the best CAGR result in the overlap window `2021-03-31 ~ 2026-03-24`:

- `CTRL_MAINLINE_A0`: `CAGR 2.3139%`, `MaxDD -15.0826%`, `Sharpe 0.2439`

The tested variants did not beat the control on both return and robustness:

- `FILTER_MA200_ONLY`: materially worse
- `FILTER_MA150_RET12`: slightly below control
- `POOL_PROXY_EXPANDED`: slightly below control
- `POOL_STANDARD_OVERLAP`: clearly worse
- `CHAIN_TOP2_6_3_1`: slightly lower CAGR with slightly better drawdown
- `CHAIN_CORE_GROWTH_SLOT`: clearly worse

## Main finding

The current broad-based ETF mainline bottleneck is still dominated by the absolute filter layer, not by the pool or selection-chain variants tested in this round.

Control-group audit readout:

- `primary_bottleneck_layer = absolute_filter`
- `absolute_filter_reject_day_count = 1065`
- `avg_target_exposure = 0.6566`
- `avg_actual_exposure = 0.4127`
- `deployment_assessment = TRACEABLE`

This means the new profile instrumentation is useful, but the tested profile swaps did not solve the main return problem.

## Study artifacts

Primary outputs:

- `outputs/ops/study_cn_broad_based_etf_mainline_filter_pool_selection_20260326/variant_compare.csv`
- `outputs/ops/study_cn_broad_based_etf_mainline_filter_pool_selection_20260326/summary.json`

Study experiments:

- `CTRL_MAINLINE_A0` -> `exp_20260326_091603657_f59b`
- `FILTER_MA200_ONLY` -> `exp_20260326_091608621_b511`
- `FILTER_MA150_RET12` -> `exp_20260326_091613482_8064`
- `POOL_PROXY_EXPANDED` -> `exp_20260326_091618328_674e`
- `POOL_STANDARD_OVERLAP` -> `exp_20260326_091623193_d0ab`
- `CHAIN_TOP2_6_3_1` -> `exp_20260326_091628109_42c1`
- `CHAIN_CORE_GROWTH_SLOT` -> `exp_20260326_091632996_b158`

Control rerun for regression:

- `CTRL_MAINLINE_A0` rerun -> `exp_20260326_092041779_6d9b`

Regression conclusion:

- `perf.json`: identical
- `nav.csv`: identical hash
- key ETF audit metrics: identical

## Verification

Completed verification:

```bash
pytest tests/unit/test_etf_beta_contract.py tests/unit/test_semantic_config_compiler.py tests/unit/test_cn_etf_beta_signal_provider.py tests/unit/test_research_audit_contract.py -q
python -m py_compile backend/api/backtest_v2/semantic_config_schema.py backend/core/config/etf_beta_contract.py backend/core/engine_vector/cn_etf_beta_signal_provider.py backend/core/audit/research_audit.py
python -m backend.cli study_run etf/cn_broad_based_mainline_filter_pool_selection --dry-run
docker exec backtest-v2-standalone python -m backend.cli study_run etf/cn_broad_based_mainline_filter_pool_selection
docker exec backtest-v2-standalone python -m backend.cli study_run etf/cn_broad_based_mainline_filter_pool_selection --variant CTRL_MAINLINE_A0
python -m backend.cli experiment_compare exp_20260326_091603657_f59b exp_20260326_092041779_6d9b
openspec validate study-cn-broad-based-etf-mainline-filter-pool-selection --type change --strict
```

## Risks

- This round adds more ETF profile branches to the provider. Even with contract-owner cleanup, the provider will continue to grow if future ETF experiments are not narrowed.
- The result still relies on the A0 proxy broad-based pool. This round does not prove that a standard-only pool is production-ready.
- The study proves observability and bottleneck localization, but it does not prove that the ETF standalone mainline has reached the target CAGR band.

## Rollback

If this change needs to be reverted, remove the new profile families and audit fields from:

- `backend/api/backtest_v2/semantic_config_schema.py`
- `backend/core/config/etf_beta_contract.py`
- `backend/core/engine_vector/cn_etf_beta_signal_provider.py`
- `backend/core/audit/research_audit.py`
- `research/studies/etf/cn_broad_based_mainline_filter_pool_selection.study.yaml`
- `research/studies/etf/cn_broad_based_mainline_filter_pool_selection.base_config.json`
- `tests/unit/test_etf_beta_contract.py`
- `tests/unit/test_cn_etf_beta_signal_provider.py`
- `tests/unit/test_research_audit_contract.py`
- `tests/unit/test_semantic_config_compiler.py`

The generated study artifacts under `outputs/ops/study_cn_broad_based_etf_mainline_filter_pool_selection_20260326/` can be deleted without affecting source behavior.
