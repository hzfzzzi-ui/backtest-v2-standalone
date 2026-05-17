## ADDED Requirements

### Requirement: Risk archetype soft deprioritize AB MUST use normal stock runtime
The risk archetype soft deprioritize AB MUST run through the normal stock
experiment runtime and ledger.

#### Scenario: Candidate is executed
- **WHEN** the risk archetype candidate is run
- **THEN** orders, fills, cash, positions, NAV, and metrics MUST come from the
  normal runtime ledger
- **AND** shadow audit rows MUST NOT be used as executable input
- **AND** ETF/combo NAV MUST NOT be assembled or compared

### Requirement: Risk archetype soft deprioritize MUST not hard-veto candidates
The AB candidate MUST only reduce candidate `final_score` through a default-off
score scale and MUST NOT remove buy candidates directly.

#### Scenario: Candidate parameters are enabled
- **WHEN** `risk_archetype_soft_deprioritize_enabled` is true
- **THEN** same-day buy candidates with hot/crowded or high-volatility chase
  flags MUST receive a score scale before candidate indexing
- **AND** the candidate MUST NOT change stock universe, entries, exits, sizing,
  execution timing, costs, or account ledger
- **AND** candidates MUST remain eligible for execution if enough slots or cash
  are available

### Requirement: Risk archetype soft deprioritize AB MUST compare same-window B0
The AB conclusion MUST compare the candidate against a same-window stock B0.

#### Scenario: Main-window results are available
- **WHEN** B0 and candidate experiment ids exist for 2016-2026
- **THEN** the report MUST compare total return, CAGR, Sharpe, max drawdown,
  Calmar, trade count, average positions, and risk-archetype trigger counts
- **AND** it MUST state continue, reject, or hold without promoting a baseline
