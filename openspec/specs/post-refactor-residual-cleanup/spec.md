# post-refactor-residual-cleanup Specification

## Purpose

This spec defines the steady-state cleanup rules for the front-end host chain and unified combo runtime path. The active implementation must stay limited to the formal owner modules and the single `execution_contract` runtime source.

## Requirements

### Requirement: cleanup MUST preserve the formal desktop shell owner map

The desktop front-end SHALL keep `desktop-shell/*` as the only active owner surface. Files outside the formal host chain SHALL NOT participate in bootstrap, shared helper ownership, or optional load-chain behavior for the same capability.

#### Scenario: non-mainline files stay out of the live path
- **WHEN** the formal desktop host chain is in place
- **THEN** only the formal owner modules participate in startup and shared behavior ownership
- **THEN** no second owner path is introduced for the same behavior

### Requirement: cleanup MUST preserve the validated replay anchor

`A_STOCK_ETF_V1` remains the reference anchor for the unified combo replay path.

#### Scenario: cleanup keeps the replay anchor stable
- **WHEN** cleanup changes are applied to the unified combo path
- **THEN** the validated `A_STOCK_ETF_V1` replay anchor stays available as the audit reference
- **THEN** the cleanup step SHALL NOT change the replay result contract

### Requirement: cleanup MUST distinguish source-wrapper passthrough from forbidden source pollution

Source-wrapper passthrough is allowed only when it preserves the existing wrapper shape and does not reintroduce non-contract runtime truth fields. Fields such as `mode`, `strategy_pack`, `signal_generation`, or `position_risk` SHALL NOT become the active runtime source once the contract-only path is established.

#### Scenario: wrapper passthrough stays thin
- **WHEN** an artifact still carries top-level wrapper fields such as `asset_context` or `unified_runtime`
- **THEN** those fields may pass through as wrapper context
- **THEN** they SHALL NOT become the active runtime source

### Requirement: cleanup MUST exclude obsolete source fields from the active path

The active unified combo path SHALL exclude obsolete source fields such as `unified_runtime.sleeves`, `combo_components`, and `component_source_mode`. The main spec set SHALL describe only the current single-`execution_contract` meaning.

#### Scenario: obsolete source fields no longer define the active path
- **WHEN** an active unified combo artifact is compiled or replayed
- **THEN** the active runtime source is resolved only through `execution_contract`
- **THEN** `component_source_contract` MAY remain as provenance metadata only
- **THEN** obsolete source fields SHALL NOT define the active path
