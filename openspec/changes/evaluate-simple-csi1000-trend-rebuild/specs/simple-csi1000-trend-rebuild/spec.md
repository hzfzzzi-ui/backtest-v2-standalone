## ADDED Requirements

### Requirement: Simple CSI1000 trend rebuild MUST be research-only
The first simple trend rebuild MUST run as an isolated research study and MUST
NOT mutate any formal baseline or production runtime behavior.

#### Scenario: Study is executed
- **WHEN** the simple trend rebuild runs
- **THEN** it MUST write outputs under `outputs/studies/`
- **AND** it MUST NOT alter baseline configs, production strategies, orders,
  fills, account state, or combo allocation.

### Requirement: Study MUST include CSI1000 in the stock pool
The study MUST use a PIT stock pool that includes CSI1000 constituents.

#### Scenario: Universe is built
- **WHEN** the study resolves a trading date universe
- **THEN** it MUST include PIT `000906.SH` and PIT `000852.SH` constituents
- **AND** it MUST record membership bucket attribution for traded symbols.

### Requirement: Trading rules MUST stay plain
The first version MUST avoid complex market, industry, theme, residual, or
failure-state rules.

#### Scenario: Candidates are scored
- **WHEN** the study ranks stocks
- **THEN** it MUST use simple stock-level trend and liquidity fields only
- **AND** it MUST NOT use industry health, market-style labels, theme labels,
  future returns, future MFE/MAE, or realized outcomes as inputs.

### Requirement: Results MUST include risk and attribution
The study conclusion MUST not only report return.

#### Scenario: Results are summarized
- **WHEN** the study completes
- **THEN** it MUST report CAGR, max drawdown, Sharpe, Calmar, trade count,
  turnover, and average positions
- **AND** it MUST report contribution by membership bucket.

### Requirement: Optional market filter branch MUST remain plain and comparable
A second research-only branch MUST remain plain and comparable if it adds an
index trend filter after the no-filter first version is measured. This branch
MUST remain simpler than the production market-state system.

#### Scenario: Market-filter branch is executed
- **WHEN** the branch decides whether to hold stock exposure
- **THEN** it MAY use only same-day available broad index close versus MA120
- **AND** it MUST NOT use industry health, theme labels, realized stock trade
  outcomes, or tuned failure/watch states
- **AND** it MUST report the same metrics as the no-filter branch.

### Requirement: Entry risk scaled branch MUST isolate position sizing
An entry risk scaled branch MUST only change target weights using fixed
entry-time risk tiers.

#### Scenario: Entry risk scaled branch is executed
- **WHEN** the branch assigns portfolio weights
- **THEN** it MUST keep the same PIT universe, candidate filters, ranking, entry
  dates, exit logic, and costs as the plain branch
- **AND** it MUST derive risk tiers only from entry-time price, volatility, and
  PIT membership fields
- **AND** it MUST leave unused exposure as cash instead of reallocating it to
  other symbols
- **AND** it MUST report same-window comparison against the plain branch.
