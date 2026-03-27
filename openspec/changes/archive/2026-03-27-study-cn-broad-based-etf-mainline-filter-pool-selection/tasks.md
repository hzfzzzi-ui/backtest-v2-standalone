# Tasks

## 1. Control and research profiles

- [x] 1.1 Freeze the current broad-based ETF mainline control and add `absolute_filter_profile`, `candidate_pool_profile`, and `selection_chain_profile` to the ETF contract and semantic schema.
- [x] 1.2 Define three minimal AB matrices for the broad-based ETF mainline: filter family, candidate-pool family, and selection-chain family.

## 2. Provider and observability

- [x] 2.1 Implement absolute-filter profiles in the ETF provider and emit reject counts plus reason codes.
- [x] 2.2 Implement candidate-pool profiles in the ETF provider and emit pool coverage plus in-pool / out-of-pool reason codes.
- [x] 2.3 Implement selection-chain profiles in the ETF provider and emit winner / reject diagnostics.

## 3. Research entry and audit

- [x] 3.1 Update the ETF research entry so this round only accepts broad-based ETF mainline profiles.
- [x] 3.2 Extend research audit so it emits explicit bottleneck evidence for `absolute_filter`, `candidate_pool`, and `selection_chain`.

## 4. Study, regression, and implementation notes

- [x] 4.1 Run the three minimal AB study families and write a unified `variant_compare.csv` plus `summary.json` under `outputs/ops/study_cn_broad_based_etf_mainline_filter_pool_selection_20260326/`.
- [x] 4.2 Re-run the control variant and confirm no unrelated drift in key `perf/nav/audit` outputs.
- [x] 4.3 Add `implementation_notes.md` with the winning variant, failed variants, risks, verification, and rollback guidance.
