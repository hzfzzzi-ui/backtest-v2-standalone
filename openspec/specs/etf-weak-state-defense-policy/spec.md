# etf-weak-state-defense-policy Specification

## Purpose

定义 ETF 在 `TRANS_DOWN` 与 `RISK_OFF` 下的正式弱势承接合同，包括目标结构、允许资产边界、deployability 语义与 explain 要求。

## Requirements

### Requirement: ETF 弱势状态必须有正式防守承接合同

系统 SHALL 为 `TRANS_DOWN` 与 `RISK_OFF` 定义正式的 ETF 弱势承接合同。该合同 MUST 明确：

- 弱势状态目标结构
- 允许资产类别
- 资产优先级
- 暴露上限
- deployability 语义

系统 SHALL NOT 依赖隐式 layering 或 fallback 细节作为唯一真相。

#### Scenario: 弱势状态输出正式策略快照

- **WHEN** ETF sleeve 在 `TRANS_DOWN` 或 `RISK_OFF` 下运行
- **THEN** 系统依据正式弱势承接合同生成目标暴露与候选资产范围
- **THEN** 运行产物能够追溯到对应弱势策略层与原因码

### Requirement: 弱势承接必须优先使用债并允许少量核心宽基

在当前主线中：

- `RISK_OFF` MUST 采用债为主、少量核心宽基为辅的结构
- `TRANS_DOWN` MUST 采用债为主的过渡结构，并允许有限核心宽基

系统 SHALL NOT 将高 beta 风险资产作为默认弱势承接工具。

#### Scenario: `RISK_OFF` 采用债 + 核心宽基结构

- **WHEN** `effective_state_5 = RISK_OFF`
- **THEN** 正式目标结构以债为主
- **THEN** 允许少量核心宽基作为低风险累积

#### Scenario: `TRANS_DOWN` 采用债为主的过渡承接

- **WHEN** `effective_state_5 = TRANS_DOWN`
- **THEN** 系统仍以债为主
- **THEN** 允许有限核心宽基作为过渡仓位

### Requirement: 弱势部署在可承接时必须可执行

当弱势目标暴露大于零且正式弱势资产池中存在可交易标的时，系统 MUST 保留最小 deployable defense seat。系统 SHALL NOT 因通用 slot/cap 逻辑而静默压成零部署。

#### Scenario: 存在可交易弱势资产时形成最小承接

- **WHEN** `effective_state_5` 属于 `TRANS_DOWN` 或 `RISK_OFF`
- **AND** 正式弱势资产池存在可交易标的
- **AND** 目标暴露大于 `0.0`
- **THEN** 系统形成最小可执行承接结果

#### Scenario: 无可交易资产时显式给出原因

- **WHEN** `effective_state_5` 属于 `TRANS_DOWN` 或 `RISK_OFF`
- **AND** 正式弱势资产池不存在可交易标的
- **THEN** 系统 MAY 输出零部署
- **THEN** 运行产物 MUST 记录无可承接资产的原因码
