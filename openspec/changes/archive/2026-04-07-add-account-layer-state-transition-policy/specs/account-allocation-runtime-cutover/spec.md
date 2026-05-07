## MODIFIED Requirements

### Requirement: 账户层必须成为 runtime 唯一真相

系统 SHALL 将账户层预算输出与状态切换输出视为 runtime 顶层真相。

#### Scenario: runtime 进入账户预算驱动模式
- **WHEN** runtime 编译正式运行输入
- **THEN** 顶层真相来自账户层 budgets、状态切换合同和约束
- **THEN** sleeves 只消费账户层输出

### Requirement: explain 与 audit 必须统一到账户叙事

系统 SHALL 让 explain、audit 和 frontend 结果展示优先解释账户预算层与账户状态切换层。

#### Scenario: 查看组合结果
- **WHEN** 用户查看 runtime explain、审计或前端结果
- **THEN** 系统优先展示 defense / core beta / alpha budgets
- **THEN** 系统优先展示账户层状态切换输出
- **THEN** 旧 combo 叙事只作为历史参考或 fallback

### Requirement: 固定组合形态必须降级为 reference

系统 SHALL 将旧的固定 `50/50` 组合作为 baseline、benchmark 或 fallback reference，而不是主 runtime 合同；当 `runtime_truth_source = account_allocator` 时，旧 combo/reference 不得与账户层主叙事并列承担解释权。

#### Scenario: 读取旧基线
- **WHEN** 系统加载历史固定组合基线
- **THEN** MAY 将其作为 reference 或 compatibility input
- **THEN** 当前 runtime 仍以账户层预算和状态切换为唯一主真相
- **THEN** query 与 frontend 只能把旧 combo 展示为 reference 区
