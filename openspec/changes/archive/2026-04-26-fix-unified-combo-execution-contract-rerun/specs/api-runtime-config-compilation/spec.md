## ADDED Requirements

### Requirement: ETF component compile MUST NOT unconditionally promote explicit R1 semantics to phase1
当 ETF component 的语义配置已显式声明 `source_entry_type = cn_etf_broad_based_standalone_mainline_entry` 或 `local_policy_mode = broad_based_rotation_mainline` 时，runtime compile SHALL 保留该 R1 standalone 研究口径，不得无条件改写为 `phase1_bucket_allocation`。

#### Scenario: compiling an explicit R1 ETF component
- **WHEN** unified combo compile 收到 ETF component 语义配置，且该配置声明 R1 standalone ETF source
- **THEN** 编译结果 MUST 保留原 ETF source entry
- **THEN** 编译结果 MUST 保留原 ETF universe symbols、price_adj、fallback 和防守资产规则
- **THEN** 编译器 SHALL NOT 调用 phase1 formal promotion 覆盖这些字段

### Requirement: ETF phase1 promotion MUST be conditional
ETF phase1 formal promotion SHALL 只在输入明确声明 phase1，或输入缺少明确 ETF source 且需要使用正式 phase1 默认 anchor 时执行。

#### Scenario: compiling a phase1 ETF component
- **WHEN** ETF component 输入声明 `source_entry_type = cn_etf_phase1_allocation_entry` 或 `local_policy_mode = phase1_bucket_allocation`
- **THEN** 编译器 MUST 应用 phase1 formal promotion
- **THEN** 编译结果 MUST 使用 phase1 formal pool、bucket allocation 和对应防守规则

#### Scenario: compiling an ETF component without explicit source
- **WHEN** ETF component 输入没有明确 ETF source entry 或 policy mode
- **THEN** 编译器 MAY 使用正式 phase1 默认 anchor
- **THEN** 编译结果 MUST 在产物中明确标记实际采用的 ETF source entry
