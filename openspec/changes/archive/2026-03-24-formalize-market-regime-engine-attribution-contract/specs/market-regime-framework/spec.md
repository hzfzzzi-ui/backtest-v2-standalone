## MODIFIED Requirements

### Requirement: 正式市场状态框架必须输出状态置信度与切换原因
正式市场状态框架 SHALL 输出统一的 canonical 状态 payload，并且 MUST 同时提供：

- `base_state_5`
- `effective_state_5`
- `coarse_state`
- `effective_coarse_state`
- `regime_confidence`
- `regime_duration_bars`
- `regime_transition_reason`
- `reason_codes`
- `feature_availability`
- `risk_budget_multiplier`
- `defense_bias`

其中：

- `base_state_5` MUST 只使用正式 canonical 五状态：
  - `BULL`
  - `TRANS_UP`
  - `LIGHT`
  - `TRANS_DOWN`
  - `RISK_OFF`
- `coarse_state` MUST 由 `base_state_5` 派生：
  - `RISK_ON`
  - `NEUTRAL`
  - `RISK_OFF`
- canonical 五状态 MUST 作为唯一正式状态真相源。
- `coarse_state` 与 `effective_coarse_state` SHALL 仅作为派生视图，不得反向成为上游状态真相。
- `effective_*` MUST 表示在人工或策略外部干预后的最终生效状态。
- `base_*` MUST 保留模型原始状态真相，不得因 override 被覆盖。
- `regime_transition_reason` MUST 说明状态切换、切换抑制或 fallback 的直接原因。
- `reason_codes` MUST 支持下游 Governor、audit 和前端使用，且不得依赖下游自行再猜测状态语义。

#### Scenario: 正式输出同时包含 base 与 effective 状态
- **WHEN** 系统完成某一交易日的正式市场状态判断
- **THEN** 结果 MUST 同时包含 `base_state_5`、`effective_state_5`、`coarse_state`、`effective_coarse_state`

#### Scenario: 三状态不得反向成为正式真相源
- **WHEN** 任一下游模块消费正式市场状态
- **THEN** 系统 MUST 使 `coarse_state` 与 `effective_coarse_state` 仅作为派生视图存在，且不得允许它们单独覆盖、重建或替代正式五状态

#### Scenario: 切换或抑制时保留原因
- **WHEN** 状态发生切换、被置信度门槛抑制、被最短持续期抑制或因 fallback 未能按候选状态生效
- **THEN** 系统 MUST 输出 `regime_transition_reason` 和 `reason_codes`

### Requirement: 正式市场状态框架必须输出可归因子分数
正式市场状态框架 MUST 同时输出 block 级与 domain 级可归因分数。

block 级输出 MUST 至少包含：

- `block_scores.trend_block`
- `block_scores.risk_block`
- `block_scores.breadth_block`
- `block_scores.participation_block`

domain 级输出 MUST 至少包含：

- `subscores.technical`
- `subscores.sentiment`
- `subscores.macro_global`

其中：

- `technical` MUST 作为 Phase 1 主导解释域。
- `sentiment` SHALL 作为解释增强和弱约束域。
- `macro_global` SHALL 作为解释增强和弱约束域；在 Phase 1 中即使尚未形成强信号，也 MUST 保留正式字段位置。
- 下游不得仅根据总状态名推断状态来源；必须可追溯到 block 或 domain 分数。

#### Scenario: 输出 block 级分数
- **WHEN** 系统输出任意交易日的正式市场状态
- **THEN** 结果 MUST 能追溯到 `trend_block`、`risk_block`、`breadth_block`、`participation_block` 的评分或等价解释字段

#### Scenario: 输出 domain 级分数
- **WHEN** 系统输出任意交易日的正式市场状态
- **THEN** 结果 MUST 同时包含 `technical`、`sentiment`、`macro_global` 三类解释域分数

### Requirement: 正式市场状态框架必须提供可审计的manual override语义
正式市场状态框架 MUST 提供可审计的 `manual_override` 结构，并且 SHALL 至少包含：

- `active`
- `scope`
- `reason`
- `actor`
- `effective_window` 或等价生效时间信息

override contract MUST 满足：

- override SHALL 只影响 `effective_state_*` 或等价最终生效输出。
- override SHALL NOT 覆盖 `base_state_*`。
- override 生效时，系统 MUST 保留模型原始状态与最终状态的双轨输出。
- Governor、research audit 和 snapshot MUST 能区分“模型原始状态”与“人工或外部干预后的最终状态”。

#### Scenario: override 生效时保留双轨状态
- **WHEN** 某一交易日存在状态类 override
- **THEN** 结果 MUST 同时保留 `base_state_*` 与 `effective_state_*`

#### Scenario: override 不得静默生效
- **WHEN** 某一交易日存在任意 manual override
- **THEN** 系统 MUST 记录 `manual_override.active=true` 以及对应的 `reason`、`scope`、`actor`

### Requirement: 正式市场状态框架必须提供最小审计产物
每次启用正式市场状态框架的运行 MUST 产出可审计 regime 证据链，至少包括：

- `portfolio_daily.csv` 中的 `base_state_5`、`effective_state_5`、`coarse_state`、`effective_coarse_state`
- `portfolio_daily.csv` 中的 `regime_confidence`、`regime_duration_bars`、`regime_transition_reason`
- `portfolio_daily.csv` 中的 `reason_codes_json`、`subscores_json`、`manual_override_json`
- `run_meta.json` 中的 regime engine 配置快照与 contract version
- 审计摘要中的状态天数、切换次数、低置信度抑制次数、override 次数、transition reason 分布

系统 SHALL NOT 仅输出最终市场状态而不输出其解释链。

#### Scenario: 产物足以解释状态来源
- **WHEN** 用户查看启用正式 regime framework 的任一回测产物
- **THEN** 产物 MUST 足以回答“今天为什么是这个状态、为什么没有切换、有没有人工干预”
