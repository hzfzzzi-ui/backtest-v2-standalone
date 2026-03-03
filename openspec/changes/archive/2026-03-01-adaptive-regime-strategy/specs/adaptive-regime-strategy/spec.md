# adaptive-regime-strategy

自适应市场状态策略——根据 benchmark 实时 regime 信号自动在趋势跟踪模式和均值回归模式之间切换。

## Requirements

### REQ-1: 双模式信号路由

策略必须支持两种运行模式，根据 regime 状态自动切换：
- **趋势模式 (TREND)**: 当 `risk_on = True`（benchmark > benchmark_MA）时激活
  - 信号逻辑: SMA fast/slow 金叉买入，死叉卖出
  - 与现有 `sma_cross` 策略行为一致
- **均值回归模式 (MEAN_REVERT)**: 当 `risk_on = False` 时激活
  - 信号逻辑: RSI(rsi_period) 上穿 `rsi_buy_threshold` 买入，下穿 `rsi_sell_threshold` 卖出
  - 附加退出: 持仓超过 `mr_max_hold_days` 天强制卖出（时间退出）
  - 附加退出: 亏损超过 `mr_stop_loss_pct` 强制卖出（止损退出）

### REQ-2: Regime 检测机制

- 使用 benchmark（默认沪深300）的收盘价 vs MA(regime_ma) 判断
- `regime_ma` 可配置（默认 60，比现有默认 120 更灵敏）
- 只使用当前 bar 及之前的数据计算（无未来函数）
- Regime 状态变化时，自动触发模式切换：
  - TREND → MEAN_REVERT: 不强制清仓（保持现有持仓由均值回归模式管理）
  - MEAN_REVERT → TREND: 不强制清仓（保持现有持仓由趋势模式管理）

### REQ-3: 策略参数

| 参数 | 默认值 | 说明 |
|------|-------|------|
| fast | 5 | 趋势模式快均线周期 |
| slow | 20 | 趋势模式慢均线周期 |
| regime_ma | 60 | Regime 检测 MA 周期 |
| benchmark_symbol | 000300.SH | Regime 检测基准指数 |
| rsi_period | 6 | 均值回归模式 RSI 周期 |
| rsi_buy_threshold | 25 | RSI 买入阈值（上穿） |
| rsi_sell_threshold | 70 | RSI 卖出阈值（下穿） |
| mr_max_hold_days | 10 | 均值回归模式最大持仓天数 |
| mr_stop_loss_pct | 0.05 | 均值回归模式止损百分比 |
| order_size | 1000 | 默认下单数量 |

### REQ-4: 信号输出格式

每个信号必须包含 meta 字段：
- `regime_on`: bool — 当前 regime 状态
- `signal_mode`: "TREND" | "MEAN_REVERT" — 当前激活的模式
- `benchmark_close`: float — benchmark 收盘价
- `benchmark_ma`: float — benchmark MA 值
- 趋势模式额外字段: `fast_ma`, `slow_ma`, `cross_up`, `cross_down`
- 均值回归模式额外字段: `rsi_value`, `rsi_prev`, `rsi_cross_up`, `rsi_cross_down`

### REQ-5: Reason Code 清单

| reason_code | 含义 |
|-------------|------|
| TREND_SMA_CROSS_UP | 趋势模式 SMA 金叉买入 |
| TREND_SMA_CROSS_DOWN | 趋势模式 SMA 死叉卖出 |
| MR_RSI_OVERSOLD_BUY | 均值回归 RSI 超卖买入 |
| MR_RSI_OVERBOUGHT_SELL | 均值回归 RSI 超买卖出 |
| MR_TIME_EXIT | 均值回归持仓超时退出 |
| MR_STOP_LOSS | 均值回归止损退出 |

### REQ-6: 走 generic_signals 引擎路径

- 策略实现 `generate_signals(day, history, positions)` 接口
- 在 `portfolio_simulator_strict.py` 中走 `_run_vector_portfolio_backtest_generic_signals` 路径
- 需要在 `run_vector_portfolio_backtest_strict` 入口处识别该策略并路由到 generic 路径

### REQ-7: 可观测性

- 每次回测 metrics 输出中包含:
  - `regime_trend_days`: 趋势模式天数
  - `regime_mr_days`: 均值回归模式天数
  - `regime_switches`: 模式切换次数
  - `mr_rsi_buy_count`: 均值回归买入次数
  - `mr_rsi_sell_count`: 均值回归卖出次数
  - `mr_time_exit_count`: 均值回归超时退出次数
  - `mr_stop_loss_count`: 均值回归止损次数
