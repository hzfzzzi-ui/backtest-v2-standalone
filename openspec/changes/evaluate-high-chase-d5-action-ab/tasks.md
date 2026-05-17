## 1. Contract

- [x] 1.1 Create proposal/design/spec/tasks and pass strict validation. DoD: research-only scope, same-window AB control, no baseline behavior change by default. Verification: `openspec validate evaluate-high-chase-d5-action-ab --strict`.
- [x] 1.2 Add study YAML with B0, all-scope D5 immediate, High Chase immediate, High Chase watch, and High Chase delayed-confirm variants. DoD: study loader can build the plan and unit tests cover scoped patches.

## 2. Runtime Implementation

- [x] 2.1 Add default-off strategy/provider parameter mapping. DoD: behavior is unchanged without config patches. Verification: strategy/provider mapping tests.
- [x] 2.2 Implement High Chase scope inside D5 runtime exit logic. DoD: uses entry-time own-stock price and breakout data only, not shadow outputs. Verification: unit tests.
- [x] 2.3 Implement `exit` and `watch_day10` actions. DoD: immediate half-exit, watch repair cancellation, and day10 half-exit behavior are testable. Verification: unit tests.

## 3. Verification

- [x] 3.1 Add signal-layer unit tests. DoD: cover high-chase scoped immediate, non-high-chase skip, and watch day10 exit. Verification: `pytest tests/unit/test_breakout_signal_provider.py`.
- [x] 3.2 Add study runner unit test. DoD: same runtime source and only High Chase D5 parameters are patched. Verification: `pytest tests/unit/test_study_runner.py`.
- [x] 3.3 Run local dry-run and Docker dry-run. DoD: study plan generation succeeds in both environments.

## 4. Runtime AB

- [x] 4.1 Run 2016-2026 main window. DoD: collect exp_id, perf, trigger counts, and runtime duration for every variant.
- [x] 4.2 Run 2012-2017 hard gate and 2012-2026 full-cycle windows. DoD: complete three-window same-window AB matrix.
- [x] 4.3 Write journal and conclusion. DoD: front-end study page can see the study round; conclusion separates facts, inference, and decision.
