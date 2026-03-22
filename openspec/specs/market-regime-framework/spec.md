# market-regime-framework Specification

## Purpose
TBD - created by archiving change upgrade-market-regime-framework. Update Purpose after archive.
## Requirements
### Requirement: 正式市场状态框架必须只使用 trailing 数据
系统 MUST 提供正式的 `market-regime-framework`，并且所有市场状态判断 SHALL 只使用当日及之前可观测的数据。框架 MUST 支持通过 rolling/lookback 方式计算特征，但 MUST 禁止使用任何未来数据、居中窗口或 ex-post 平滑结果作为正式状态真相。

系统 MUST 提供正式的 `market-regime-framework`，并且所有市场状态判断 SHALL 只使用当日及之前可观测的数据。框架 MUST 支持通过 rolling/lookback 方式计算特征，但 MUST 禁止使用任何未来数据、居中窗口或 ex-post 平滑结果作为正式状态真相。

#### Scenario: 仅使用历史数据计算状态
- **WHEN** 系统在任一交易日计算市场状态
- **THEN** 参与计算的价格、波动、广度、参与度特征 MUST 仅来自该日及之前的数据

#### Scenario: 数据不足时进入 fallback
- **WHEN** 正式市场状态框架所需特征历史不足
- **THEN** 系统 MUST 明确标记 `feature_availability` 并进入配置指定的 fallback 模式，而不是静默伪造状态### Requirement: 正式市场状态框架必须组合四类输入
正式市场状态框架 SHALL 将状态判断拆分为四类输入块：
- `trend_block`
- `risk_block`
- `breadth_block`
- `participation_block`

其中：
- `trend_block` MUST 覆盖价格相对长期均线、长期均线斜率或同等趋势确认特征
- `risk_block` MUST 覆盖滚动波动率、ATR 带宽、drawdown 压力或同等级风险特征
- `breadth_block` MUST 覆盖成分股广度类特征
- `participation_block` MUST 覆盖量能或换手参与度类确认特征

#### Scenario: 以多因子而非单一均线判断状态
- **WHEN** 系统输出任一正式市场状态
- **THEN** 该状态 MUST 可追溯到四类输入块中的至少趋势块与风险块，不得仅由单一均线关系直接决定

### Requirement: 正式市场状态框架必须输出状态置信度与切换原因
正式市场状态框架 SHALL 输出：
- `market_state`
- `regime_confidence`
- `regime_duration_bars`
- `regime_transition_reason`
- `feature_availability`

`market_state` 兼容现有状态名：
- `BULL`
- `TRANS_UP`
- `TRANS_DOWN`
- `BEAR`

正式市场状态框架 SHALL 输出：
- `market_state`
- `regime_confidence`
- `regime_duration_bars`
- `regime_transition_reason`
- `feature_availability`

`market_state` 兼容现有状态名：
- `BULL`
- `TRANS_UP`
- `TRANS_DOWN`
- `BEAR`

#### Scenario: 输出状态置信度
- **WHEN** 系统完成某一交易日的状态判定
- **THEN** 结果 MUST 同时包含 `market_state` 和 `regime_confidence`

#### Scenario: 输出切换原因
- **WHEN** 市场状态相较上一交易日发生变化
- **THEN** 系统 MUST 记录 `regime_transition_reason`### Requirement: 正式市场状态框架必须提供 persistence / hysteresis 机制
正式市场状态框架 MUST 提供可配置的持续性控制参数，包括但不限于：
- `entry_confirm_bars`
- `exit_confirm_bars`
- `min_state_duration`
- `confidence_floor`
- `transition_cooldown`

系统 SHALL 使用这些参数抑制高频碎片化切换。

#### Scenario: 状态不满足最短持续期
- **WHEN** 新状态刚出现但尚未满足 `min_state_duration`
- **THEN** 系统 MUST 继续保留前一正式状态，或明确输出 transitional 状态，不得立即硬切换

#### Scenario: 低置信度切换被抑制
- **WHEN** 候选新状态的 `regime_confidence` 低于 `confidence_floor`
- **THEN** 系统 MUST 不确认该切换，并记录相应切换抑制原因

### Requirement: 正式市场状态框架必须提供最小审计产物
每次启用正式市场状态框架的运行 MUST 输出可审计字段与统计结果，至少包括：
- `portfolio_daily.csv` 中的 `market_state`、`trade_mode`、`regime_confidence`、`regime_duration_bars`、`regime_transition_reason`
- `run_meta.json` 中的 regime engine 配置快照
- 统计层中的状态天数、模式天数、状态切换次数、低置信度占比、切换原因分布

每次启用正式市场状态框架的运行 MUST 输出可审计字段与统计结果，至少包括：
- `portfolio_daily.csv` 中的 `market_state`、`trade_mode`、`regime_confidence`、`regime_duration_bars`、`regime_transition_reason`
- `run_meta.json` 中的 regime engine 配置快照
- 统计层中的状态天数、模式天数、状态切换次数、低置信度占比、切换原因分布

#### Scenario: 运行完成后可审计
- **WHEN** 启用正式市场状态框架的回测完成
- **THEN** 产物 MUST 允许用户回答“今天为什么是这个状态、切换是由什么触发的”### Requirement: 正式市场状态框架必须组合四类输入
正式市场状态框架 SHALL 将状态判断拆分为四类输入块：
- `trend_block`
- `risk_block`
- `breadth_block`
- `participation_block`

其中：
- `trend_block` MUST 覆盖价格相对长期均线、长期均线斜率或同等趋势确认特征
- `risk_block` MUST 覆盖滚动波动率、ATR 带宽、drawdown 压力或同等级风险特征
- `breadth_block` MUST 覆盖成分股广度类特征
- `participation_block` MUST 覆盖量能或换手参与度类确认特征

#### Scenario: 以多因子而非单一均线判断状态
- **WHEN** 系统输出任一正式市场状态
- **THEN** 该状态 MUST 可追溯到四类输入块中的至少趋势块与风险块，不得仅由单一均线关系直接决定

### Requirement: 正式市场状态框架必须提供 persistence / hysteresis 机制
正式市场状态框架 MUST 提供可配置的持续性控制参数，包括但不限于：
- `entry_confirm_bars`
- `exit_confirm_bars`
- `min_state_duration`
- `confidence_floor`
- `transition_cooldown`

系统 SHALL 使用这些参数抑制高频碎片化切换。

#### Scenario: 状态不满足最短持续期
- **WHEN** 新状态刚出现但尚未满足 `min_state_duration`
- **THEN** 系统 MUST 继续保留前一正式状态，或明确输出 transitional 状态，不得立即硬切换

#### Scenario: 低置信度切换被抑制
- **WHEN** 候选新状态的 `regime_confidence` 低于 `confidence_floor`
- **THEN** 系统 MUST 不确认该切换，并记录相应切换抑制原因

