## 1. Contract

- [x] 1.1 Add OpenSpec proposal/design/spec/tasks.
- [x] 1.2 Validate OpenSpec in strict mode.

## 2. Runtime Implementation

- [x] 2.1 Add default-off peak-giveback MA20 strategy params.
- [x] 2.2 Preserve params through strategy registry and vector provider models.
- [x] 2.3 Implement partial sell signal with reason code `PEAK_GIVEBACK_MA20_EXIT`.

## 3. Research Surface

- [x] 3.1 Add stock-only AB study variants for B0 and giveback thresholds.
- [x] 3.2 Ensure study variants patch only the new strategy params.
- [x] 3.3 Include reason-code counts in the study result analysis if available.

## 4. Verification

- [x] 4.1 Add focused unit tests for default-off behavior, trigger behavior, and param preservation.
- [x] 4.2 Run local unit tests.
- [x] 4.3 Run Docker unit tests and dry-run.
- [x] 4.4 Run Docker 2016-2026 main-window AB.
- [ ] 4.5 If interpretable, run Docker 2012-2017 and 2012-2026. Not run yet: main-window result is mixed and fails the drawdown-preservation acceptance check.

## 5. Reporting

- [x] 5.1 Report same-window metrics, reason-code counts, and recent 2025 computer impact.
- [x] 5.2 State continue/reject/hold without baseline promotion.
