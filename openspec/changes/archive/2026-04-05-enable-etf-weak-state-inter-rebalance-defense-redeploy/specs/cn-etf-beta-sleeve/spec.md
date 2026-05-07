## ADDED Requirements

### Requirement: ETF beta sleeve 弱势状态必须允许非再平衡日防守补位
当 ETF beta sleeve 处于 `TRANS_DOWN` 或 `RISK_OFF`，且正式 weak-state defense policy 已激活时，如果当前 live seats 未满足正式 defense posture，系统 MUST 允许通过 inter-rebalance defense redeploy 进入防守部署。该路径 SHALL NOT 改变 `BULL / TRANS_UP` 的固定再平衡节奏。

#### Scenario: 弱势状态绕过固定 biweekly 等待进入防守部署
- **WHEN** ETF beta sleeve 运行于非再平衡日
- **AND** `effective_state_5` 属于 `TRANS_DOWN` 或 `RISK_OFF`
- **AND** 当前 live seats 未满足正式 defense posture
- **THEN** 系统 MUST 允许 inter-rebalance defense redeploy
- **THEN** 系统 SHALL NOT 仅因 `AWAIT_BIWEEKLY_REBALANCE` 而放弃该弱势防守部署

### Requirement: ETF beta sleeve 弱势 inter-rebalance 路径必须保持正式边界
ETF beta sleeve 的 weak-state inter-rebalance defense redeploy MUST 只使用正式弱势防守合同生成的目标集合。系统 SHALL NOT 在该路径中回退到普通进攻 ranking，也 SHALL NOT 借机修改 stock sleeve、regime 或 combo 主结构。

#### Scenario: 非再平衡日 weak-state redeploy 只使用 formal defense targets
- **WHEN** weak-state inter-rebalance defense redeploy 被激活
- **THEN** 选中结果 MUST 来自 formal weak-state defense targets
- **THEN** 运行 explain surface MUST 能区分该路径与常规再平衡路径
