## ADDED Requirements

### Requirement: Entry-risk position sizing MUST be default-off
The formal stock trend alpha core MUST expose entry-risk position sizing without
changing existing behavior when the switch is not enabled.

#### Scenario: Existing stock config runs
- **WHEN** no entry-risk position sizing override is provided
- **THEN** buy signal ranking, buy eligibility, target sizing, fills, exits, and
  NAV accounting MUST remain unchanged

### Requirement: Entry-risk tier MUST use decision-date information only
The position sizing tier MUST be computed from decision-date buy-candidate
features already observable at signal generation time.

#### Scenario: A buy signal is generated
- **WHEN** entry-risk position sizing is enabled
- **THEN** the tier MUST use only current/past own-stock feature ranks or values
- **AND** it MUST NOT use future returns, realized PnL, TOP30 labels, study
  output files, or post-entry outcomes

### Requirement: Entry-risk action MUST size down normal buys only
The entry-risk action MUST reduce normal buy order value scale and MUST NOT
remove the candidate from ranking or alter exit behavior.

#### Scenario: Normal buy has risk flag count 2
- **WHEN** entry-risk position sizing is enabled
- **THEN** the buy signal MUST remain eligible
- **AND** its normal order value scale MUST be multiplied by the configured
  high-risk multiplier
- **AND** normal lot sizing, cash-aware planning, fill accounting, and later
  exits MUST continue to apply

### Requirement: Restore and delta target buys MUST preserve existing target basis
The AB MUST NOT override buy signals that already carry a delta or restore target
weight basis.

#### Scenario: Restore candidate buy signal is emitted
- **WHEN** the signal has `target_weight_basis = delta_restore_gap`
- **THEN** entry-risk position sizing MUST NOT replace its target weight
- **AND** restore metadata MUST remain authoritative

### Requirement: Entry-risk metadata MUST be auditable
Executed buy orders MUST preserve enough metadata to audit which buys were
reduced.

#### Scenario: Entry-risk sized buy order is created
- **WHEN** a buy order reaches execution planning
- **THEN** order metadata MUST include the tier, flag count, multiplier, original
  order value scale, final order value scale, and resulting target weight

### Requirement: Conclusion MUST compare same-window stock-leg control and AB
The research conclusion MUST prioritize same-window formal stock-leg comparison.

#### Scenario: AB results are analyzed
- **WHEN** control and AB experiment ids exist for the same window
- **THEN** the conclusion MUST compare return, CAGR, Sharpe, max drawdown,
  Calmar, trade count, exposure/position statistics where available, and buys by
  tier
- **AND** it MUST state continue, reject, or hold
- **AND** it MUST NOT promote the rule to a baseline without explicit user
  instruction
