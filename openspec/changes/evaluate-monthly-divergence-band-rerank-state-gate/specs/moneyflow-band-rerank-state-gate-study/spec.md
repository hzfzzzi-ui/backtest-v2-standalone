## ADDED Requirements

### Requirement: state-gated band rerank MUST be a valid moneyflow rank action

The system MUST accept explicit state-gated band-rerank modes for moneyflow overlay rank insertion.

#### Scenario: validate `bull_only_band_rerank`

- **WHEN** a runtime config enables `moneyflow_overlay.mode = bull_only_band_rerank`
- **THEN** the contract MUST resolve to a valid rank action
- **THEN** `band_limit` MUST still be required

#### Scenario: validate `bull_trans_up_band_rerank`

- **WHEN** a runtime config enables `moneyflow_overlay.mode = bull_trans_up_band_rerank`
- **THEN** the contract MUST resolve to a valid rank action
- **THEN** `band_limit` MUST still be required

### Requirement: state-gated rerank MUST activate only inside the declared states

The system MUST suppress rerank behavior outside the declared state gate.

#### Scenario: `bull_only_band_rerank` outside bull

- **WHEN** `moneyflow_overlay.mode = bull_only_band_rerank`
- **AND** `market_state_today = TRANS_UP`
- **THEN** overlay rerank MUST be suppressed

#### Scenario: `bull_trans_up_band_rerank` inside trans-up

- **WHEN** `moneyflow_overlay.mode = bull_trans_up_band_rerank`
- **AND** `market_state_today = TRANS_UP`
- **THEN** overlay rerank MUST be active

### Requirement: `v10/moneyflow_monthly_band_rerank_state_gate_s1` MUST define the minimal state-gated rerank study

The system MUST provide a formal study that compares baseline control with state-gated band-rerank variants.

#### Scenario: load the study definition

- **WHEN** the system loads `v10/moneyflow_monthly_band_rerank_state_gate_s1`
- **THEN** the variants MUST include `B0`, `MF_BAND20_BULL`, and `MF_BAND20_BULL_TRANSUP`
- **THEN** the study MUST remain runtime-config-backed
