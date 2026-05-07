# entry-trend-filter Specification

## Purpose

TBD — 入场趋势过滤能力，基于 slow_ma 的位置和斜率对买入信号进行过滤，以减少逆趋势入场。

---

## Requirements

### Requirement: close > slow_ma 入场过滤
VECTOR 引擎 SHALL 支持基于 close 与 slow_ma 相对位置的入场过滤。

#### Scenario: 启用 close > slow_ma 过滤
- **WHEN** 配置 `enable_entry_above_slow_ma = true`
- **THEN** 仅当当日 `close > slow_ma` 时，该标的的金叉买入信号才通过过滤
- **THEN** 不满足条件的买入信号 SHALL 被阻断，reason_code 记录 `BLOCK_ENTRY_BELOW_SLOW_MA`

#### Scenario: 禁用时行为不变
- **WHEN** 配置 `enable_entry_above_slow_ma = false`（默认）
- **THEN** 入场过滤不生效，行为与变更前一致

---

### Requirement: slow_ma 斜率入场过滤
VECTOR 引擎 SHALL 支持基于 slow_ma 斜率方向的入场过滤。

#### Scenario: 启用 slow_ma 斜率过滤
- **WHEN** 配置 `enable_entry_slow_ma_slope = true`
- **THEN** 仅当 `slow_ma[t] - slow_ma[t - entry_slope_lookback] > 0` 时，该标的的金叉买入信号才通过过滤
- **THEN** 不满足条件的买入信号 SHALL 被阻断，reason_code 记录 `BLOCK_ENTRY_SLOW_MA_SLOPE`

#### Scenario: entry_slope_lookback 参数
- **WHEN** 配置 `entry_slope_lookback = N`（默认 5）
- **THEN** 斜率计算窗口 SHALL 为 N 个交易日
- **THEN** 前 N 日数据不足时，斜率视为不满足（阻断）

#### Scenario: 禁用时行为不变
- **WHEN** 配置 `enable_entry_slow_ma_slope = false`（默认）
- **THEN** 斜率过滤不生效，行为与变更前一致

---

### Requirement: 两个过滤条件可组合
两个入场过滤条件 SHALL 可独立开关，也可同时启用。

#### Scenario: 同时启用
- **WHEN** `enable_entry_above_slow_ma = true` 且 `enable_entry_slow_ma_slope = true`
- **THEN** 买入信号须同时满足两个条件才通过（AND 逻辑）
- **THEN** 分别统计各条件的阻断次数

#### Scenario: 仅启用其一
- **WHEN** 仅其中一个为 true
- **THEN** 仅应用该条件，另一条件视为全部通过

---

### Requirement: 诊断可观测性
每个入场过滤条件 SHALL 有独立的诊断计数器。

#### Scenario: 计数器输出
- **WHEN** 回测完成
- **THEN** `run_meta.json` counters SHALL 包含：
  - `entry_above_slow_ma_block_count`: 被 close <= slow_ma 阻断的买入信号总数
  - `entry_slope_block_count`: 被 slow_ma 斜率 <= 0 阻断的买入信号总数

#### Scenario: 信号级 meta
- **WHEN** 引擎生成买入候选诊断信息时
- **THEN** 信号 meta SHALL 包含 `entry_above_slow_ma: bool` 和 `slow_ma_slope_pos: bool` 字段

---

### Requirement: 前端 Signal Generation 面板
前端 SHALL 在 Signal Generation 区域提供入场过滤的配置控件。

#### Scenario: UI 控件
- **WHEN** 用户打开 Signal + Composition 面板
- **THEN** Signal Generation 区域 SHALL 显示入场过滤子区域，包含：
  - checkbox `close > slow_ma`（默认关闭）
  - checkbox `slow_ma 斜率 > 0`（默认关闭）
  - 数字输入 `斜率回看天数`（默认 5，仅在斜率 checkbox 启用时可编辑）

#### Scenario: 参数传递
- **WHEN** 用户勾选入场过滤 checkbox 并提交回测
- **THEN** 前端 SHALL 将 `enable_entry_above_slow_ma`、`enable_entry_slow_ma_slope`、`entry_slope_lookback` 传递给后端
