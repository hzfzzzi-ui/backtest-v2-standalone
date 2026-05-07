# etf-defense-core-beta-budgets Specification

## Purpose

定义 ETF 预算层中的 `defense` 与 `core beta` 两类角色，使 ETF 不再作为单一“万能腿”承担全部弱势与核心暴露语义。

## Requirements

### Requirement: ETF 必须在预算层区分 defense 与 core beta

系统 SHALL 在预算层为 ETF 区分 defense budget 与 core beta budget。

#### Scenario: 生成 ETF 二级预算
- **WHEN** 账户层为 ETF 分配预算
- **THEN** 系统将 ETF 预算拆成 defense 与 core beta 两部分
- **THEN** 两者具有独立 explain 语义

### Requirement: defense 与 core beta 必须在 explain 和 audit 中可区分

系统 SHALL 在 explain 和 audit 产物中区分 ETF defense 与 core beta。

#### Scenario: 阅读弱势解释
- **WHEN** 用户查看 `TRANS_DOWN` 或 `RISK_OFF` 的 explain
- **THEN** 能分别看到 defense 与 core beta 的目标、实际和偏差

### Requirement: 本阶段不强制拆成两个独立运行引擎

系统 MAY 继续使用单一 ETF 运行引擎，但 SHALL 保证 budget 与 explain 语义已拆分。

#### Scenario: 单引擎承载双角色预算
- **WHEN** 当前实现仍使用单一 ETF engine
- **THEN** 系统仍能区分 defense 与 core beta 预算
- **THEN** 后续 runtime cutover 可在不改语义的前提下继续推进
