# etf-weak-state-inter-rebalance-defense-redeploy Specification

## Purpose

定义 ETF 在弱势状态下的非再平衡日防守 redeploy 合同，以及 `RISK_OFF` 下的 `cash-drip top-up` 执行分支。

## Requirements

### Requirement: 弱势防守合同必须支持非再平衡日 redeploy

当 `effective_state_5` 处于 `TRANS_DOWN` 或 `RISK_OFF`，且正式 weak-state defense policy 已激活时，系统 MUST 支持 ETF sleeve 在非再平衡日执行防守 redeploy。该 redeploy 只用于让正式弱势防守合同落地，不替代常规进攻段再平衡。

#### Scenario: 非再平衡日触发防守 redeploy

- **WHEN** ETF sleeve 运行于非再平衡日
- **AND** `effective_state_5` 属于 `TRANS_DOWN` 或 `RISK_OFF`
- **AND** `weak_state_defense_policy_active = true`
- **AND** 当前持仓未满足正式 defense posture
- **THEN** 系统 MUST 允许一次 inter-rebalance defense redeploy
- **THEN** redeploy 目标来自正式 weak-state defense targets

### Requirement: 已满足防守姿态时不得重复触发 redeploy

如果当前 live seats 已满足正式弱势防守姿态，系统 SHALL NOT 因弱势状态持续存在而重复触发 inter-rebalance defense redeploy。

#### Scenario: 已满足 posture 时拒绝额外 redeploy

- **WHEN** ETF sleeve 运行于非再平衡日
- **AND** 当前持仓已满足正式 defense posture
- **THEN** 系统 SHALL NOT 生成额外 defense redeploy 订单
- **THEN** explain surface 给出“已满足防守姿态”的拒绝原因

### Requirement: `RISK_OFF` 必须支持 cash-drip top-up 分支

在 `RISK_OFF` 下，系统 MUST 支持基于最小可执行单位和可用现金的小额 `cash-drip top-up` 分支。该分支优先补债，其次才补核心宽基。

#### Scenario: 进入 `RISK_OFF cash-drip`

- **WHEN** `effective_state_5 = RISK_OFF`
- **AND** 当前存在目标缺口
- **AND** 不需要等待固定再平衡日
- **THEN** 系统进入 `cash-drip top-up` 评估

#### Scenario: 现金不足最小单位时拒绝

- **WHEN** `effective_state_5 = RISK_OFF`
- **AND** 当前存在目标缺口
- **AND** 可用现金不足最小可执行单位
- **THEN** 系统保留 `cash too small` 类拒绝原因

### Requirement: 弱势 inter-rebalance redeploy 必须可审计

系统 MUST 为弱势 inter-rebalance defense redeploy 输出专门的 activation 与 reject explain 字段，至少区分：

- 已激活并执行
- 已满足防守姿态
- 无 defense 候选
- 现金不足最小单位
- 被执行约束拒绝

#### Scenario: 保留弱势 redeploy 原因码

- **WHEN** ETF sleeve 在弱势状态下进入 inter-rebalance redeploy 判定
- **THEN** 运行产物 MUST 记录该路径是否激活
- **THEN** 运行产物 MUST 记录对应 activation 或 reject 原因码
