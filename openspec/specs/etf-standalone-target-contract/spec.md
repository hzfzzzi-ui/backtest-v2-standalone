# etf-standalone-target-contract Specification

## Purpose

Define the target contract for ETF standalone inter-rebalance deployment so final target semantics and incremental deploy-gap semantics are not mixed.

## Requirements

### Requirement: ETF standalone deploy MUST expose both final and delta targets

The ETF standalone inter-rebalance deploy path SHALL preserve two explicit target semantics: `final_target_weight` for the final intended portfolio weight of a symbol, and `target_weight` for the incremental deploy gap to trade on the current day. The system SHALL NOT collapse both meanings into one field.

#### Scenario: existing holdings require only incremental top-up
- **WHEN** a selected ETF already has an existing holding
- **THEN** emitted BUY orders may have `target_weight` smaller than `final_target_weight`
- **THEN** both values remain available for audit and downstream reasoning

#### Scenario: new holdings may have equal final and delta targets
- **WHEN** a selected ETF has no existing holding
- **THEN** `target_weight` MAY equal `final_target_weight`
- **THEN** the two fields still preserve different semantics

### Requirement: partial fallback fill MUST preserve zero-original fallback semantics

When standalone deploy uses partial fallback fill and original target symbols still exist, fallback symbols with zero original target SHALL keep both `target_weight` and `final_target_weight` at `0.0`. The system SHALL NOT promote such fallback symbols into positive target weights through postprocess defaults or equalization logic.

#### Scenario: partial fallback does not create false positive targets
- **WHEN** original target symbols still exist in the selected set
- **THEN** fallback symbols with zero original target keep `target_weight = 0.0`
- **THEN** the same fallback symbols keep `final_target_weight = 0.0`

#### Scenario: full fallback replacement may still carry live target
- **WHEN** no original target symbols remain and the path becomes full fallback replacement
- **THEN** fallback symbols MAY carry live target semantics
- **THEN** those targets still follow the formal standalone target contract
