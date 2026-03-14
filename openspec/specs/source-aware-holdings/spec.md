# source-aware-holdings Specification

## Purpose
定义多 alpha 组合场景下的持仓来源归因、来源感知退出和来源元数据透传要求。

## Requirements
### Requirement: 入场来源归因
系统 SHALL 为每笔由组合后信号触发的入场订单与新建持仓保留最小来源归因信息，包括：
- `entry_alpha_id`
- `entry_sleeve_id`
- `entry_reason_code`
- `entry_date`

这些字段 MUST 从组合后信号一路透传到订单、成交记录和持仓状态。

#### Scenario: 新建持仓保留来源
- **WHEN** `S7` 基于 `composed_signal` 生成买入订单并在次日成交
- **THEN** 对应持仓 SHALL 记录该笔订单的 `entry_alpha_id` 与 `entry_sleeve_id`
- **THEN** 后续审计产物 SHALL 能追溯该持仓的来源

#### Scenario: 未成交订单不写入持仓来源
- **WHEN** 某笔带来源归因的买入订单因停牌、涨跌停或无成交而未执行
- **THEN** 系统 SHALL 保留订单级来源信息
- **THEN** 系统 SHALL 不为该标的创建新的持仓来源记录

### Requirement: 来源感知退出所有权
系统 SHALL 默认采用 `holding_ownership = source_only`。

在该模式下，`S9` 生成的退出信号 MUST 只作用于 `entry_alpha_id` 匹配的持仓；`S8` MAY 以全局风险覆盖方式强制退出任意持仓，但 MUST 显式标记为全局覆盖，而不是策略来源退出。

#### Scenario: 来源策略只退出本来源持仓
- **WHEN** `rsi_reversal` 产生卖出信号，而某标的当前持仓的 `entry_alpha_id` 为 `breakout_55`
- **THEN** `S9` SHALL 不得将该信号应用于该持仓
- **THEN** 审计结果 SHALL 记录该信号因来源不匹配而未执行

#### Scenario: 全局风险覆盖允许强平
- **WHEN** `S8` 触发全局风险关闭并要求退出某持仓
- **THEN** 系统 SHALL 允许该持仓被卖出
- **THEN** 对应卖出记录 SHALL 标记 `exit_owner = global_risk_override`

### Requirement: 来源元数据透传
系统 SHALL 在订单、成交和审计记录中透传来源元数据，以支持回放、归因和 UI 校验。

#### Scenario: 订单与成交记录包含来源字段
- **WHEN** 一笔来源感知持仓发生买入或卖出成交
- **THEN** `orders.csv` 与 `trades.csv` SHALL 包含与该笔交易关联的 `alpha_id` 或 `entry_alpha_id`
- **THEN** 同步生成的审计记录 SHALL 能区分策略退出与全局风险覆盖退出
