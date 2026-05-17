## ADDED Requirements

### Requirement: D7 post-entry action AB MUST isolate D7 action method
The D7 post-entry action AB MUST only change runtime parameters that control
the D7 MFE/MAE confirmation action.

#### Scenario: Candidate payload is built
- **WHEN** a D7 post-entry action variant is materialized
- **THEN** stock universe, ranking, entry rules, execution timing, costs,
  sizing, D7 scope, D7 MFE threshold, and D7 MAE threshold MUST remain fixed
- **AND** candidate differences MUST be limited to D7 exit fraction, D7
  lookahead bars, or D7 watch-review parameters

### Requirement: D7 post-entry action AB MUST use normal stock runtime
The D7 post-entry action AB MUST run through the normal stock runtime ledger.

#### Scenario: Candidate runs
- **WHEN** the study executes
- **THEN** orders, fills, cash, positions, NAV, and metrics MUST come from the
  normal runtime ledger
- **AND** the study MUST NOT use shadow rows as executable input
- **AND** the study MUST NOT assemble ETF or combo NAV

### Requirement: D7 post-entry action conclusion MUST compare same-window variants
The D7 post-entry action conclusion MUST compare current half-exit, stronger
immediate exits, delayed day5 confirmation, and day10 watch in the same window.

#### Scenario: Results are analyzed
- **WHEN** experiment ids exist for a window
- **THEN** the report MUST compare total return, CAGR, Sharpe, max drawdown,
  Calmar, trades, turnover, and D7 exit/watch count
- **AND** it MUST state continue, reject, or hold without promoting a baseline
