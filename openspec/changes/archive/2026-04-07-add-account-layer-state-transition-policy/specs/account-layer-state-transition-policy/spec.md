## ADDED Requirements

### Requirement: 账户层必须定义统一状态切换合同
系统 SHALL 在账户层定义统一的状态切换合同，覆盖 `risk_on -> risk_on`、`risk_on -> defensive`、`defensive -> defensive`、`defensive -> recovery` 四类切换，而不是只对单一状态补丁式定义新语义。

#### Scenario: 读取状态切换合同
- **WHEN** runtime 进入账户层状态切换评估阶段
- **THEN** 系统能识别当前切换所属的状态切换类别
- **THEN** 系统引用账户层统一状态切换合同，而不是直接落回 ETF 局部执行语义

### Requirement: 状态切换合同必须显式输出库存重构语义
系统 SHALL 让每类状态切换显式输出 carry rules、de-risk rules、cash release rules 和 budget handoff rules。

#### Scenario: 从风险承担状态切入防守状态
- **WHEN** 账户层从 `BULL`、`LIGHT` 或 `TRANS_UP` 切入 `TRANS_DOWN` 或 `RISK_OFF`
- **THEN** 系统输出允许保留的仓位规则
- **THEN** 系统输出需要降风险的仓位规则、释放现金规则和预算移交规则

### Requirement: 账户层状态机必须是上游真相
系统 SHALL 将账户层状态机视为上游真相，组件状态只能作为输入证据，不得再由组件状态简单聚合反推账户状态。

#### Scenario: 计算账户层有效状态
- **WHEN** 系统评估账户层有效状态
- **THEN** 系统以账户层状态机为唯一决策入口
- **THEN** stock/ETF sleeve 状态只作为输入证据参与，不再直接决定账户层状态
