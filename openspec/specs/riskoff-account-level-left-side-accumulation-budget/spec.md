# riskoff-account-level-left-side-accumulation-budget Specification

## Purpose

定义 `RISK_OFF` 下账户层左侧累积预算的正式语义边界。

## Requirements

### Requirement: RISK_OFF 必须支持账户层左侧累积预算

系统 SHALL 在 `RISK_OFF` 下提供账户层左侧累积预算，使 runtime 主真相能表达“防守优先、少量核心宽基累积”。

#### Scenario: RISK_OFF 进入账户层左侧累积模式
- **WHEN** `account_allocator_runtime.effective_state_5` 为 `RISK_OFF`
- **THEN** 系统输出正式的 `defense` 与 `core_beta` 目标预算
- **THEN** `defense` SHALL 为主预算
- **THEN** `core_beta` SHALL 表达为少量核心宽基累积预算

### Requirement: RISK_OFF 左侧累积必须限定在债与单一核心宽基

系统 SHALL 将本轮 `RISK_OFF` 左侧累积限定为债资产与单一核心宽基，不得扩展为多资产或高 beta 抄底。

#### Scenario: 构建 RISK_OFF 左侧累积目标
- **WHEN** 系统生成 `RISK_OFF` 目标预算
- **THEN** `defense` 目标 SHALL 绑定债类承接资产
- **THEN** `core_beta` 目标 SHALL 绑定 `510300.SH`
- **THEN** 系统 MUST NOT 在本轮把黄金、第二核心宽基或个股 alpha 纳入同一左侧累积合同

### Requirement: explain 与 audit 必须标记账户层左侧累积语义

系统 SHALL 在 explain 与 audit 中明确这是一条账户层左侧累积预算，而不是 ETF 局部执行补丁。

#### Scenario: 查看 RISK_OFF 结果解释
- **WHEN** 用户查看 `run_meta`、`audit` 或前端 governor/account allocator 面板
- **THEN** 系统 SHALL 展示账户层左侧累积预算的目标、实际和偏差
- **THEN** 系统 SHALL 标记该语义只针对 `RISK_OFF`
- **THEN** 系统 MUST NOT 将其解释为 execution constraint 已解决
