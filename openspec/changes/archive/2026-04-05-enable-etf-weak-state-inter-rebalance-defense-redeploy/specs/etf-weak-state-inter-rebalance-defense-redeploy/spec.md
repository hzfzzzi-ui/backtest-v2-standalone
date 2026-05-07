## ADDED Requirements

### Requirement: ETF 弱势防守合同必须支持非再平衡日 redeploy
当 `effective_state_5` 处于 `TRANS_DOWN` 或 `RISK_OFF`，且正式弱势防守合同已激活时，系统 MUST 支持 ETF sleeve 在非再平衡日执行防守型 redeploy。该 redeploy MUST 只用于让正式弱势防守合同落地，而不是替代常规进攻段再平衡。

#### Scenario: 弱势合同在非再平衡日触发防守 redeploy
- **WHEN** ETF sleeve 运行于非再平衡日
- **AND** `effective_state_5` 属于 `TRANS_DOWN` 或 `RISK_OFF`
- **AND** `weak_state_defense_policy_active = true`
- **AND** 当前持仓未满足正式 defense posture
- **THEN** 系统 MUST 允许一次 inter-rebalance defense redeploy
- **THEN** redeploy 目标 MUST 来自正式 weak-state defense targets

### Requirement: 已满足防守姿态时不得重复触发 redeploy
如果当前 live seats 已经满足正式弱势防守姿态，系统 SHALL NOT 因为弱势状态持续存在而重复触发 inter-rebalance defense redeploy。

#### Scenario: 已满足防守姿态时拒绝额外 redeploy
- **WHEN** ETF sleeve 运行于非再平衡日
- **AND** 弱势防守合同已激活
- **AND** 当前持仓已经满足 formal defense posture
- **THEN** 系统 SHALL NOT 生成额外的 defense redeploy 订单
- **THEN** explain surface MUST 给出“已满足防守姿态”的拒绝原因码

### Requirement: 弱势 inter-rebalance redeploy 必须可审计
系统 MUST 为 weak-state inter-rebalance defense redeploy 输出专门的 activation 与 reject explain 字段，至少区分“已激活并执行”“已满足防守姿态”“无 defense 候选”“被执行约束拒绝”。

#### Scenario: 非再平衡日保留弱势 redeploy 原因码
- **WHEN** ETF sleeve 在弱势状态下进入 inter-rebalance defense redeploy 判定
- **THEN** 运行产物 MUST 记录该路径是否激活
- **THEN** 运行产物 MUST 记录对应 activation 或 reject 原因码
