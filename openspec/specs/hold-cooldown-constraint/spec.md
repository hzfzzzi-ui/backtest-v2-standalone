# hold-cooldown-constraint Specification

## Purpose

定义最短持有天数与个股卖出冷却期约束，约束卖出后再买回与过早反向交易的行为。

## Requirements

### Requirement: 最短持有天数约束
引擎 SHALL 支持 `min_hold_days` 参数，持仓天数不足时阻断普通卖出信号。

#### Scenario: cross_down 受 min_hold 约束
- **WHEN** 持仓天数 `(当前日 - entry_day[sym]).days < min_hold_days`
- **THEN** `SMA_CROSS_DOWN` 卖出信号 SHALL 被阻断
- **THEN** 产生 reason_code `BLOCK_MIN_HOLD`

#### Scenario: 风控退出不受约束
- **WHEN** 持仓天数 < min_hold_days 且退出原因为 `ATR_STOP_LOSS`、`ATR_TRAIL_EXIT`、`RISK_OFF_EXIT` 或 `TREND_BREAK_EXIT`
- **THEN** 卖出信号 SHALL 正常执行，不受 min_hold_days 约束

#### Scenario: min_hold_exempt_reasons 可配置
- **WHEN** 配置指定 `min_hold_exempt_reasons` 列表
- **THEN** 列表中的 reason_code SHALL 被豁免 min_hold_days 检查
- **THEN** 默认豁免列表 SHALL 为 `["ATR_STOP_LOSS", "ATR_TRAIL_EXIT", "RISK_OFF_EXIT", "TREND_BREAK_EXIT"]`

#### Scenario: entry_day 记录成交日
- **WHEN** BUY 订单在 T 日开盘成交
- **THEN** `entry_day[sym]` SHALL 记录为 T 日（成交日，非信号日）

#### Scenario: min_hold_days=0 时不启用
- **WHEN** `min_hold_days` 未配置或等于 0
- **THEN** 不执行最短持有检查，所有卖出信号正常通过

### Requirement: 个股卖出冷却期约束
引擎 SHALL 支持 `cooldown_days` 参数，个股清仓后在冷却期内禁止买回。

#### Scenario: 清仓后冷却
- **WHEN** 标的 sym 仓位清零（`positions[sym]` 从 >0 变为 0）成交日为 T
- **THEN** 在 T+1 到 T+cooldown_days 期间，sym 的 BUY 候选 SHALL 被跳过
- **THEN** 产生 reason_code `BLOCK_COOLDOWN`

#### Scenario: 部分减仓不触发冷却
- **WHEN** 卖出后 `positions[sym]` 仍 > 0（部分减仓）
- **THEN** 不写入 `last_sell_day[sym]`，不触发冷却

#### Scenario: cooldown_days=0 时不启用
- **WHEN** `cooldown_days` 未配置或等于 0
- **THEN** 不执行冷却检查，所有 BUY 候选正常通过

#### Scenario: 冷却期过期自动清理
- **WHEN** `(当前日 - last_sell_day[sym]).days >= cooldown_days`
- **THEN** sym 的冷却约束解除，允许买入

### Requirement: 诊断计数器输出
引擎 SHALL 输出 min_hold 和 cooldown 的阻断计数。

#### Scenario: metrics 包含阻断计数
- **WHEN** 回测完成
- **THEN** metrics SHALL 包含 `min_hold_block_count`（int）和 `cooldown_block_count`（int）

#### Scenario: candidate_diag_reason_counts 包含阻断统计
- **WHEN** 回测完成
- **THEN** `candidate_diag_reason_counts` SHALL 包含 `BLOCK_MIN_HOLD` 和 `BLOCK_COOLDOWN` 条目

#### Scenario: 前端诊断面板展示
- **WHEN** 回测完成且前端渲染诊断面板
- **THEN** 诊断面板 SHALL 显示 `BLOCK_MIN_HOLD` 和 `BLOCK_COOLDOWN` 计数

### Requirement: 前端 UI 控件
前端退出规则面板 SHALL 新增"持仓约束"分组。

#### Scenario: 控件布局
- **WHEN** 用户打开 Risk & Exit 面板
- **THEN** 在 Exit 区域尾部（退出优先级之前）SHALL 显示"持仓约束"分组
- **THEN** 包含：min_hold_days 数字输入（0~15，默认 0）、cooldown_days 数字输入（0~30，默认 0）

#### Scenario: 参数传递
- **WHEN** 用户设置 min_hold_days 和 cooldown_days 并运行回测
- **THEN** `buildConfigDraft()` SHALL 在 `exit_rules.hold_constraint` 下输出这些参数
- **THEN** `_build_runtime_cfg_from_workbench()` SHALL 映射到 `strategy.params.min_hold_days` 和 `strategy.params.cooldown_days`
