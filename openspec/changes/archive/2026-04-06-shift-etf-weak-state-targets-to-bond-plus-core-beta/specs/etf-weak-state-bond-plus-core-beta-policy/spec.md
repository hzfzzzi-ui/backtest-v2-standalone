## ADDED Requirements

### Requirement: ETF 弱势正式目标必须支持债加核心宽基累积结构
系统 MUST 为 ETF 弱势状态定义正式的“债加核心宽基”目标映射合同。在该合同下，`RISK_OFF` 与 `TRANS_DOWN` 的正式目标 SHALL 使用债为主、核心宽基为辅的结构，而不是退回纯空仓或继续依赖黄金作为本轮正式承接真相。

#### Scenario: `RISK_OFF` 使用债 70 / 核心宽基 30
- **WHEN** ETF sleeve 运行于 `RISK_OFF`
- **THEN** 正式目标映射 MUST 采用 `511010.SH 70% + 510300.SH 30%`
- **THEN** 该状态 SHALL NOT 将黄金作为本轮正式承接目标的一部分

#### Scenario: `TRANS_DOWN` 使用债 55 / 核心宽基 45
- **WHEN** ETF sleeve 运行于 `TRANS_DOWN`
- **THEN** 正式目标映射 MUST 采用 `511010.SH 55% + 510300.SH 45%`
- **THEN** 该状态 SHALL 保持债为主，而不是恢复高 beta 进攻结构

### Requirement: 弱势债加宽基合同不得改变总暴露语义
“债加核心宽基”合同 MUST 只改变弱势状态内部的目标构成，不得在本轮研究中修改 `RISK_OFF` 与 `TRANS_DOWN` 的总暴露定义。

#### Scenario: 仅替换弱势状态内部构成
- **WHEN** 系统启用 ETF 弱势债加核心宽基合同
- **THEN** `target_exposure_by_state_5` 的数值 SHALL 保持不变
- **THEN** 本轮变化 MUST 只体现在弱势状态内部资产目标映射上

### Requirement: 弱势债加宽基合同必须可审计地区分状态结构
系统 MUST 在运行产物中输出可审计的弱势目标结构，使研究者能够直接判断 `RISK_OFF` 与 `TRANS_DOWN` 的正式目标是否已切到债加核心宽基结构。

#### Scenario: 运行产物可读出弱势目标构成
- **WHEN** ETF sleeve 在 `RISK_OFF` 或 `TRANS_DOWN` 下运行
- **THEN** formal 或 research explain 中 MUST 能读出对应状态的正式目标映射
- **THEN** 研究者 MUST 能直接区分债券承接与核心宽基累积的目标比例
