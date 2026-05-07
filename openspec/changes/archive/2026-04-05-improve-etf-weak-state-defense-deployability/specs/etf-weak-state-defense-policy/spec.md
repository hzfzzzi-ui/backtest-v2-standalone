## ADDED Requirements

### Requirement: ETF 弱势状态必须有正式防守承接合同
系统 SHALL 为 `TRANS_DOWN` 与 `RISK_OFF` 定义正式的 ETF 弱势承接策略合同。该合同 MUST 明确弱势状态目标、允许资产类别、资产优先级、暴露上限与 deployability 语义，并且不得依赖隐式 layering 或 fallback 细节作为唯一真相。

#### Scenario: 弱势状态输出正式防守策略快照
- **WHEN** ETF sleeve 在 `TRANS_DOWN` 或 `RISK_OFF` 下运行
- **THEN** 系统 MUST 依据正式弱势承接合同生成目标暴露与候选资产范围
- **THEN** 运行产物 MUST 能追溯到对应弱势策略层与原因码

### Requirement: ETF 弱势状态必须优先使用防守资产池
在 `RISK_OFF` 下，系统 MUST 优先使用正式防守资产池承接风险预算；在 `TRANS_DOWN` 下，系统 MAY 在防守资产之外允许有限 defensive equity 或极小核心 beta，但 SHALL NOT 把高 beta 风险资产当作默认承接工具。系统 SHALL NOT 把长期反向 ETF 或杠杆 ETF 作为正式弱势承接真相。

#### Scenario: Risk-off 优先选择防守资产
- **WHEN** `effective_state_5 = RISK_OFF` 且正式防守资产池中存在可交易标的
- **THEN** 系统 MUST 先从正式防守资产池中生成可部署候选
- **THEN** 系统 SHALL NOT 先用普通宽基 beta 作为默认承接

### Requirement: ETF 弱势部署在可承接时必须可执行
当弱势状态目标暴露大于零且正式防守资产池存在可交易标的时，系统 MUST 保留至少 1 个 deployable defense seat，并生成可执行的防守部署结果。系统 SHALL NOT 仅因通用 slot/cap 规则就把该状态静默压成零部署。

#### Scenario: 存在可交易防守资产时形成最小可执行承接
- **WHEN** `effective_state_5` 属于 `TRANS_DOWN` 或 `RISK_OFF`
- **AND** 正式防守资产池存在可交易标的
- **AND** 弱势状态目标暴露大于 `0.0`
- **THEN** 系统 MUST 形成至少 1 个 deployable defense seat
- **THEN** 生成的目标暴露 MUST 大于 `0.0` 且不超过对应弱势预算上限

#### Scenario: 无可承接资产时显式给出零部署原因
- **WHEN** `effective_state_5` 属于 `TRANS_DOWN` 或 `RISK_OFF`
- **AND** 正式防守资产池不存在可交易标的
- **THEN** 系统 MAY 输出零部署
- **THEN** 运行产物 MUST 显式记录无可承接资产的原因码，而不是只留下空结果
