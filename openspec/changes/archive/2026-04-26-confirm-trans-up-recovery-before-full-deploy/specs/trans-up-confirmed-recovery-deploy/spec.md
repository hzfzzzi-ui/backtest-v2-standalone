## ADDED Requirements

### Requirement: Staged recovery entry in TRANS_UP

When stock alpha is in `TRANS_UP` with `TREND_LIGHT` and benchmark regime is off, the runtime MUST support staged recovery entry scaling instead of forcing immediate full-size deployment.

#### Scenario: staged recovery deploy

- **GIVEN** `allow_trans_up_recovery_entries_when_benchmark_off = true`
- **AND** `trans_up_recovery_entry_scale_when_benchmark_off < 1.0`
- **WHEN** a stock buy signal is preserved in `TRANS_UP` while `benchmark_regime_on = false`
- **THEN** the signal MUST carry scaled deploy metadata
- **AND** the entry reason MUST identify the holding as a staged recovery entry

### Requirement: Confirmed top-up for staged recovery holdings

When a staged recovery holding later sees benchmark regime confirmation while still in `TRANS_UP`, the runtime MUST support a one-time confirmed top-up for that existing holding.

#### Scenario: one-time confirmed top-up

- **GIVEN** a holding was opened as `TRANS_UP_RECOVERY_STAGED_ENTRY`
- **AND** the runtime remains in `TRANS_UP`
- **AND** `benchmark_regime_on = true`
- **AND** `trans_up_recovery_confirmed_top_up_scale_when_benchmark_on > 0`
- **WHEN** the signal pipeline prepares stock alpha buys
- **THEN** the existing holding MUST be eligible for a single confirmed top-up
- **AND** after the top-up fill, the holding source reason MUST update so the same holding is not topped up repeatedly
