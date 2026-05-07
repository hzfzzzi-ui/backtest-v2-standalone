## MODIFIED Requirements

### Requirement: the ETF beta sleeve MUST remain a governed standalone sleeve
The system SHALL expose `cn-etf-beta-sleeve` as the formal ETF stabilizer sleeve under the A-share combo mainline. It is a low-frequency, explainable budget-bearing stabilizer rather than a second stock-style alpha engine or a research-only broad-based branch.

#### Scenario: ETF sleeve runs as formal stabilizer under combo governor budget
- **WHEN** the ETF beta sleeve is enabled under the formal combo mainline
- **THEN** it is treated as a sleeve independent from stock alpha logic
- **THEN** it runs within governor-issued budget and execution constraints
- **THEN** its formal identity is `formal ETF stabilizer`

### Requirement: Phase 1 ETF scope MUST stay bounded
Phase 1 SHALL treat only the symbols declared by `formal_etf_pool_v1` as formal in-scope truth, with formal defense candidates explicitly bounded by contract.

#### Scenario: only `formal_etf_pool_v1` symbols are treated as formal ETF truth
- **WHEN** the system builds the formal Phase 1 ETF candidate set
- **THEN** only the symbols declared by `formal_etf_pool_v1` are treated as formal core beta or formal defense truth
- **THEN** out-of-scope or research-only ETF symbols are not silently upgraded into the formal sleeve

## REMOVED Requirements

### Requirement: ETF beta sleeve 在账户层主真相下只能作为 transition execution adapter
**Reason**: 主线 promotion 后，ETF sleeve 不再只是账户层共享执行的 diagnostics/reference adapter，而是正式 budget-bearing stabilizer sleeve。
**Migration**: ETF sleeve 仍需保留 transition execution diagnostics，但 formal output contract 需要将其提升为正式主线组件，而不是仅作为 adapter 描述。

## ADDED Requirements

### Requirement: ETF beta sleeve MUST use the formal Phase 1 allocation entry type when promoted
当 ETF beta sleeve 作为 formal mainline 组件运行时，系统 MUST 使用 `cn_etf_phase1_allocation_entry` 作为正式入口类型。

#### Scenario: promoted ETF sleeve compiles source entry type
- **WHEN** ETF sleeve 进入 formal mainline compile path
- **THEN** `source_entry_type` MUST be `cn_etf_phase1_allocation_entry`
- **THEN** 系统 SHALL NOT 继续沿用 `cn_etf_research_entry` 作为 formal source truth

### Requirement: ETF beta sleeve MUST pass formal alignment before combo promotion
ETF beta sleeve 在被组合主线消费前 MUST 通过 formal alignment，且 `formal_alignment_status` MUST equal `formal_mainline`。

#### Scenario: combo promotion validates ETF sleeve
- **WHEN** 系统尝试将 ETF sleeve 作为正式组合组件挂回 unified combo
- **THEN** `etf_beta_sleeve` 审计 gate MUST be `PASS`
- **THEN** `formal_alignment_status` MUST be `formal_mainline`

### Requirement: ETF beta sleeve formal outputs MUST exclude research-only semantics
ETF beta sleeve 的 formal output contract MUST 剥离 research-only 字段、reason family 与 explain 语义。

#### Scenario: formal ETF sleeve writes outputs
- **WHEN** ETF sleeve 作为 formal mainline 组件写出 `run_meta.json`、`audit.json` 与 explain 产物
- **THEN** formal outputs MUST exclude research-only semantics
- **THEN** research diagnostics MAY remain available in internal audit surfaces only
