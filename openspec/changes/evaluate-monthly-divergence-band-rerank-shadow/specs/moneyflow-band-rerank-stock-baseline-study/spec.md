## ADDED Requirements

### Requirement: `band_rerank` MUST be a valid moneyflow overlay rank action

The system MUST accept `asset_context.moneyflow_overlay.mode = band_rerank` only when the overlay contract declares a valid bounded rank insertion.

#### Scenario: validate the contract

- **WHEN** a runtime config enables `moneyflow_overlay.mode = band_rerank`
- **THEN** `factor_role` MUST resolve to `rank`
- **THEN** `band_limit` MUST be present and MUST be an integer >= 2
- **THEN** invalid configs MUST be rejected at runtime-config validation time

### Requirement: band rerank MUST preserve the baseline order outside the candidate band

The system MUST only rerank the bounded candidate band and MUST leave the suffix outside the band untouched.

#### Scenario: rerank a top-3 band

- **WHEN** baseline ranking produces candidates `A, B, C, D`
- **AND** `band_limit = 3`
- **AND** overlay scores reorder the band to `C, B, A`
- **THEN** the final candidate order MUST be `C, B, A, D`
- **AND** `D` MUST remain outside the reranked band even if it has a higher overlay score

### Requirement: `v10/moneyflow_monthly_band_rerank_s1` MUST define the minimal band-rerank study

The system MUST provide a formal study that evaluates moneyflow monthly band rerank on the official `baseline_V10_1` shell.

#### Scenario: load the study definition

- **WHEN** the system loads `v10/moneyflow_monthly_band_rerank_s1`
- **THEN** the study MUST declare `study_id`, `baseline_id`, `asset_scope`, `hypothesis`, `variants`, `windows`, and `required_outputs`
- **THEN** `baseline_id` MUST equal `baseline_V10_1`
- **THEN** the variants MUST include `B0` and `MF_BAND20`

### Requirement: the study MUST remain runtime-config-backed

The study MUST continue to use `runtime_config_path + runtime_config_json` as the single execution surface.

#### Scenario: build the 1226 overlay payload

- **WHEN** the system builds the `1226 / MF_BAND20` study payload
- **THEN** the payload MUST include `runtime_config_path`
- **THEN** the payload MUST include `runtime_config_json.asset_context.moneyflow_overlay.mode = band_rerank`
- **THEN** the payload MUST include `runtime_config_json.asset_context.moneyflow_overlay.band_limit = 20`
- **THEN** the payload SHALL NOT fall back to `workbench_config_path`
