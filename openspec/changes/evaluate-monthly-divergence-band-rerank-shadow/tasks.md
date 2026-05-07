## 1. Contract and runtime

- [x] 1.1 Add `band_rerank` to the moneyflow overlay contract
- [x] 1.2 Require and validate `band_limit`
- [x] 1.3 Implement bounded candidate-band rerank in candidate planning
- [x] 1.4 Preserve baseline rank diagnostics alongside post-rerank rank

## 2. Tests

- [x] 2.1 Add unit coverage for contract rejection without `band_limit`
- [x] 2.2 Add unit coverage for candidate-band rerank behavior
- [x] 2.3 Keep existing shadow / soft-weight tests green

## 3. Study

- [x] 3.1 Add `v10/moneyflow_monthly_band_rerank_s1`
- [x] 3.2 Add generated thin script
- [x] 3.3 Run `1217`
- [x] 3.4 Run `1226`
- [x] 3.5 Summarize whether candidate-band rerank is more effective than sizing-only insertion
