## 1. Contract

- [x] 1.1 Create proposal/design/spec/tasks and pass strict validation. DoD: research-only scope, default-off switch, same-window stock-leg B0/A2 control, no baseline behavior change by default. Verification: `openspec validate evaluate-high-chase-a2-size-down-ab --strict`.

## 2. Runtime Implementation

- [x] 2.1 Add default-off A2 sizing config fields. DoD: existing configs construct successfully and default values preserve B0.
- [x] 2.2 Attach decision-date A2 feature values to stock buy signal metadata. DoD: values use current/past own-stock data only.
- [x] 2.3 Apply A2 size-down inside candidate buy planning before lot/cash feasibility. DoD: triggered candidates keep their buy signal but have reduced `order_value_scale`.
- [x] 2.4 Preserve A2 diagnostics in order meta/debug output. DoD: executed buys can be counted by trigger state.

## 3. Verification

- [x] 3.1 Add targeted unit tests for disabled parity and enabled size-down.
- [x] 3.2 Run targeted local tests.
- [x] 3.3 Run Docker B0/A2 stock-leg AB on the current main window and collect comparable metrics.

## 4. Conclusion

- [x] 4.1 Report facts, inference, decision, risk, and rollback path.
