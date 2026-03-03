## Why

ATR止损和ATR止盈在代码中"存在"但实际无法有效触发。经测试发现三个问题：
1. **退出优先级错误**：`TREND_BREAK_EXIT` 优先级高于 `ATR_STOP_LOSS`，当 MA 趋势破坏时两个条件同时满足，但趋势破坏永远先触发，导致 ATR 止损计数始终为 0。止损作为风控底线，应具有最高优先级。
2. **Generic 信号路径缺失退出规则**：`REGIME_ROUTER`、`ADAPTIVE_REGIME` 等策略走 `_run_vector_portfolio_backtest_generic_signals` 路径，该路径完全没有退出规则引擎（ATR止损/止盈/移动止盈/固定止损全部不生效）。
3. **引擎缺少 `atr_stop_exit_count` 计数器**：其他退出类型（`take_profit`、`fixed_stop_loss`）在引擎内有显式计数器并写入顶层响应，但 `atr_stop_exit_count` 和 `atr_trail_exit_count` 只通过 reason_code CSV 后置统计，未写入引擎级 metrics。

## What Changes

- **调整退出优先级**：将止损类退出（ATR止损、固定止损）提升到趋势破坏之前。新优先级：`RISK_OFF > ATR_STOP_LOSS > FIXED_STOP_LOSS > TREND_BREAK > TAKE_PROFIT > ATR_TRAIL > TIME_EXIT > CROSS_DOWN`
- **Generic 路径补充退出规则引擎**：在 `_run_vector_portfolio_backtest_generic_signals` 中，对策略产生的 SELL 信号之外，增加对持仓的退出规则检查（ATR止损、固定止损、止盈、移动止盈）
- **补齐引擎级计数器**：在引擎模拟循环中增加 `atr_stop_exit_count` 和 `atr_trail_exit_count` 显式计数器，写入 metrics 和顶层 API 响应

## Capabilities

### New Capabilities
- `generic-path-exit-rules`: Generic 信号路径（REGIME_ROUTER 等）的退出规则引擎，使 ATR止损/止盈/移动止盈/固定止损在所有策略中生效

### Modified Capabilities
- `fixed-pct-stop-loss`: 优先级从"与 ATR 止损同级"调整为"ATR止损 > 固定止损 > 趋势破坏"
- `exit-stats-display`: 引擎级 `atr_stop_exit_count` / `atr_trail_exit_count` 计数器直接写入顶层响应

## Impact

- **后端引擎**：`portfolio_simulator_strict.py` — SMA 路径优先级重排 + generic 路径增加退出检查循环
- **配置适配**：`_experiment_runner_api.py` — 确保 exit_cfg 传入 generic 路径
- **API 响应**：顶层 result dict 增加 `atr_stop_exit_count` / `atr_trail_exit_count` 字段
- **现有 spec**：`fixed-pct-stop-loss` 和 `exit-stats-display` 的优先级/计数器要求需更新
