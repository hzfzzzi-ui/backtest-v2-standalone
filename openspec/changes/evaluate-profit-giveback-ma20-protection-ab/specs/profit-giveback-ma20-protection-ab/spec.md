## ADDED Requirements

### Requirement: Peak-giveback MA20 protection MUST be default-off
The peak-giveback MA20 protection rule MUST NOT affect existing stock runtime
behavior unless explicitly enabled by strategy params.

#### Scenario: Default strategy is built
- **WHEN** a breakout strategy is built without peak-giveback MA20 params
- **THEN** `enable_peak_giveback_ma20_exit` MUST be false
- **AND** no `PEAK_GIVEBACK_MA20_EXIT` orders MUST be emitted

### Requirement: Peak-giveback MA20 protection MUST use only live-safe runtime inputs
The protection rule MUST only use current or prior runtime data available on the
decision day.

#### Scenario: Candidate exit is evaluated
- **WHEN** the rule evaluates a held stock
- **THEN** it MAY use average cost, current close, existing peak close state,
  bars since entry, and current MA20
- **AND** it MUST NOT use future return, future MFE/MAE, shadow labels,
  industry/theme labels, or manually selected symbols

### Requirement: Peak-giveback MA20 protection MUST isolate one behavior
The AB study MUST isolate the peak-giveback MA20 exit behavior.

#### Scenario: Study variant is materialized
- **WHEN** a candidate variant is built
- **THEN** stock universe, PIT membership, ranking, entry rules, execution
  timing, costs, sizing, market regime, ETF leg, and combo allocator MUST remain
  unchanged except window bounds
- **AND** only the peak-giveback MA20 strategy params MAY differ from B0

### Requirement: Peak-giveback MA20 conclusion MUST compare against same-window B0
The study conclusion MUST compare each candidate against same-window B0.

#### Scenario: Results are analyzed
- **WHEN** B0 and candidate exp ids exist for a window
- **THEN** the report MUST compare total return, CAGR, Sharpe, max drawdown,
  Calmar, trades, and `PEAK_GIVEBACK_MA20_EXIT` count
- **AND** it MUST state continue, reject, or hold without promoting a baseline
