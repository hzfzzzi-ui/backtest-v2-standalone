## ADDED Requirements

### Requirement: RISK_OFF 账户层预算必须能够 materialize 为真实执行意图
系统 SHALL 在 `RISK_OFF` 下将账户层 defense / core beta 预算缺口转成正式执行意图，而不是只停留在 explain 层。

#### Scenario: RISK_OFF 预算进入执行链
- **WHEN** `account_allocator_runtime.effective_state_5` 为 `RISK_OFF`
- **THEN** 系统 SHALL 生成账户层 budget materialization contract
- **THEN** 该 contract SHALL 能表达 defense 优先、core beta 次之的执行顺序
- **THEN** 系统 MUST NOT 把该行为降级为仅 explain 字段

### Requirement: RISK_OFF materialization 必须允许 bounded partial de-risk 释放现金
系统 SHALL 在 `RISK_OFF` 下允许对既有风险仓位做有界的部分去风险，以释放现金给 defense / core beta 预算落地。

#### Scenario: 旧仓占满现金导致预算无法落地
- **WHEN** 当前持仓结构阻塞 `RISK_OFF` 预算落地
- **THEN** 系统 SHALL 允许 bounded partial de-risk release
- **THEN** release SHALL 先服务于 defense 预算，再服务于 core beta 预算
- **THEN** 系统 MUST NOT 自动上调总暴露

### Requirement: materialization 拒绝必须可审计
系统 SHALL 在 `RISK_OFF` 下把 budget materialization 的激活、执行和拒绝原因写入 runtime explain 与 audit。

#### Scenario: RISK_OFF 预算未完全落地
- **WHEN** 系统未能把账户层预算完整 materialize 为真实执行
- **THEN** audit 与 explain SHALL 区分预算成立、执行激活、执行拒绝三种状态
- **THEN** 系统 SHALL 记录 reject 原因而不是回退为模糊的 ETF 局部补丁解释
