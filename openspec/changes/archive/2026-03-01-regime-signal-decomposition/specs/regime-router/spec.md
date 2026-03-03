# regime-router

市况路由器 — 根据 regime detection 结果将信号生成委托给不同子策略。

## ADDED Requirements

### Requirement: RegimeDetector 独立组件

系统 SHALL 提供独立的 `RegimeDetector` 类，负责判断当前市况状态。
- 输入: 当日及之前的 benchmark 历史数据
- 输出: regime 状态枚举（TREND / MEAN_REVERT）
- 检测逻辑: benchmark close vs MA(regime_ma)
- 只使用当前 bar 及之前的数据（无未来函数）
- 数据不足时默认返回 TREND

#### Scenario: 牛市检测
- **WHEN** benchmark close > benchmark MA(regime_ma)
- **THEN** RegimeDetector 返回 TREND

#### Scenario: 非牛市检测
- **WHEN** benchmark close <= benchmark MA(regime_ma)
- **THEN** RegimeDetector 返回 MEAN_REVERT

#### Scenario: 数据不足
- **WHEN** benchmark 历史数据行数 < regime_ma
- **THEN** RegimeDetector 返回 TREND（默认）

### Requirement: RegimeRouter 路由壳

系统 SHALL 提供 `RegimeRouter` 类，实现 `Strategy.generate_signals()` 接口，内部持有：
- 一个 `RegimeDetector` 实例
- 一个趋势模式子策略（`trend_strategy: Strategy`）
- 一个 MR 模式子策略（`mr_strategy: Strategy`）

RegimeRouter 的 `generate_signals()` 逻辑：
1. 调用 RegimeDetector 判断当前 regime
2. 若 regime = TREND → 委托 `trend_strategy.generate_signals()`
3. 若 regime = MEAN_REVERT → 委托 `mr_strategy.generate_signals()`
4. MR 模式产生的持仓在 regime 切回 TREND 时，MUST 继续由 MR 子策略的退出规则管理

#### Scenario: 趋势模式路由
- **WHEN** RegimeDetector 返回 TREND 且无 MR 遗留持仓
- **THEN** RegimeRouter 仅调用 trend_strategy.generate_signals()

#### Scenario: MR 模式路由
- **WHEN** RegimeDetector 返回 MEAN_REVERT
- **THEN** RegimeRouter 仅调用 mr_strategy.generate_signals()

#### Scenario: MR 遗留持仓管理
- **WHEN** RegimeDetector 返回 TREND 但存在 MR 模式产生的未平仓持仓
- **THEN** RegimeRouter 对非 MR 持仓调用 trend_strategy，对 MR 持仓继续应用 mr_strategy 的退出规则（止损/超时），不产生新 MR 买入

### Requirement: 子策略可插拔

RegimeRouter 的 trend_strategy 和 mr_strategy MUST 接受任意实现了 `Strategy.generate_signals()` 接口的策略实例。
- trend_strategy 可以是 SMACrossStrategy、EMACrossStrategy 等
- mr_strategy 可以是 RSIReversalStrategy（从现有代码提取）、BollingerBreakoutStrategy 等
- 每个子策略独立管理自身的参数和状态

#### Scenario: SMA + RSI 组合
- **WHEN** 用户配置 trend_strategy=SMA_CROSS, mr_strategy=RSI_REVERSAL
- **THEN** 系统构造 RegimeRouter(trend=SMACrossStrategy(...), mr=RSIReversalStrategy(...))

#### Scenario: EMA + RSI 组合
- **WHEN** 用户配置 trend_strategy=EMA_CROSS, mr_strategy=RSI_REVERSAL
- **THEN** 系统构造 RegimeRouter(trend=EMACrossStrategy(...), mr=RSIReversalStrategy(...))

### Requirement: Signal meta 字段兼容

RegimeRouter 产生的所有 Signal MUST 包含以下 meta 字段（与现有 adaptive_regime 保持兼容）：
- `regime_on`: bool
- `signal_mode`: "TREND" | "MEAN_REVERT"
- `benchmark_close`: float | None
- `benchmark_ma`: float | None
- 子策略特有的 meta 字段由子策略自行填充

#### Scenario: meta 字段完整性
- **WHEN** RegimeRouter 产生任意 Signal
- **THEN** Signal.meta 包含 regime_on、signal_mode、benchmark_close、benchmark_ma 四个字段

### Requirement: RSIReversalStrategy 独立提取

从现有 `AdaptiveRegimeStrategy._generate_mr_signals()` 提取为独立的 `RSIReversalStrategy` 类，实现 `Strategy.generate_signals()` 接口。
- 参数: rsi_period, rsi_buy_threshold, rsi_sell_threshold, mr_max_hold_days, mr_stop_loss_pct, order_size
- 信号逻辑与现有 MR 模式完全一致
- Reason codes: MR_RSI_OVERSOLD_BUY, MR_RSI_OVERBOUGHT_SELL, MR_TIME_EXIT, MR_STOP_LOSS

#### Scenario: RSI 超卖买入
- **WHEN** RSI 从 <= rsi_buy_threshold 上穿到 > rsi_buy_threshold 且无持仓
- **THEN** 产生 BUY 信号，reason_code = MR_RSI_OVERSOLD_BUY

#### Scenario: RSI 止损退出
- **WHEN** 持仓且当前价格 <= entry_price * (1 - mr_stop_loss_pct)
- **THEN** 产生 SELL 信号，reason_code = MR_STOP_LOSS
