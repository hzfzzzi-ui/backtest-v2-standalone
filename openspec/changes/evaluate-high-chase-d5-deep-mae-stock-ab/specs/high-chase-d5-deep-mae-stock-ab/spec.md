## ADDED Requirements

### Requirement: Deep MAE stock AB MUST use the normal stock runtime
The deep MAE stock AB MUST run through the normal stock experiment runtime.

#### Scenario: Deep MAE stock candidate runs
- **WHEN** a deep MAE stock AB candidate is executed
- **THEN** orders, fills, cash, positions, NAV, and metrics MUST come from the
  normal runtime ledger
- **AND** the study MUST NOT use shadow rows as executable input
- **AND** the study MUST NOT assemble or compare ETF/combo NAV

### Requirement: Deep MAE stock AB MUST isolate MAE-depth behavior
The deep MAE stock AB MUST only change High Chase + D5 MAE thresholds and watch
action parameters.

#### Scenario: Candidate payload is built
- **WHEN** a deep MAE stock variant is materialized
- **THEN** stock universe, ranking, entry rules, execution timing, costs, sizing,
  and baseline defaults MUST remain unchanged except window bounds
- **AND** runtime `strategy.params` MUST contain explicit D5 MAE-depth
  parameters for candidate variants

### Requirement: Deep MAE stock conclusion MUST compare against same-window B0
The deep MAE stock conclusion MUST compare each candidate against same-window
`B0_V3_STOCK_REPLAY`.

#### Scenario: Results are analyzed
- **WHEN** B0 and candidate exp ids exist for a window
- **THEN** the report MUST compare total return, CAGR, Sharpe, max drawdown,
  Calmar, trades, immediate D5 exit count, and watch D5 exit count
- **AND** it MUST state continue, reject, or hold without promoting a baseline
