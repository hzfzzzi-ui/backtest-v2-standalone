# cn-a-portfolio-governor Specification

## Purpose
定义 A 股子系统唯一合法的总风险预算与 sleeve 预算总控层，明确市场状态、回撤、恢复、冷却与 defense floor 如何被统一汇总为全组合预算真相。
## Requirements
### Requirement: A股子系统必须存在唯一合法的总风险预算层
A 股子系统 MUST 存在唯一合法的 `global_portfolio_governor`，并且 Governor SHALL 只消费正式 `market_regime_engine` payload。

Governor 的 regime 输入 MUST 至少包含：
- `base_state_5`
- `effective_state_5`
- `coarse_state`
- `effective_coarse_state`
- `regime_confidence`
- `reason_codes`
- `risk_budget_multiplier`
- `defense_bias`
- `manual_override`

Governor SHALL NOT：
- 自行根据私有 `market_state` 数值或旧状态名重新猜测 canonical 状态
- 仅根据 `coarse_state` 或 `effective_coarse_state` 单独重建正式五状态
- 绕过 `effective_state_*` 直接用局部 `trade_mode` 决定全组合总风险预算
- 忽略 manual override 而直接使用 `base_state_*`

Governor MUST 将其消费的 regime 输入作为正式预算真相来源。

#### Scenario: Governor 只消费正式 regime payload
- **WHEN** Governor 计算总风险预算与 sleeve budget
- **THEN** 输入 MUST 来自正式 regime payload，而不是下游自行拼接的状态字段

#### Scenario: Governor 区分 base 与 effective
- **WHEN** 某一交易日存在 override 或外部状态干预
- **THEN** Governor MUST 能区分 `base_state_*` 与 `effective_state_*`
- **THEN** Governor MUST 对最终预算使用生效状态

### Requirement: Governor 必须统一 drawdown ladder 与恢复状态
`cn-a-portfolio-governor` MUST 统一管理 A 股子系统的 `drawdown_ladder`、`recovery_state`、`cooldown_state` 和 `defense_floor`。Governor SHALL 允许不同 sleeve 在预算内做本地执行，但 MUST 保持回撤与恢复规则对全组合一致。

#### Scenario: 回撤进入更严格档位
- **WHEN** 当前组合回撤穿越 Governor 配置的更高风险档位
- **THEN** Governor MUST 重新计算 `total_risk_budget`
- **THEN** Governor MUST 相应压缩受影响 sleeve 的 `sleeve_budgets`

#### Scenario: 组合处于冷却或恢复阶段
- **WHEN** Governor 判断组合处于 `cooldown` 或 `recovery` 阶段
- **THEN** Governor MUST 在预算输出中显式暴露该状态
- **THEN** 下游 sleeve MUST 基于该状态调整开仓和恢复节奏

### Requirement: Governor 必须输出最小可归因预算证据链
Governor MUST 输出最小可归因预算证据链，并且该证据链 MUST 明确引用 regime 来源。

最小证据链至少包含：
- `portfolio_budget.total_risk_budget`
- `portfolio_budget.total_exposure_cap`
- `portfolio_budget.regime_source_state`
- `portfolio_budget.regime_effective_state`
- `portfolio_budget.regime_reason_codes`
- `portfolio_budget.defense_floor`
- `portfolio_budget.drawdown_state`
- `portfolio_budget.recovery_state`
- `portfolio_budget.cooldown_state`
- `portfolio_budget.sleeve_budgets`
- `portfolio_budget.budget_reason_codes`

其中：
- `regime_source_state` MUST 对应 `base_state_5`
- `regime_effective_state` MUST 对应 `effective_state_5`
- `budget_reason_codes` MUST 明确说明预算是被 regime、drawdown、cooldown、defense floor 还是 override 所驱动

