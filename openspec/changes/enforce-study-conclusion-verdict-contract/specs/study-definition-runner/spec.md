## ADDED Requirements

### Requirement: study runner MUST map hard gate results to formal study verdicts

When `study_run` completes a window/variant, the study runner MUST map execution hard-gate output into a formal study verdict before appending a conclusion record. The mapping MUST NOT directly copy `PASS` or `FAIL` into conclusion `verdict`.

#### Scenario: weak hard gate pass with negative baseline compare
- **WHEN** a study variant has `gate_status = "PASS"` because it satisfies a weak execution gate such as `min_trades`
- **WHEN** the same-window compare shows materially worse return, Sharpe, or drawdown versus the compared baseline
- **THEN** the study runner MUST append a conclusion with `verdict = "falsified"` or `verdict = "inconclusive"`
- **THEN** the study runner MUST preserve `gate_status = "PASS"` separately

#### Scenario: hard gate failure
- **WHEN** a study variant fails execution hard gates
- **THEN** the study runner MUST append a conclusion with `verdict = "inconclusive"` unless an explicit research verdict override is provided by a governed study surface
- **THEN** the study runner MUST preserve the failing gate status and reason separately

### Requirement: study journal MUST summarize formal verdicts without treating gate status as acceptance

The research study journal MUST use formal conclusion `verdict` values for conclusion summary and MUST NOT treat hard-gate `PASS` as an accepted study direction.

#### Scenario: journal summarizes mixed records
- **WHEN** the journal links experiment evidence that has conclusion records with both `verdict` and `gate_status`
- **THEN** auto summary MUST count `confirmed`, `falsified`, and `inconclusive` as research verdicts
- **THEN** auto summary MAY expose `gate_status` counts separately
