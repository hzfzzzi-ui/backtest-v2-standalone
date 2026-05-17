## ADDED Requirements

### Requirement: Bad breakout quality AB MUST use normal stock runtime
The bad breakout quality AB MUST run through the normal stock experiment
runtime and ledger.

#### Scenario: Candidate is executed
- **WHEN** the bad breakout quality candidate is run
- **THEN** orders, fills, cash, positions, NAV, and metrics MUST come from the
  normal runtime ledger
- **AND** shadow audit rows MUST NOT be used as executable input
- **AND** ETF/combo NAV MUST NOT be assembled or compared

### Requirement: Bad breakout quality veto MUST isolate one rank-based entry condition
The AB candidate MUST only add a default-off breakout entry veto based on
same-day cross-sectional ranks of pre-entry 5-day return and rolling 60-day
trend R2.

#### Scenario: Candidate parameters are enabled
- **WHEN** `bad_breakout_quality_veto_enabled` is true
- **THEN** breakout entries with
  `ret5_rank >= bad_breakout_quality_ret5_rank_min` and
  `r2_60_rank <= bad_breakout_quality_r2_60_rank_max` MUST be excluded before
  candidate indexing
- **AND** the candidate MUST NOT use fixed absolute thresholds copied from the
  shadow sample
- **AND** stock universe, ranking, exits, sizing, execution timing, costs, and
  account ledger MUST remain unchanged

### Requirement: Bad breakout quality AB MUST compare same-window B0
The AB conclusion MUST compare the candidate against a same-window stock B0.

#### Scenario: Main-window results are available
- **WHEN** B0 and candidate experiment ids exist for 2016-2026
- **THEN** the report MUST compare total return, CAGR, Sharpe, max drawdown,
  Calmar, trade count, average positions, and diagnostic veto count
- **AND** it MUST state continue, reject, or hold without promoting a baseline