#### Scenario: 预算证据链能回答为什么今天降仓
- **WHEN** Governor 输出某交易日预算摘要
- **THEN** 结果 MUST 能追溯预算变化对应的 regime 状态、drawdown 状态和预算原因码

#### Scenario: 预算证据链能区分状态与预算干预
- **WHEN** 某交易日存在 manual override 或 defense bias
- **THEN** Governor 证据链 MUST 能区分“状态本身变了”和“预算被额外压缩/偏防守”两类原因

### Requirement: Governor 必须承担正式多 sleeve 协调，combo 不得成为独立生产模块
当系统需要同时协调 stock sleeve、ETF sleeve 或未来更多正式子系统时，`global_portfolio_governor` MUST 作为唯一合法的 ex-ante 协调层发布预算与风险覆盖。独立 `combo` SHALL NOT 再承担正式预算分配职责。

#### Scenario: 正式多 sleeve 协调
- **WHEN** 系统需要在同一账本中协调多个正式子系统
- **THEN** budget coordination MUST 来源于 `global_portfolio_governor`
- **THEN** 独立 `combo` SHALL NOT 作为正式生产模块承担该职责

### Requirement: Governor 必须区分真实 breadth 限仓与 ETF sleeve slot-cap 限仓
当 `global_portfolio_governor` 为 `cn_etf` 输出预算证据链时，系统 MUST 区分真实 breadth 模块施加的仓位压缩和 ETF sleeve 本地 slot-cap 施加的仓位压缩。Governor SHALL NOT 再把 ETF sleeve 的 slot-cap 压缩误报为 `BREADTH_CAP_ACTIVE`。

#### Scenario: breadth 未启用时不得误报 breadth 标签
- **WHEN** `cn_etf` 运行中 breadth 模块未启用，但 ETF sleeve slot-cap 小于 `hard_max_positions`
- **THEN** Governor MUST NOT 输出 `BREADTH_CAP_ACTIVE`
- **THEN** Governor MUST 输出独立的 ETF slot-cap 标签或等价字段

#### Scenario: breadth 与 ETF slot-cap 同时生效时可同时归因
- **WHEN** breadth 模块真实压缩仓位，且 ETF sleeve slot-cap 也进一步压缩预算
- **THEN** Governor MUST 同时保留 breadth 和 ETF slot-cap 两类归因
- **THEN** 预算证据链 MUST 能让下游审计区分两者不是同一个原因

### Requirement: Governor 必须暴露 slot-cap 最小来源字段
当 `cn_etf` sleeve 的预算被 slot-cap 压缩时，Governor MUST 在预算快照中暴露最小可审计的 slot-cap 来源字段，供 diagnostics、audit 和 rootcause 摘要直接消费，而 SHALL NOT 要求下游根据 runtime reason codes 反推来源。

#### Scenario: ETF slot-cap 来源可被快照直接读取
- **WHEN** Governor 输出某个 `cn_etf` 交易日预算摘要
- **THEN** 快照 MUST 直接包含 slot-cap 是否生效以及其来源文本
- **THEN** 下游系统 MUST 能仅依赖 Governor 快照判断该日是否属于 ETF slot-cap 压缩

### Requirement: Governor 必须向正式 sleeve 发布分层预算合同
`cn-a-portfolio-governor` MUST 将正式 sleeve 的预算真相拆分为可审计的分层合同，而不是只发布单一 `target_exposure`。对每个正式 sleeve，Governor SHALL 至少输出：

- `strategic_floor_cap`
- `tactical_overlay_cap`
- `deployment_pace`
- `hard_block_flags`
- `defense_bias`

现有 `target_exposure` 若继续保留，MUST 仅作为聚合视图存在，且 SHALL NOT 取代上述分层预算字段作为正式真相来源。

下游 sleeve 在形成对执行层的正式动作合同时，`suggested_size` MUST 以自身 budget 为基准表达，而 SHALL NOT 直接把全组合绝对权重写成对子系统外部合同。

