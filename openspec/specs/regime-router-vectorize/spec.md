# regime-router-vectorize Specification

## Purpose

Vectorized signal provider for the RegimeRouter strategy, supporting both simple benchmark-MA regime detection and three-layer RegimeFilter integration for per-stock regime routing.

## Requirements

### Requirement: RegimeRouterSignalProvider 预计算

系统 SHALL 提供 `RegimeRouterSignalProvider` 类，实现 `SignalProvider` 协议。`precompute()` 方法 MUST 在日循环前一次性完成以下矩阵构建：
1. OHLC 矩阵（`build_ohlc_matrices_from_history`）
2. 特征矩阵（`compute_feature_matrices`，含 fast_ma、slow_ma、atr14、rsi）
3. SMA 交叉信号矩阵（`build_signal_matrices`，含 cross_up、cross_down）
4. RSI 交叉信号矩阵（rsi_buy：RSI 下穿 buy_threshold；rsi_overbought：RSI 上穿 sell_threshold）
5. **RegimeFilter 预计算**（替代原有的 benchmark close > MA 二值判断）：
   - 创建 `RegimeFilter` 实例，传入配置参数
   - 加载行业指数 OHLCV 和行业映射数据
   - 调用 `regime_filter.precompute(benchmark, sector_data, stock_matrices, industry_mapping)`
   - 用 `regime_filter.regime_signals >= regime_threshold` 生成布尔数组 `regime_on[T]`（按股票维度取每日最大值或自定义聚合）

`precompute()` MUST 从传入的 `strategy`（RegimeRouter 实例）中提取以下参数：
- `regime_ma`（默认 60）-- 保留用于 fallback
- 趋势子策略参数：`fast`、`slow`、`order_size`
- MR 子策略参数：`rsi_period`、`rsi_buy_threshold`、`rsi_sell_threshold`、`mr_max_hold_days`、`mr_stop_loss_pct`、`order_size`
- **新增** RegimeFilter 参数：从 strategy 配置或 kwargs 中提取 `regime_filter_cfg`

#### Scenario: 预计算完成后矩阵可用
- **WHEN** 调用 `provider.precompute(history=..., benchmark=..., trading_days=..., strategy=regime_router)`
- **THEN** provider 内部持有 OHLC 矩阵、特征矩阵、SMA 信号矩阵、RSI 信号矩阵、**RegimeFilter 信号矩阵**，所有矩阵的行数等于 `len(trading_days)`

#### Scenario: RSI 矩阵使用正确的参数
- **WHEN** RegimeRouter 配置 `rsi_period=14`、`rsi_buy_threshold=25`
- **THEN** `compute_feature_matrices` 使用 `rsi_period=14` 计算 RSI 矩阵，RSI 买入信号在 RSI 从 >25 下穿到 <=25 时触发

#### Scenario: RegimeFilter 替代简单均线判断
- **WHEN** RegimeFilter 配置有效（非 None）
- **THEN** `regime_on` 数组由 `regime_filter.regime_signals` 阈值比较生成，不使用旧的 `bench_close > bench_ma(regime_ma)` 逻辑

#### Scenario: 向后兼容（无 RegimeFilter 配置时）
- **WHEN** 未提供 `regime_filter_cfg` 或设为 None
- **THEN** 退回到原有逻辑：`regime_on = bench_close > bench_ma(regime_ma)`

### Requirement: 趋势模式信号生成

当 regime 状态为趋势模式时（`regime_on[day_idx] == True`），`day_signals()` MUST 生成以下信号：

**卖出信号**（按优先级）：
1. 引擎级退出规则（RISK_OFF_EXIT、ATR_STOP_LOSS、FIXED_STOP_LOSS、TAKE_PROFIT、ATR_TRAIL_EXIT）
2. SMA 交叉下穿（`SMA_CROSS_DOWN`）
3. MR 遗留持仓的 RSI 退出：overbought（`MR_RSI_OVERBOUGHT_SELL`）、stop_loss（`MR_STOP_LOSS`）、time_exit（`MR_TIME_EXIT`）

