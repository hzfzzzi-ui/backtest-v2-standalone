# state-edge-cash-release-contract Specification

## Purpose

定义账户层在状态切换边缘进行部分去风险与现金释放的正式合同，使弱势承接和累积具备明确现金来源。

## Requirements

### Requirement: 状态边缘必须可触发部分现金释放

系统 SHALL 在特定状态边缘上支持 bounded partial de-risking 和现金释放。

#### Scenario: 从进攻态切到弱势态
- **WHEN** 账户状态从 `BULL`、`LIGHT` 或 `TRANS_UP` 切入 `TRANS_DOWN` 或 `RISK_OFF`
- **THEN** 系统评估是否需要释放部分现金
- **THEN** 不默认执行全清仓

### Requirement: 现金释放必须有明确去向

系统 SHALL 明确释放现金的目标去向。

#### Scenario: 释放现金后给出用途
- **WHEN** 系统执行状态边缘现金释放
- **THEN** explain surface 记录释放金额和目标去向
- **THEN** 目标去向为 defense bucket、core beta accumulation bucket 或保持现金

### Requirement: 现金释放必须可审计

系统 SHALL 输出状态边缘释放的原因码与结果。

#### Scenario: 状态边缘未释放现金
- **WHEN** 进入弱势状态但未执行释放
- **THEN** 产物记录未释放原因
- **THEN** 能区分“无需释放”和“受约束未释放”
