## ADDED Requirements

### Requirement: Generic 信号路径退出规则引擎
使用 `_run_vector_portfolio_backtest_generic_signals` 路径的策略（REGIME_ROUTER、ADAPTIVE_REGIME 等）SHALL 支持与 SMA 路径相同的退出规则检查。

#### Scenario: ATR止损在 Generic 路径生效
- **WHEN** 策略类型为 REGIME_ROUTER 或 ADAPTIVE_REGIME 且 `enable_atr_stop = true`
- **WHEN** 持仓当日收盘价 <= avg_cost - atr_stop_k × ATR
- **THEN** 系统 SHALL 生成 SELL 信号，`reason_code` 为 `ATR_STOP_LOSS`

#### Scenario: 固定止损在 Generic 路径生效
- **WHEN** 策略类型为 Generic 路径且 `enable_fixed_stop_loss = true`
- **WHEN** 持仓当日收盘价 <= avg_cost × (1 - fixed_stop_loss_pct)
- **THEN** 系统 SHALL 生成 SELL 信号，`reason_code` 为 `FIXED_STOP_LOSS`

#### Scenario: 止盈在 Generic 路径生效
- **WHEN** 策略类型为 Generic 路径且 `enable_take_profit = true`
- **WHEN** 百分比模式下收盘价 >= avg_cost × (1 + take_profit_pct)，或 ATR 模式下收盘价 >= avg_cost + take_profit_atr_k × ATR
- **THEN** 系统 SHALL 生成 SELL 信号，`reason_code` 为 `TAKE_PROFIT`

#### Scenario: 移动止盈在 Generic 路径生效
- **WHEN** 策略类型为 Generic 路径且 `enable_atr_trail = true`
- **WHEN** 持仓当日收盘价 <= peak_close - atr_trail_k × ATR
- **THEN** 系统 SHALL 生成 SELL 信号，`reason_code` 为 `ATR_TRAIL_EXIT`

### Requirement: Generic 路径退出优先级
退出规则检查 SHALL 在策略自身的 SELL 信号之前执行，且遵循统一优先级。

#### Scenario: 退出规则优先于策略信号
- **WHEN** 同一天某持仓的退出规则触发（如 ATR止损）且策略也产生了该持仓的 SELL 信号
- **THEN** 退出规则的 reason_code SHALL 优先（不重复卖出）

#### Scenario: 退出规则不影响策略 BUY 信号
- **WHEN** 退出规则仅对当前持仓进行检查
- **THEN** 策略产生的 BUY 信号 SHALL 不受退出规则影响

### Requirement: Generic 路径退出规则参数传递
退出规则参数 SHALL 通过 strategy.params 和 exit_cfg 传入 Generic 路径。

#### Scenario: 参数来源与 SMA 路径一致
- **WHEN** 前端配置 exit_rules 并通过 workbench 接口提交
- **THEN** `_experiment_runner_api.py` 编译的 strategy.params 和 exit_cfg SHALL 同时传入 Generic 路径
- **THEN** Generic 路径 SHALL 从 strategy 对象和 exit_cfg 读取退出参数

### Requirement: Generic 路径 ATR 计算
Generic 路径 SHALL 使用与 SMA 路径相同的 ATR 计算方法。

#### Scenario: ATR 值来源
- **WHEN** Generic 路径需要 ATR 值进行退出判断
- **THEN** SHALL 使用 14 日 True Range SMA（与 features.py 中 `compute_feature_matrices` 的 `atr14` 一致）
- **THEN** ATR 窗口参数 SHALL 从 `strategy.atr_n`（默认 14）读取
