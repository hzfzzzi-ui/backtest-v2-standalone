## ADDED Requirements

### Requirement: High Chase D5 AB MUST use real runtime execution
The system MUST evaluate High Chase + D5 actions through the normal runtime ledger so orders, fills, cash, positions, NAV, and metrics come from one execution chain.

#### Scenario: AB variant runs
- **WHEN** a High Chase D5 AB variant is executed
- **THEN** sell signals MUST be emitted by the stock signal provider at runtime
- **AND** the variant MUST NOT replay precomputed shadow rows as executable orders

### Requirement: High Chase scope MUST be explicit and default-off
The system MUST only apply High Chase scoped D5 behavior when both D5 confirmation exit and high-chase scope are explicitly enabled in runtime parameters.

#### Scenario: Existing V3 config runs
- **WHEN** no High Chase D5 overrides are provided
- **THEN** `mfe_mae_confirmation_scope` MUST behave as `all`
- **AND** no high-chase-specific D5 behavior MUST alter the baseline

### Requirement: High Chase label MUST be based on entry-time observable data
The High Chase label MUST be computed from own-stock entry-time price path and breakout metadata available at the decision bar.

#### Scenario: Held symbol reaches D5 evaluation
- **WHEN** the current bar is a configured D5 evaluation bar after entry
- **THEN** the provider MUST compute high_chase from pre-entry returns, moving-average/ATR extension, and breakout stretch
- **AND** the computation MUST NOT read study output CSV files, TOP30 labels, future returns, industry/theme indexes, or post-exit outcomes

### Requirement: Immediate High Chase D5 action MUST only affect high-chase failures
The immediate action variant MUST sell only when both high_chase and the configured D5 MFE/MAE failure are true.

#### Scenario: High-chase held stock fails day3 D5
- **WHEN** `mfe_mae_confirmation_scope=high_chase`
- **AND** `mfe_mae_confirmation_action=exit`
- **AND** the stock is high_chase at entry
- **AND** close-path MFE is below the configured threshold
- **AND** close-path MAE is at or below the configured threshold
- **THEN** the provider MUST emit a partial sell signal using `mfe_mae_confirmation_exit_pct`

### Requirement: Watch action MUST defer mild failures and sell only unresolved cases
The watch action variant MUST allow a configured day3 failure to enter watch instead of immediately selling, and MUST only sell at review if the trade remains unrepaired.

#### Scenario: Watched position remains unrepaired
- **WHEN** a high-chase position enters D5 watch
- **AND** the review bar is reached while the position is still held
- **AND** close-path MFE remains below the configured recovery threshold
- **AND** current close return remains at or below the configured recovery threshold
- **AND** close-path MAE remains at or below the configured review MAE threshold
- **THEN** the provider MUST emit a partial sell signal with reason `MFE_MAE_CONFIRMATION_WATCH_EXIT`

#### Scenario: Watched position repairs
- **WHEN** a high-chase position enters D5 watch
- **AND** the review bar is reached
- **AND** the recovery conditions are satisfied
- **THEN** the provider MUST clear the watch state
- **AND** it MUST NOT emit a watch-exit sell signal

### Requirement: Same-window conclusions MUST compare B0, all-scope D5, and High Chase D5 variants
The study conclusion MUST prioritize same-window metrics across B0, all-scope D5 immediate, High Chase immediate, High Chase watch, and High Chase delayed confirmation.

#### Scenario: Study results are analyzed
- **WHEN** experiment ids exist for the same window
- **THEN** the conclusion MUST report return, CAGR, Sharpe, max drawdown, Calmar, trade count, turnover, D5 trigger counts, and runtime duration deltas
- **AND** it MUST state whether the result supports continue, reject, or hold
- **AND** it MUST NOT promote the rule to baseline without explicit user instruction and three-window evidence
