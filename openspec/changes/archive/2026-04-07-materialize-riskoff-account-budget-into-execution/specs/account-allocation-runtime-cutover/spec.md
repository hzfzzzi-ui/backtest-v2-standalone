## MODIFIED Requirements

### Requirement: 账户层必须成为 runtime 唯一真相

系统 SHALL 将账户层预算输出视为 runtime 顶层真相；在 `RISK_OFF` 下，账户层预算不仅负责解释，还必须能够驱动真实执行 materialization。

#### Scenario: runtime 进入预算驱动模式
- **WHEN** runtime 编译正式运行输入
- **THEN** 顶层真相来自账户层 budgets 和约束
- **THEN** sleeves 只消费账户层输出

#### Scenario: RISK_OFF 驱动真实执行
- **WHEN** `account_allocator_runtime.effective_state_5` 为 `RISK_OFF`
- **THEN** 账户层预算 SHALL 进入正式执行链
- **THEN** defense / core beta 预算缺口 SHALL 能触发 execution materialization
- **THEN** 系统 MUST NOT 将 `RISK_OFF` 预算降级为仅 explain 语义
