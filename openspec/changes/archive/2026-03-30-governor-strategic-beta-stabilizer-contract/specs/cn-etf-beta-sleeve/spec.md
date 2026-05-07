## ADDED Requirements

### Requirement: formal ETF sleeve 必须支持 strategic beta stabilizer 角色
`cn-etf-beta-sleeve` 在正式主线中 MUST 支持 `strategic_beta_stabilizer` 语义。该语义 SHALL 至少包含三个正式角色层：

- `core_accumulator`
- `tactical_satellite`
- `limited_defense`

正式系统 MUST 能够区分“长期需要保留的 beta 底仓”和“可在状态变化时收缩或扩张的战术暴露”，而不是继续把全部 ETF 目标视为单层 tactical allocation。

#### Scenario: 系统定义 core accumulator
- **WHEN** formal ETF sleeve 进入 `strategic_beta_stabilizer` 模式
- **THEN** 系统 MUST 为 `core_accumulator` 提供显式角色映射
- **THEN** 该角色 SHALL 对应长期 beta 底仓，而不是普通短期轮动目标

#### Scenario: 系统定义 tactical satellite 与 limited defense
- **WHEN** formal ETF sleeve 进入 `strategic_beta_stabilizer` 模式
- **THEN** 系统 MUST 将进攻增强暴露与有限防守暴露从 `core_accumulator` 中分离
- **THEN** `tactical_satellite` 与 `limited_defense` MUST 能被独立审计和归因

### Requirement: formal ETF sleeve 必须先收缩 overlay，再决定弱市承接节奏
在 `strategic_beta_stabilizer` 模式下，formal ETF sleeve MUST 以 Governor 分层预算为准处理弱市语义：

- `LIGHT`：保留战略底仓，收缩部分 overlay，允许低速部署
- `TRANS_DOWN`：继续保留战略底仓，overlay 进一步收缩，允许对 `core_accumulator` 进行 paced accumulation
- `RISK_OFF`：默认保留最低 floor 或 `floor + limited_defense` 过渡，不得新增 `tactical_satellite`

只有 Governor 显式发布硬阻断信号时，formal ETF sleeve 才能停止新增风险或优先去风险。

#### Scenario: TRANS_DOWN 且 Governor 未硬阻断
- **WHEN** ETF sleeve 处于 `TRANS_DOWN` 且 Governor 未发布 `hard_block_flags`
- **THEN** ETF sleeve MUST 先收缩 `tactical_satellite`
- **THEN** ETF sleeve MAY 仅对 `core_accumulator` 执行 paced accumulation

#### Scenario: RISK_OFF 且 Governor 未硬阻断
- **WHEN** ETF sleeve 处于 `RISK_OFF` 且 Governor 未发布硬阻断
- **THEN** ETF sleeve MUST 允许 `core_accumulator` floor 或 `limited_defense` 过渡存在
- **THEN** ETF sleeve SHALL NOT 将 `RISK_OFF` 默认解释为全部目标归零

#### Scenario: Governor 发布硬阻断
- **WHEN** Governor 发布 `allow_new_risk=false`、`force_deleveraging=true` 或等价硬阻断
- **THEN** ETF sleeve MUST 停止新增 `tactical_satellite`
- **THEN** ETF sleeve MUST 优先服从去风险要求，而不是继续执行弱市承接

### Requirement: paced accumulation 必须受 Governor 节奏约束，而不是演变为无限制抄底
`cn-etf-beta-sleeve` 的任何 weak-state accumulation 行为 MUST 消费 Governor 发布的 `deployment_pace` 与 `strategic_floor_cap`，且 SHALL NOT 自行扩大预算、无上限摊平或把价格便宜本身解释为新增风险许可。

#### Scenario: Governor 下发正的 deployment pace
- **WHEN** Governor 为 ETF sleeve 下发正的 `deployment_pace`
- **THEN** ETF sleeve MAY 在 `core_accumulator` 范围内按该节奏逐步部署
- **THEN** ETF sleeve MUST 在产物中显式记录 accumulation 来源于 Governor 节奏，而不是本地自由裁量

#### Scenario: Governor 未下发 deployment pace
- **WHEN** Governor 未提供正的 `deployment_pace`
- **THEN** ETF sleeve SHALL NOT 仅因价格下跌或状态转弱就自行扩大 `core_accumulator` 买入节奏
- **THEN** 系统 MUST 将此类行为视为合同外风险扩张