**买入信号**：
- SMA cross_up 且 tradable 且非已持仓 且非 MR 遗留 symbol
- reason_code = `SMA_CROSS_UP`

#### Scenario: 趋势模式下生成 SMA 买入信号
- **WHEN** regime_on == True 且某 symbol 发生 SMA 金叉 且该 symbol 不在 MR 遗留持仓中
- **THEN** 生成 BUY 信号，reason_code = `SMA_CROSS_UP`

#### Scenario: 趋势模式下 MR 遗留持仓检查退出
- **WHEN** regime_on == True 且某持仓 symbol 在 `mr_symbols` 集合中
- **THEN** 对该持仓检查 RSI overbought、stop_loss、time_exit 退出条件

#### Scenario: 趋势模式下 SMA 死叉卖出
- **WHEN** regime_on == True 且某持仓 symbol 发生 SMA 死叉
- **THEN** 生成 SELL 信号，reason_code = `SMA_CROSS_DOWN`

### Requirement: 均值回归模式信号生成

当 regime 状态为均值回归模式时（`regime_on[day_idx] == False`），`day_signals()` MUST 生成以下信号：

**卖出信号**（按优先级）：
1. 引擎级退出规则（RISK_OFF_EXIT、ATR_STOP_LOSS、FIXED_STOP_LOSS、TAKE_PROFIT、ATR_TRAIL_EXIT）
2. RSI overbought 退出（`MR_RSI_OVERBOUGHT_SELL`）
3. MR stop loss（`MR_STOP_LOSS`）：close <= entry_price × (1 - mr_stop_loss_pct)
4. MR time exit（`MR_TIME_EXIT`）：持仓天数 >= mr_max_hold_days

**买入信号**：
- RSI 下穿 buy_threshold 且 tradable 且非已持仓
- reason_code = `MR_RSI_OVERSOLD_BUY`
- 买入后加入 `mr_symbols`，记录 entry_day 和 entry_price

#### Scenario: MR 模式下 RSI 超卖买入
- **WHEN** regime_on == False 且某 symbol RSI 从 >buy_threshold 下穿到 <=buy_threshold
- **THEN** 生成 BUY 信号，reason_code = `MR_RSI_OVERSOLD_BUY`，该 symbol 加入 `mr_symbols`

#### Scenario: MR 模式下持仓超时退出
- **WHEN** regime_on == False 且某 MR 持仓的持仓天数 >= mr_max_hold_days
- **THEN** 生成 SELL 信号，reason_code = `MR_TIME_EXIT`

#### Scenario: MR 模式下止损退出
- **WHEN** regime_on == False 且某 MR 持仓的 close <= entry_price × (1 - mr_stop_loss_pct)
- **THEN** 生成 SELL 信号，reason_code = `MR_STOP_LOSS`

### Requirement: MR 持仓状态跨 regime 持续

`mr_symbols` 集合 MUST 在 regime 切换时保持不变。MR 模式下买入的持仓，在切换到趋势模式后仍标记为 MR 持仓，直到触发退出条件卖出后才从 `mr_symbols` 中移除。

#### Scenario: regime 切换不清空 MR 持仓
- **WHEN** 第 D 天 regime 从 False 切换到 True，且有 MR 持仓未退出
- **THEN** 第 D+1 天 `mr_symbols` 仍包含这些 symbol，趋势模式下继续检查 MR 退出条件

#### Scenario: MR 持仓卖出后清理
- **WHEN** MR 持仓触发退出（overbought/stop_loss/time_exit）并成功卖出
- **THEN** 该 symbol 从 `mr_symbols`、`mr_entry_day`、`mr_entry_price` 中移除

### Requirement: Regime 判断从二值改为逐股票连续信号

当 RegimeFilter 启用时，系统 MUST 将 `regime_on` 的语义从全局二值切换为逐股票连续信号路由：

- 原逻辑：`regime_on[day_idx]` 为全局 bool，所有股票共享同一 regime 状态
- 新逻辑：`regime_signals[day_idx, col_idx]` 为每只股票独立的连续信号 ∈ [0, 1]，通过 `>= regime_threshold` 转为 bool

