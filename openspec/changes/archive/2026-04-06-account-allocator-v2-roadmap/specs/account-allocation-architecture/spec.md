# account-allocation-architecture Specification

## Purpose

定义账户配置中枢 V2 的正式目标结构，使系统从“sleeve 驱动后拼装”演进到“账户层先定预算、sleeves 按职责执行”。

## Requirements

### Requirement: 系统必须定义账户层为顶层预算真相

系统 SHALL 将账户层视为 defense / core beta / alpha 预算的最终来源。

#### Scenario: 账户层输出预算建议
- **WHEN** runtime 进入账户级预算计算阶段
- **THEN** 系统输出 defense / core beta / alpha 预算建议
- **THEN** sleeves 只能消费账户层预算，而不是各自定义顶层预算真相

### Requirement: 系统必须按阶段迁移到账户配置中枢

系统 SHALL 通过 shadow mode、预算上收、状态边缘现金释放、ETF 预算拆分和最终 cutover 分阶段迁移。

#### Scenario: 按阶段推进迁移
- **WHEN** 团队推进 `Account Allocator V2`
- **THEN** 系统先完成 shadow mode
- **THEN** 再逐步上收预算权与现金释放，再进行最终 runtime cutover

### Requirement: 目标架构必须保留可解释的角色分层

系统 SHALL 明确区分防守层、核心 beta 层和 alpha 层的预算语义与解释语义。

#### Scenario: 弱势环境解释账户行为
- **WHEN** `effective_state_5` 进入 `TRANS_DOWN` 或 `RISK_OFF`
- **THEN** explain surface 能区分 defense、core beta 与 alpha 的预算变化
- **THEN** 系统不再把所有弱势行为混入单一 ETF 腿解释中
