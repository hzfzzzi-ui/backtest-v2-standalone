## MODIFIED Requirements

### Requirement: 固定组合形态必须降级为 reference
系统 SHALL 将旧的固定 `50/50` 组合作为 baseline、benchmark 或 fallback reference，而不是主 runtime 合同；在 `RISK_OFF` 下，账户层 runtime 解释 SHALL 允许 defense 主导且 core beta 仅作为少量左侧累积预算。

#### Scenario: 读取旧基线
- **WHEN** 系统加载历史固定组合基线
- **THEN** MAY 将其作为 reference 或 compatibility input
- **THEN** 当前 runtime 仍以账户层预算为唯一主真相

#### Scenario: RISK_OFF 解释账户层预算
- **WHEN** `account_allocator_runtime.effective_state_5` 为 `RISK_OFF`
- **THEN** explain、audit 和 frontend 结果展示 SHALL 优先解释 `defense` 与 `core_beta` 的账户层预算
- **THEN** 旧 `50/50` 结构 SHALL 只作为 reference 展示，不得覆盖账户层左侧累积预算语义