`day_signals()` 中的 regime 路由逻辑 MUST 改为逐股票判断：
- 趋势模式买入候选：仅限 `regime_signals[day_idx, col] >= threshold` 的股票
- MR 模式买入候选：仅限 `regime_signals[day_idx, col] < threshold` 的股票
- 已有持仓的退出逻辑不受 regime 状态影响（保持现有行为）

#### Scenario: 同一天不同股票不同 regime
- **WHEN** RegimeFilter 启用，股票 A 的 RegimeSignal = 0.8（>= 0.3），股票 B 的 RegimeSignal = 0.1（< 0.3）
- **THEN** 股票 A 走趋势模式（SMA 信号），股票 B 走 MR 模式（RSI 信号）

#### Scenario: 兼容模式下行为不变
- **WHEN** RegimeFilter 未启用
- **THEN** `regime_on` 仍为全局 bool，所有股票共享同一 regime 状态（与现有行为完全一致）

---

### Requirement: Dispatch 路由

`run_vector_portfolio_backtest_strict()` MUST 在检测到 `strategy` 为 `RegimeRouter` 实例时，路由到 `_run_regime_router_path()` 函数，该函数创建 `RegimeRouterSignalProvider` 并调用 `_run_unified_loop()`。

`CompositeStrategy` 和 `AdaptiveRegimeStrategy` MUST 仍走 `_run_generic_path()`。

#### Scenario: RegimeRouter 使用新 provider
- **WHEN** 传入的 strategy 是 RegimeRouter 实例
- **THEN** 使用 `RegimeRouterSignalProvider` 而非 `GenericSignalProvider`

#### Scenario: 其他复合策略不受影响
- **WHEN** 传入的 strategy 是 CompositeStrategy 实例
- **THEN** 仍使用 `GenericSignalProvider`（`_run_generic_path`）

### Requirement: 结果一致性验证

同参数配置下，`RegimeRouterSignalProvider` 路径与 `GenericSignalProvider` 路径产出的 `portfolio_trades.csv` 和 `portfolio_daily.csv` MUST 零差异。

验证指标：
- trades 数量、symbol、side、reason_code 完全一致
- daily NAV 曲线完全一致
- metrics（total_return、max_drawdown、sharpe）完全一致

#### Scenario: 零差异验证
- **WHEN** 使用相同配置分别通过新旧两条路径运行回测
- **THEN** `portfolio_trades.csv` 的行数、每行的 date/symbol/side/reason_code/qty 完全相同；`portfolio_daily.csv` 的 nav 列逐行相等

### Requirement: 可观测性计数器

`RegimeRouterSignalProvider` MUST 输出以下诊断计数器，供 metrics 收集：
- `total_buy_signals`：总买入信号数
- `regime_trend_days`：趋势模式天数（全局层面，RegimeFilter 启用时取 G_m >= threshold 的天数）
- `regime_mr_days`：均值回归模式天数
- `mr_rsi_oversold_buy_count`：MR RSI 超卖买入次数
- `mr_rsi_overbought_sell_count`：MR RSI 超买卖出次数
- `mr_stop_loss_count`：MR 止损退出次数
- `mr_time_exit_count`：MR 超时退出次数
- `atr_stop_exit_count`、`atr_trail_exit_count`、`take_profit_exit_count`、`fixed_stop_loss_exit_count`：引擎退出计数器
- `precompute_seconds`：预计算耗时
- **新增** `regime_filter_diagnostics`：RegimeFilter 的诊断数据（gate_m_mean、gate_sec_coverage、regime_signal_mean 等）

#### Scenario: 计数器非零
- **WHEN** 回测完成且存在 MR 模式交易
- **THEN** `mr_rsi_oversold_buy_count > 0` 且 `regime_mr_days > 0`

#### Scenario: RegimeFilter 诊断数据可访问
- **WHEN** RegimeFilter 启用且回测完成
- **THEN** `regime_filter_diagnostics` 包含 RegimeFilter 的所有诊断字段
