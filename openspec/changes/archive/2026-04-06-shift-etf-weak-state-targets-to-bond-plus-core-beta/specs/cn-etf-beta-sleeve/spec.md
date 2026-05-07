## ADDED Requirements

### Requirement: ETF beta sleeve 弱势状态必须使用债加核心宽基正式目标
ETF beta sleeve 在 `RISK_OFF` 与 `TRANS_DOWN` 下 MUST 使用正式的“债加核心宽基”弱势目标映射。该映射 SHALL 只改变弱势状态内部目标结构，不得借机修改 `BULL / TRANS_UP` 的进攻逻辑，也不得影响 stock sleeve、regime 或 combo 主结构。

#### Scenario: ETF sleeve 弱势状态切到债加核心宽基目标
- **WHEN** ETF beta sleeve 运行于 `RISK_OFF` 或 `TRANS_DOWN`
- **THEN** 系统 MUST 使用正式的债加核心宽基目标映射
- **THEN** `BULL / TRANS_UP` 的核心逻辑 SHALL 保持不变

### Requirement: ETF beta sleeve 的弱势正式目标必须移除黄金本轮正式角色
在本轮研究中，ETF beta sleeve 的 `RISK_OFF` 与 `TRANS_DOWN` 正式目标 SHALL NOT 继续把黄金作为正式承接真相。黄金可以作为未来独立研究对象，但不得与本轮“债加核心宽基”单改动混在一起。

#### Scenario: 弱势正式目标不再包含黄金
- **WHEN** ETF beta sleeve 生成 `RISK_OFF` 或 `TRANS_DOWN` 的正式 targets
- **THEN** 正式 target map SHALL NOT 包含黄金 ETF
- **THEN** 弱势承接结构 MUST 收敛到债券与核心宽基
