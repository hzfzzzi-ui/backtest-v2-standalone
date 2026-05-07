## ADDED Requirements

### Requirement: 平台必须原生支持单因子研究

系统 MUST 支持在不运行完整策略回放的前提下，对单个个股 alpha 因子执行正式研究，并输出覆盖率、分层收益、稳定性等标准研究结果。

#### Scenario: 运行单因子研究

- **WHEN** 用户选择某个正式 catalog 因子并指定研究窗口
- **THEN** 系统 MUST 基于 `factor_snapshot` 运行单因子研究
- **THEN** 系统 MUST 输出标准研究结果而不是要求先跑完整策略回放

### Requirement: 平台必须原生支持因子组合研究

系统 MUST 支持对多个正式 catalog 因子做组合研究，并输出组合分数及其标准研究结果。

#### Scenario: 运行因子组合研究

- **WHEN** 用户选择多个正式 catalog 因子并给出组合方式
- **THEN** 系统 MUST 生成正式 `factor_score`
- **THEN** 系统 MUST 输出该组合分数对应的标准研究结果

### Requirement: 因子研究入口必须与完整回放入口分层

第一条 change 中的因子研究入口 MUST 作为研究入口存在，不得要求默认接入完整主策略 runtime 才能使用。

#### Scenario: 研究入口与回放入口并存

- **WHEN** 用户仅做单因子或因子组合研究
- **THEN** 系统 MUST 允许其直接消费 `factor_snapshot`
- **THEN** 系统 SHALL NOT 强制其触发完整组合回放
