## ADDED Requirements

### Requirement: Wide PIT Runtime Optimization

The system SHALL provide research-controlled runtime optimizations for wide PIT stock universes without changing stock pool, signal, ranking, execution, exit, or portfolio semantics.

#### Scenario: PIT interval pushdown keeps auditability

- **WHEN** a `PIT_DYNAMIC` universe has membership intervals
- **THEN** runtime MAY prune OHLCV rows outside membership intervals plus configured warmup
- **AND** it MUST expose before/after row counts, warmup days, and dropped rows in audit metadata
- **AND** it MUST NOT replace PIT membership with static current constituents.

#### Scenario: partial top-k preserves ordering semantics

- **WHEN** a runtime path selects top-k candidates from a larger ordered population
- **THEN** it MAY use partial selection
- **AND** the final top-k order MUST match the stable full-sort order for equal inputs.

#### Scenario: candidate-first scoring preserves rank population

- **WHEN** expensive scoring is moved after cheap gates
- **THEN** the optimization MUST preserve the original rank population for any factor whose definition requires full active-universe ranking
- **AND** any score that cannot be safely moved MUST remain on the original path.

#### Scenario: streaming rolling state is parity gated

- **WHEN** rolling features are implemented through streaming state
- **THEN** the path MUST be guarded by tests that compare against the existing pandas/matrix calculation
- **AND** it MUST NOT become the default formal runtime path until B0 parity is accepted.

#### Scenario: active-set sparse scoring preserves full-rank population

- **WHEN** residual-only sparse scoring is enabled for a research run
- **THEN** the system MUST preserve the original full active-universe rank population for residual score calculation
- **AND** it MAY defer full `residual_strength_score` and `final_score` matrix materialization
- **AND** day-signal generation MUST compute candidate and held-symbol scores from the same-day full-rank row
- **AND** the path MUST remain disabled unless its safety preconditions are met.

#### Scenario: runtime profile survives precompute failure

- **WHEN** a wide PIT run is killed during provider precompute or simulation
- **THEN** the experiment directory SHOULD contain a checkpoint profile with at least the last phase, symbol count, trading-day count, row counts, matrix-cell estimate, and enabled runtime optimization flags
- **AND** successful runs SHOULD still emit the normal `run_profile.json`.
