## ADDED Requirements

### Requirement: Restore Candidate AB MUST preserve unified runtime NAV

The D6 restore candidate AB MUST run stock+ETF combo variants through the same
runtime NAV assembly used by the V3 combo template.

#### Scenario: No precomputed component shortcut is introduced

- **WHEN** the D6 AB study builds a request payload
- **THEN** `precomputed_component_results` MUST NOT be used
- **AND** the stock runtime config MUST be patched only through declared
  strategy params
- **AND** the ETF runtime config, combo allocator, and NAV assembly contract MUST
  remain unchanged.

### Requirement: Restore Candidate MUST be armed only by filled partial D5 confirmation exits

The runtime MUST arm restore state only after a D5 MFE/MAE confirmation action
creates a partial exit from an existing stock position and that partial sell is
filled.

#### Scenario: Filled half exit arms restore state

- **GIVEN** a held stock position triggers a D5 MFE/MAE confirmation exit
- **AND** the configured exit percentage sells only part of the position
- **AND** `enable_mfe_mae_restore_candidate` is true
- **WHEN** the partial sell order is filled
- **THEN** symbol-scoped restore state MUST be recorded with the arm date and
  source reason.

#### Scenario: Unfilled or non-partial exits do not arm restore state

- **GIVEN** a D5 MFE/MAE confirmation action fully exits a position
- **OR** a partial sell order is not filled
- **WHEN** runtime accounting processes fills
- **THEN** no restore state MUST be recorded for that symbol.

### Requirement: Restore Candidate MUST require normal raw candidate re-entry

The runtime MUST emit a restore buy candidate only when the same symbol re-enters
the normal raw buy candidate list within the configured restore window.

#### Scenario: Already held symbol can pass the provider filter only as restore

- **GIVEN** a symbol is still held after a D5 half exit
- **AND** restore state for that symbol is active
- **WHEN** the symbol appears in the normal raw buy candidates again
- **THEN** the provider MAY emit a buy signal with
  `restore_candidate=true`
- **AND** the signal MUST include `target_weight_basis=delta_restore_gap`
- **AND** the signal MUST include `reason_code=MFE_MAE_RESTORE_CANDIDATE`.

#### Scenario: Held symbols without restore state are still filtered

- **GIVEN** a symbol is already held
- **AND** there is no active restore state for that symbol
- **WHEN** it appears in the normal raw buy candidates
- **THEN** the provider MUST keep filtering it as an existing holding.

### Requirement: Restore Candidate buy quantity MUST be a delta top-up

Candidate and execution planning MUST cap restore buys to the normal target
quantity minus current held quantity.

#### Scenario: Restore buy tops up without overbuying

- **GIVEN** a restore signal has a normal target quantity of 500 shares
- **AND** the account already holds 300 shares
- **WHEN** the execution order is planned
- **THEN** the buy quantity MUST be at most 200 shares after lot rounding
- **AND** the order MUST NOT consume an additional new-position slot.

#### Scenario: Restore buy with non-positive delta is rejected

- **GIVEN** a restore signal has a normal target quantity less than or equal to
  the current held quantity
- **WHEN** the candidate or execution layer evaluates the signal
- **THEN** no buy order MUST be created
- **AND** the rejection reason MUST make the zero restore delta auditable.

### Requirement: Restore Candidate AB MUST report same-window evidence

The D6 restore candidate study MUST compare B0, D5 immediate, and D5 immediate
plus restore variants on the same configured windows.

#### Scenario: Study outputs are interpretable

- **WHEN** the D6 restore candidate study completes a window
- **THEN** the matrix MUST include performance metrics, experiment ids, effective
  execution start dates, and reason-code counts
- **AND** the final conclusion MUST state whether restore behavior should
  continue, be rejected, or remain a small-sample diagnostic.
