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
