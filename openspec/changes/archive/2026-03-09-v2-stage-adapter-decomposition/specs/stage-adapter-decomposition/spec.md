## ADDED Requirements

### Requirement: The stage adapter SHALL be decomposed behind one public entrypoint
The backend SHALL keep a single public adapter entrypoint for the stage shell while decomposing the
internal implementation into explicit modules with narrow responsibilities.

#### Scenario: Public adapter entrypoint remains stable
- **WHEN** the foundation shell invokes the stage adapter for a single run
- **THEN** the backend SHALL continue to use one public adapter entrypoint
- **AND** internal module extraction SHALL remain invisible to the public request chain

### Requirement: Candidate flow, holding flow, and order planning SHALL have separate internal ownership
The backend SHALL isolate candidate flow stage logic, holding flow stage logic, and S7 order
planning logic into separate internal modules.

#### Scenario: Candidate flow is isolated
- **WHEN** the adapter produces `S1` through `S6` outputs
- **THEN** those outputs SHALL be assembled by candidate-flow-specific internal logic

#### Scenario: Holding flow is isolated
- **WHEN** the adapter produces `S9` and `S8` outputs
- **THEN** those outputs SHALL be assembled by holding-flow-specific internal logic

#### Scenario: S7 planning is isolated
- **WHEN** the adapter produces the `S7` output
- **THEN** the order planning glue SHALL be owned by a dedicated internal module

### Requirement: Adapter decomposition SHALL preserve the locked baseline
The backend SHALL preserve the locked baseline while decomposing the adapter.

#### Scenario: Locked baseline remains equivalent
- **WHEN** the backend reruns the locked baseline request after an adapter extraction step
- **THEN** `portfolio_daily.csv`, `portfolio_trades.csv`, `portfolio_candidates.csv`, `perf.json`, and `config_truth` SHALL remain `PASS`
- **AND** any allowed `WARN` SHALL remain limited to diagnostic drift already accepted by contract
