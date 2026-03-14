# multi-alpha-signal-composition Specification

## Purpose
定义第一阶段多 alpha 组合能力的支持边界，包括组合模块、S6 组合语义、regime 路由和同股冲突裁决。

## Requirements
### Requirement: 第一阶段组合模块支持
系统 SHALL 在第一阶段支持将 `breakout_55` 与 `rsi_reversal` 作为可组合的 alpha 模块接入 `signal_generation.modules`。

#### Scenario: 接受第一阶段支持的模块
- **WHEN** 回测配置在 `signal_generation.modules` 中声明 `breakout_55` 与 `rsi_reversal`
- **THEN** 配置编译 SHALL 通过
- **THEN** 运行时 SHALL 为两个模块分别保留独立的 `alpha_id`

#### Scenario: 拒绝第一阶段未支持的模块
- **WHEN** 回测配置在 `signal_generation.modules` 中声明第一阶段未支持的模块名称
- **THEN** 配置编译 SHALL 失败
- **THEN** 错误信息 SHALL 明确指出未支持的模块名

### Requirement: S6 组合流程语义
系统 SHALL 在不改变现有 9-stage 编号的前提下，将多 alpha 组合定义为 `S6` 的内部两段流程：
- `S6a` 生成各 alpha 的 `raw_alpha_signal`
- `S6b` 根据组合策略生成 `composed_signal`

`S7` SHALL 只消费组合后的最终买卖信号，不直接读取未组合的原始 alpha 信号。

#### Scenario: 组合模式启用
- **WHEN** 回测配置显式启用 `signal_composition`
- **THEN** 系统 SHALL 先执行 `S6a` 原始信号生成，再执行 `S6b` 组合决策
- **THEN** `S7` SHALL 使用 `composed_signal` 生成仓位与订单

#### Scenario: 组合模式关闭
- **WHEN** 回测配置未声明 `signal_composition`
- **THEN** 系统 SHALL 保持现有单策略路径行为不变
- **THEN** 运行结果 SHALL 与 baseline 单策略口径兼容

### Requirement: regime_route 组合模式
系统 SHALL 支持 `compose_mode = regime_route`，并仅使用 `S2-S5` 在 `t` 日收盘后可见的输出决定各 alpha 是否启用。

`regime_route` SHALL 支持按 regime 映射启用、停用或并存不同 alpha 模块，且组合决策 MUST 在 `t` 日形成并仅影响 `t+1` 的订单。

#### Scenario: 上行趋势优先 breakout
- **WHEN** 当前交易日的 regime 被判定为 `TREND_UP`，且配置矩阵仅为该 regime 启用 `breakout_55`
- **THEN** `S6b` SHALL 仅放行来自 `breakout_55` 的组合后信号
- **THEN** `rsi_reversal` 的原始信号 SHALL 被标记为未启用

#### Scenario: 震荡期允许 breakout 与 reversal 并存
- **WHEN** 当前交易日的 regime 被判定为 `RANGE`，且配置矩阵同时启用 `breakout_55` 与 `rsi_reversal`
- **THEN** `S6b` SHALL 同时评估两个模块的原始信号
- **THEN** 输出的 `composed_signal` SHALL 保留各自的 `alpha_id`

### Requirement: 同股冲突裁决
系统 SHALL 支持 `same_symbol_policy = prefer_higher_score`，在同一交易日同一标的出现多个买入候选时，以更高的 `compose_score` 作为唯一放行结果。

系统 MUST 为每次冲突裁决记录确定性的 `conflict_resolution` 字段，且不得依赖模块声明顺序或遍历顺序隐式决定结果。

#### Scenario: 同股双买信号按分数裁决
- **WHEN** 同一交易日同一标的同时收到 `breakout_55` 与 `rsi_reversal` 的买入候选，且二者 `compose_score` 不同
- **THEN** 系统 SHALL 仅放行分数更高的一条 `composed_signal`
- **THEN** 被抑制的信号 SHALL 记录冲突原因

#### Scenario: 同股无冲突
- **WHEN** 同一交易日不同标的分别收到不同 alpha 的买入候选
- **THEN** 系统 SHALL 不进行同股冲突裁决
- **THEN** 两条 `composed_signal` SHALL 都可进入后续仓位控制阶段
