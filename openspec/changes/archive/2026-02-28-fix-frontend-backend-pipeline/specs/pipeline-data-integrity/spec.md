## ADDED Requirements

### Requirement: reason_code 随策略类型动态变化
引擎 SHALL 根据策略 ma_type 生成对应的 reason_code。

#### Scenario: EMA 策略生成 EMA reason code
- **WHEN** 策略 ma_type 为 "EMA"
- **THEN** BUY 信号 reason_code SHALL 为 "EMA_CROSS_UP"
- **THEN** cross_down SELL 信号 reason_code SHALL 为 "EMA_CROSS_DOWN"

#### Scenario: SMA 策略保持 SMA reason code
- **WHEN** 策略 ma_type 为 "SMA"
- **THEN** reason_code SHALL 保持 "SMA_CROSS_UP" / "SMA_CROSS_DOWN"

### Requirement: 信号漏斗计数完整输出
`_compute_metrics()` SHALL 在 return dict 中包含完整漏斗计数。

#### Scenario: 漏斗字段存在
- **WHEN** 回测完成
- **THEN** metrics SHALL 包含 `total_buy_signals`（原始信号数）
- **THEN** metrics SHALL 包含 `blocked_signals`（被趋势过滤拦截数）

#### Scenario: experiment_runner 正确传递
- **WHEN** experiment_runner 构建 result dict
- **THEN** `raw_signal` SHALL 等于 `total_buy_signals`
- **THEN** `blocked` SHALL 等于 `blocked_signals`

### Requirement: exit_rules 参数完整映射
`_build_runtime_cfg_from_workbench()` SHALL 映射所有 exit_rules 子项到 strategy.params。

#### Scenario: ATR stop 参数映射
- **WHEN** workbench_config 包含 exit_rules.atr_stop
- **THEN** strategy.params SHALL 包含 enable_atr_stop 和 atr_stop_k

#### Scenario: ATR trailing 参数映射
- **WHEN** workbench_config 包含 exit_rules.trailing
- **THEN** strategy.params SHALL 包含 enable_atr_trail 和 atr_trail_k

#### Scenario: time_exit 参数映射
- **WHEN** workbench_config 包含 exit_rules.time_exit
- **THEN** strategy.params SHALL 包含 max_hold_days（从 n_days 映射）

### Requirement: TIME_EXIT 引擎实现
引擎 SHALL 支持基于持仓天数的时间退出。

#### Scenario: 持仓超过 max_hold_days
- **WHEN** `max_hold_days > 0` 且 `(day - entry_day[sym]).days >= max_hold_days`
- **THEN** 引擎 SHALL 生成 reason_code "TIME_EXIT" 的卖出信号

#### Scenario: max_hold_days=0 不启用
- **WHEN** max_hold_days 为 0
- **THEN** 不执行时间退出检查

### Requirement: reversal 统计覆盖所有策略
artifacts 层 reversal_exit_count SHALL 匹配所有策略的 cross_down reason code。

#### Scenario: 匹配 EMA 和 SMA
- **WHEN** 统计 reversal 退出次数
- **THEN** SHALL 匹配 "SIGNAL_REVERSE"、"SMA_CROSS_DOWN"、"EMA_CROSS_DOWN"

### Requirement: 前端 config_draft 加载同步
加载历史实验后，前端 SHALL 同步 config_draft。

#### Scenario: 加载实验后摘要栏正确
- **WHEN** 用户加载历史实验
- **THEN** renderSummaryBar() SHALL 显示实验实际配置而非陈旧 draft

#### Scenario: JSON 预览正确
- **WHEN** 用户加载历史实验
- **THEN** Config JSON 预览 SHALL 显示实验实际配置

### Requirement: experiment label 策略感知
`_generate_experiment_label()` SHALL 按实际策略类型获取 MA 参数。

#### Scenario: EMA 策略标签
- **WHEN** 策略为 EMA_CROSS
- **THEN** label 中的 fast/slow SHALL 从 signal_generation.ema 取值
