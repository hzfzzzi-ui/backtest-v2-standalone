## MODIFIED Requirements

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
- `regime_ma`（默认 60）— 保留用于 fallback
- 趋势子策略参数：`fast`、`slow`、`order_size`
- MR 子策略参数：`rsi_period`、`rsi_buy_threshold`、`rsi_sell_threshold`、`mr_max_hold_days`、`mr_stop_loss_pct`、`order_size`
- **新增** RegimeFilter 参数：从 strategy 配置或 kwargs 中提取 `regime_filter_cfg`

#### Scenario: 预计算完成后矩阵可用
- **WHEN** 调用 `provider.precompute(history=..., benchmark=..., trading_days=..., strategy=regime_router)`
- **THEN** provider 内部持有 OHLC 矩阵、特征矩阵、SMA 信号矩阵、RSI 信号矩阵、**RegimeFilter 信号矩阵**，所有矩阵的行数等于 `len(trading_days)`

#### Scenario: RegimeFilter 替代简单均线判断
- **WHEN** RegimeFilter 配置有效（非 None）
- **THEN** `regime_on` 数组由 `regime_filter.regime_signals` 阈值比较生成，不使用旧的 `bench_close > bench_ma(regime_ma)` 逻辑

#### Scenario: 向后兼容（无 RegimeFilter 配置时）
- **WHEN** 未提供 `regime_filter_cfg` 或设为 None
- **THEN** 退回到原有逻辑：`regime_on = bench_close > bench_ma(regime_ma)`

---

### Requirement: Regime 判断从二值改为逐股票连续信号

当 RegimeFilter 启用时，`regime_on` 的语义从全局二值变为逐股票信号：

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
