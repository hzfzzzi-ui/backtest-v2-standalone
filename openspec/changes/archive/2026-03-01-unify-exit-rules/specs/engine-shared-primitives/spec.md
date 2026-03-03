## ADDED Requirements

### Requirement: 引擎退出规则评估函数
引擎 SHALL 提供共享函数 `_evaluate_engine_exits()` 评估所有持仓的引擎级退出规则。该函数 MUST：
- 接收当前持仓列表、当日日期、收盘价索引、均价字典、ATR 查询函数、峰值状态字典、入场日字典、退出配置（ExitConfig）、以及可选的 risk_on 标志和 max_hold_days
- 按优先级顺序评估退出规则：RISK_OFF > ATR_STOP > FIXED_STOP > TAKE_PROFIT > ATR_TRAIL > TIME_EXIT
- 每个标的最多触发一条退出信号（命中最高优先级规则后跳过后续规则）
- 更新峰值状态（原地修改）
- 返回退出信号列表和各规则触发计数
- 函数 MUST NOT 包含策略层退出逻辑（如 TREND_BREAK_EXIT、CROSS_DOWN），这些属于信号提供者职责

#### Scenario: RISK_OFF 退出
- **WHEN** risk_on 为 False 且持仓存在
- **THEN** 对所有持仓生成 RISK_OFF_EXIT 信号，优先级最高

#### Scenario: ATR_STOP_LOSS 退出
- **WHEN** enable_atr_stop 为 True，ATR 值有效，收盘价 ≤ 均价 - atr_stop_k × ATR
- **THEN** 生成 ATR_STOP_LOSS 信号，atr_stop_exit_count 加 1

#### Scenario: FIXED_STOP_LOSS 退出
- **WHEN** enable_fixed_stop_loss 为 True，均价 > 0，收盘价 ≤ 均价 × (1 - fixed_stop_loss_pct)
- **THEN** 生成 FIXED_STOP_LOSS 信号，fixed_stop_loss_exit_count 加 1

#### Scenario: TAKE_PROFIT 退出
- **WHEN** enable_take_profit 为 True，均价 > 0，且满足止盈条件（pct 模式或 atr 模式）
- **THEN** 生成 TAKE_PROFIT 信号，take_profit_exit_count 加 1

#### Scenario: ATR_TRAIL_EXIT 退出
- **WHEN** enable_atr_trail 为 True，ATR 值有效，收盘价 ≤ 峰值 - atr_trail_k × ATR
- **THEN** 生成 ATR_TRAIL_EXIT 信号，atr_trail_exit_count 加 1

#### Scenario: TIME_EXIT 退出
- **WHEN** max_hold_days > 0，标的在 entry_day 中有记录，持仓天数 ≥ max_hold_days
- **THEN** 生成 TIME_EXIT 信号

#### Scenario: 峰值状态更新
- **WHEN** 评估某标的退出规则时
- **THEN** 峰值状态更新为 max(当前峰值, 当日收盘价)，无论是否触发退出

#### Scenario: 两路径使用同一函数
- **WHEN** SMA 路径和 Generic 路径分别调用 `_evaluate_engine_exits()`
- **THEN** 引擎级退出规则的判断结果完全一致；SMA 路径的 TREND_BREAK_EXIT 和 CROSS_DOWN 在调用方处理
