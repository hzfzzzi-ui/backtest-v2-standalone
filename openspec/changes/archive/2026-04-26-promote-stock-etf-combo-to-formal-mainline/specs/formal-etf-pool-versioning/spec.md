## ADDED Requirements

### Requirement: formal ETF pool versions MUST define a single formal truth set
系统 MUST 为 ETF formal 主线维护显式的版本化资产池合同。每个版本 SHALL 明确 core beta in-scope、formal defense、excluded 与 research-only 资产范围。

#### Scenario: `formal_etf_pool_v1` is materialized
- **WHEN** 系统编译 formal ETF 主线合同
- **THEN** 系统 MUST 产生 `formal_etf_pool_v1`
- **THEN** 该版本 MUST 显式声明 core beta、formal defense、excluded 与 research-only 资产集合

### Requirement: expanding the formal ETF pool MUST create a new version
系统 SHALL NOT 静默修改已发布的 formal ETF pool 版本。新增正式标的或移除正式标的 MUST 通过新版本合同表达。

#### Scenario: a new ETF is proposed for formal scope
- **WHEN** 维护者希望将新的 ETF 纳入正式主线
- **THEN** 系统 MUST 通过新的 `formal_etf_pool_vN` 表达变更
- **THEN** 已存在的 formal pool 版本 SHALL 保持可复现
