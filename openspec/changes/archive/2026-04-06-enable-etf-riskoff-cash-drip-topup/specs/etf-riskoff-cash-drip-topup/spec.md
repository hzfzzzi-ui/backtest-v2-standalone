## ADDED Requirements

### Requirement: ETF `RISK_OFF` 必须支持 cash-drip top-up
当 ETF sleeve 运行于 `RISK_OFF`，且正式弱势目标已存在未完成缺口时，系统 MUST 允许基于可用现金执行小额、频繁的 drip top-up。该路径 SHALL NOT 再要求先满足较大的完整 deploy gap 才允许下单。

#### Scenario: 有可用现金时允许最小单位补仓
- **WHEN** `effective_state_5 = RISK_OFF`
- **AND** 当前 ETF 实际暴露低于正式弱势目标暴露
- **AND** 存在可用现金且满足最小可执行单位
- **THEN** 系统 MUST 允许发出一次小额 drip top-up
- **THEN** 系统 SHALL NOT 仅因 deploy gap 未达到旧门槛而拒绝下单

### Requirement: ETF `RISK_OFF` cash-drip top-up 必须债优先、核心宽基次之
`RISK_OFF` 下的 drip top-up MUST 先补防守债仓，再补核心宽基。系统 SHALL NOT 在债仓缺口仍存在时优先把有限现金分配给核心宽基。

#### Scenario: 有限现金时先补债仓
- **WHEN** `RISK_OFF` 下债与核心宽基都存在未完成缺口
- **AND** 可用现金不足以同时完整补两者
- **THEN** 系统 MUST 优先为债仓生成 drip top-up
- **THEN** 核心宽基 only receives remaining cash after debt-first allocation

### Requirement: ETF `RISK_OFF` cash-drip top-up 必须可审计
系统 MUST 为 `RISK_OFF cash-drip top-up` 输出单独的 activation 与 reject explain，至少区分“已执行 drip top-up”“现金不足最小单位”“目标已满足无需继续补仓”“被硬约束阻断”四类情形。

#### Scenario: cash-drip top-up 保留执行与拒绝原因
- **WHEN** 系统在 `RISK_OFF` 下评估 drip top-up
- **THEN** 运行产物 MUST 记录该路径是否激活
- **THEN** 运行产物 MUST 记录对应 activation 或 reject 原因码
