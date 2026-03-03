## ADDED Requirements

### Requirement: 固定百分比止损
系统 SHALL 支持基于入场价的固定百分比止损，作为 ATR 止损的简单替代。

#### Scenario: 亏损达到阈值触发止损
- **WHEN** 持仓当日收盘价相对入场价的跌幅 ≥ `fixed_stop_loss_pct`（如 0.05 表示 -5%）
- **THEN** 系统 SHALL 在下一交易日开盘价卖出该持仓
- **THEN** 交易记录的 `reason_code` SHALL 为 `FIXED_STOP_LOSS`

#### Scenario: 固定止损默认关闭
- **WHEN** `enable_fixed_stop_loss` 为 false 或 `fixed_stop_loss_pct` 为 0
- **THEN** 固定止损规则 SHALL 不参与退出判断

#### Scenario: 与 ATR 止损共存
- **WHEN** 同时启用 ATR 止损和固定百分比止损
- **THEN** 两者 SHALL 独立判断，先触发者生效
- **THEN** ATR 止损的 `reason_code` 仍为 `ATR_STOP_LOSS`，固定止损为 `FIXED_STOP_LOSS`

#### Scenario: 固定止损优先级
- **WHEN** 退出优先级判断
- **THEN** 固定止损 SHALL 与 ATR 止损同级（风控退出 > 趋势破位 > ATR止损/固定止损 > 止盈 > 时间退出 > 信号反转）

### Requirement: 固定止损计数器
系统 SHALL 输出固定止损触发的计数器。

#### Scenario: 计数器写入 run_meta
- **WHEN** 回测完成
- **THEN** `run_meta.json` 的 `counters` 对象 SHALL 包含 `fixed_stop_loss_exit_count`（整数）

### Requirement: 前端固定止损配置控件
前端 SHALL 提供固定止损参数的配置入口。

#### Scenario: 固定止损 UI 控件
- **WHEN** 用户查看退出配置区域
- **THEN** SHALL 显示"固定止损"checkbox（默认关闭）
- **THEN** 勾选后 SHALL 显示百分比输入框，默认值 5%
