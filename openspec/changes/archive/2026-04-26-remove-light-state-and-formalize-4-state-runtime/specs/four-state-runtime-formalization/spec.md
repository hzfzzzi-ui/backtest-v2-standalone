## ADDED Requirements

### Requirement: 正式运行状态必须收成 4-state
系统正式运行状态 MUST 只承认 `BULL / TRANS_UP / TRANS_DOWN / RISK_OFF` 四种正式状态。

#### Scenario: 历史 LIGHT 输入兼容映射
- **GIVEN** 上游输入或历史配置包含 `LIGHT` 或 `LIGHT_TREND`
- **WHEN** runtime 进行正式状态解析
- **THEN** 系统 MUST 将其映射为 `TRANS_UP`
- **AND** 新运行产物 MUST NOT 再把 `LIGHT` 作为正式有效状态输出

### Requirement: 账户层预算与 transition contract 不再依赖 LIGHT
账户层 budget map、transition policy 和 execution handoff MUST 基于 4-state 正式状态集合运行。

#### Scenario: 账户层状态解析
- **GIVEN** 账户层消费组件证据
- **WHEN** 生成正式 `effective_state_5`
- **THEN** 输出 MUST 只包含 `BULL / TRANS_UP / TRANS_DOWN / RISK_OFF`

### Requirement: ETF 正式映射不再保留 LIGHT 分支
ETF 正式状态映射、模板与默认权重 MUST 删除 `LIGHT` 运行分支。

#### Scenario: ETF 正式模板解析
- **GIVEN** ETF runtime 解析正式状态模板
- **WHEN** 输入为历史 `LIGHT`
- **THEN** 系统 MUST 按 `TRANS_UP` 模板处理
