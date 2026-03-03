## ADDED Requirements

### Requirement: 固定百分比止盈
系统 SHALL 支持基于入场价的固定百分比止盈退出。

#### Scenario: 浮盈达到阈值触发止盈
- **WHEN** 持仓当日收盘价相对入场价的涨幅 ≥ `take_profit_pct`（如 0.10 表示 10%）
- **THEN** 系统 SHALL 在下一交易日开盘价卖出该持仓
- **THEN** 交易记录的 `reason_code` SHALL 为 `TAKE_PROFIT`

#### Scenario: 止盈默认关闭
- **WHEN** `enable_take_profit` 为 false 或 `take_profit_pct` 为 0
- **THEN** 止盈规则 SHALL 不参与退出判断

#### Scenario: 止盈优先级
- **WHEN** 同一天同一持仓同时触发止盈和其他退出规则
- **THEN** 止盈 SHALL 排在 ATR 止损之后、时间退出之前（优先级：风控退出 > 趋势破位 > ATR止损 > 止盈 > 时间退出 > 信号反转）

### Requirement: ATR 倍数止盈
系统 SHALL 支持基于 ATR 倍数的止盈退出，作为固定百分比的替代模式。

#### Scenario: ATR 止盈触发
- **WHEN** `take_profit_mode` 为 `"atr"` 且持仓当日收盘价 ≥ 入场价 + `take_profit_atr_k` × ATR
- **THEN** 系统 SHALL 在下一交易日卖出，`reason_code` 为 `TAKE_PROFIT`

#### Scenario: 两种模式互斥
- **WHEN** `take_profit_mode` 为 `"pct"` 时
- **THEN** 使用 `take_profit_pct` 阈值
- **WHEN** `take_profit_mode` 为 `"atr"` 时
- **THEN** 使用 `take_profit_atr_k` × ATR 阈值

### Requirement: 止盈计数器与可观测性
系统 SHALL 输出止盈触发的计数器，供 UI 验证。

#### Scenario: 计数器写入 run_meta
- **WHEN** 回测完成
- **THEN** `run_meta.json` 的 `counters` 对象 SHALL 包含 `take_profit_exit_count`（整数）
- **THEN** 该值 SHALL 等于 `reason_code == TAKE_PROFIT` 的交易总数

### Requirement: 前端止盈配置控件
前端 SHALL 提供止盈参数的配置入口。

#### Scenario: 止盈 UI 控件
- **WHEN** 用户查看退出配置区域
- **THEN** SHALL 显示"止盈"checkbox（默认关闭）
- **THEN** 勾选后 SHALL 显示模式选择（百分比/ATR）和对应参数输入框
- **THEN** 百分比模式默认值 SHALL 为 10%，ATR 模式默认值 SHALL 为 3.0