#### Scenario: Governor 在正常风险环境下发布分层预算
- **WHEN** Governor 评估某个正式 sleeve 处于可承担正常风险的状态
- **THEN** Governor MUST 输出正的 `strategic_floor_cap`
- **THEN** Governor MAY 输出正的 `tactical_overlay_cap`
- **THEN** Governor MUST 输出明确的 `deployment_pace`

#### Scenario: Governor 在弱市但未硬阻断时压缩 overlay
- **WHEN** Governor 判断市场转弱但未触发 `allow_new_risk=false`、`force_deleveraging=true` 或等价硬阻断
- **THEN** Governor MUST 允许 `strategic_floor_cap` 与 `tactical_overlay_cap` 分别变化
- **THEN** Governor SHALL NOT 仅因状态转弱就把全部 budget 静默折叠成单一零目标

#### Scenario: Governor 在硬阻断时显式发布停止新增风险信号
- **WHEN** Governor 触发 `allow_new_risk=false`、`force_deleveraging=true` 或等价硬阻断条件
- **THEN** Governor MUST 在 `hard_block_flags` 中显式输出阻断原因
- **THEN** Governor MUST 允许下游 sleeve 区分“底仓仍允许持有”和“禁止新增风险”两类语义

#### Scenario: sleeve 对执行层只报相对自身预算的动作大小
- **WHEN** 某个正式 sleeve 在 Governor budget 内形成买入或减持动作
- **THEN** 它对执行层发布的大小语义 MUST 相对于自身 budget，而不是直接声明全组合绝对权重

### Requirement: Governor 必须向 execution_kernel 发布独立 risk_override_v1 合同
当 Governor 需要跨来源强平或禁止新增风险时，系统 MUST 由 `global_portfolio_governor` 向 `execution_kernel` 发布独立 `risk_override_v1` 合同，而 SHALL NOT 将该类动作伪装成普通子系统 `action_intent_v1`。

`risk_override_v1` 最小字段至少包括：
- `contract_version`
- `as_of_date`
- `override_owner`
- `scope`
- `action`
- `reason_codes`

第一版最小语义至少支持：
- `scope = portfolio | symbol`
- `action = FORCE_EXIT | REDUCE_ONLY`

#### Scenario: Governor 触发整本账 reduce-only
- **WHEN** Governor 判断当前账本只能减仓、不得新增风险
- **THEN** Governor MUST 发布 `risk_override_v1`
- **THEN** 执行层 MUST 将其优先级置于普通子系统动作之上

#### Scenario: Governor 跨来源强平单个标的
- **WHEN** Governor 判断某个标的需要跨来源强平
- **THEN** Governor MUST 通过 `risk_override_v1` 明确声明对应 `scope`
- **THEN** 后续执行结果 MUST 能显式区分该卖出来自 `global_risk_override`

### Requirement: 正式 Governor 合同不得从固定 research combo 权重派生生产预算
`cn-a-portfolio-governor` SHALL NOT 将固定 stock/ETF 权重假设，例如 `50/50`，解释为正式生产级 sleeve budget 真相。任何固定组合权重只能作为 `research_combo_only` 假设存在，并 MUST 与正式 Governor 合同明确区分。

#### Scenario: 研究组合使用固定 50/50 权重
- **WHEN** 系统运行 `CN_STOCK_ETF_50_50` 或等价 research combo
- **THEN** 该实验 MUST 在 `run_meta`、`audit` 或等价正式产物中显式标记为 `research_combo_only`
- **THEN** 系统 SHALL NOT 将该组合权重写回正式 Governor 预算真相

#### Scenario: 正式多 sleeve 运行发布预算
- **WHEN** 系统进入正式 Governor 驱动的多 sleeve 运行
- **THEN** sleeve budget MUST 来源于 Governor 分层合同
- **THEN** sleeve budget SHALL NOT 默认回退到固定 `0.5 / 0.5` 权重
