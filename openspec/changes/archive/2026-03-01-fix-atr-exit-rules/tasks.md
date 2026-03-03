# Tasks: fix-atr-exit-rules

## 1. SMA 路径退出优先级重排

- [x] 在 `portfolio_simulator_strict.py` 的 SMA 路径 held-only SELL 判断链（约 line 576-598）中，将 `ATR_STOP_LOSS` 和 `FIXED_STOP_LOSS` 检查移到 `TREND_BREAK_EXIT` 之前。新顺序：RISK_OFF → ATR_STOP → FIXED_STOP → TREND_BREAK → TAKE_PROFIT → ATR_TRAIL → TIME → CROSS_DOWN
- [x] 更新同文件中的注释 `# held-only SELL (risk_off > confirmed_trend_break > atr_stop ...)` 使其反映新优先级

## 2. 引擎级计数器补齐（SMA 路径）

- [x] 在 SMA 路径模拟循环初始化处（约 line 333-347），声明 `atr_stop_exit_count = 0` 和 `atr_trail_exit_count = 0`
- [x] 在 `reason == "ATR_STOP_LOSS"` 处（原 line 583）增加 `atr_stop_exit_count += 1`
- [x] 在 `reason == "ATR_TRAIL_EXIT"` 处（原 line 594）增加 `atr_trail_exit_count += 1`
- [x] 在 metrics 输出处（约 line 1013）增加 `metrics["atr_stop_exit_count"]` 和 `metrics["atr_trail_exit_count"]`
- [x] 在顶层 result dict 返回处确保这两个计数器被写入（与 `take_profit_exit_count` 同级）

## 3. Generic 路径退出规则引擎

- [x] 在 `_run_vector_portfolio_backtest_generic_signals` 函数开头，从 strategy 对象提取退出参数：`enable_atr_stop`, `atr_stop_k`, `enable_atr_trail`, `atr_trail_k`, `atr_n`, `max_hold_days` 等（与 SMA 路径 line 209-223 对齐）
- [x] 在 Generic 路径启动时，对每个 symbol 预计算 ATR 序列：从 history DataFrame 中提取 OHLC，按 `atr_n` 窗口计算 True Range → SMA，存为 `atr_lookup: dict[str, dict[date, float]]`
- [x] 在日循环中策略产生信号之前，对所有持仓执行退出规则检查：遍历 `positions`，查 ATR 值和当日收盘价，按优先级判断 ATR_STOP → FIXED_STOP → TAKE_PROFIT → ATR_TRAIL，触发时生成 SELL Signal
- [x] 维护 `peak_close_state`（移动止盈所需）和 `entry_day`（时间退出所需）字典，在 BUY 执行时记录，SELL 执行时清除
- [x] 将退出规则产生的 SELL 信号与策略自身的 SELL 信号合并，按 symbol 去重（退出规则优先）
- [x] 声明并维护 `atr_stop_exit_count`, `atr_trail_exit_count`, `take_profit_exit_count`, `fixed_stop_loss_exit_count` 计数器，写入 metrics

## 4. 发现并修复的额外问题

- [x] SMACrossStrategy 缺少 ATR 退出参数字段：在 `sma_cross.py` 添加 `enable_atr_stop`, `atr_stop_k`, `enable_atr_trail`, `atr_trail_k` 字段
- [x] `registry.py` 的 `build_strategy()` 对 `sma_cross` 未传递 ATR 退出参数（ema_cross 正确传递）
- [x] **关键修复**：退出规则价格尺度不匹配 — `position_avg_cost` 使用不复权价（raw），但 `mx.close` 使用复权价（adjusted），导致 ATR 止损条件永远无法满足（复权价 ~1568 vs 不复权均价 ~14.3）
- [x] SMA 路径修复：引入 `_raw_close_v`（不复权收盘价）和 `_raw_atr`（缩放到不复权尺度的 ATR），所有基于成本的退出比较使用不复权价格
- [x] SMA 路径修复：添加 `_raw_peak_state` 字典追踪不复权峰值，用于 ATR 移动止盈
- [x] Generic 路径修复：将 `_atr_lookup2` 的 ATR 计算源从复权 `hist` 改为 `raw_history`，使 ATR 与 `close_idx`（不复权）一致

## 5. Docker 重建与验证

- [x] Docker 重建
- [x] 验证 ATR止损 k=0.3：`atr_stop_exit_count=10`（之前全为 TREND_BREAK_EXIT）
- [x] 验证 ATR止损 k=0.8 + ATR止盈 k=3.0：`atr_stop_exit_count=8`
- [x] 验证多种退出规则共存：k_stop=2.0 + take_profit=2% + trail=0.5 → ATR_STOP=2, TAKE_PROFIT=3, ATR_TRAIL=4
- [x] 运行回测验证：REGIME_ROUTER + ATR止损 k=0.5 + 止盈 3% → `atr_stop_exit_count=115, take_profit_exit_count=52`，Generic 路径退出规则生效
- [x] 修复 API adapter 为 REGIME_ROUTER/ADAPTIVE_REGIME 编译 exit_rules（之前 return cfg 提前返回跳过了 exit_rules 编译）
- [x] 添加 `enable_atr_stop`, `atr_stop_k`, `enable_atr_trail`, `atr_trail_k` 到 ExitConfig
- [x] Generic 路径退出参数改为优先从 exit_cfg 读取（支持所有策略类型）
