## Context

当前 `RegimeRouterSignalProvider` 使用基准指数 MA60 做趋势/MR 二值路由。MA200 四象限分析表明：
- BULL 象限（close > MA200, slope > 0）：+55,440 利润，1,099 笔交易
- 其余三象限合计：-28,168 亏损，2,719 笔交易
- BELOW_FLAT 象限是最差区域（-20,360，多为假突破）

现有 MR 策略（RSI Reversal）在非趋势环境中持续产生小额亏损，是主要损耗来源。需要在 MA60 之上增加 MA200 层级的市场状态过滤，并将 MR 槽位替换为轻趋势策略。

图表层面，研究者需要直观看到不同市场状态的分布和持续时间。

## Goals / Non-Goals

**Goals:**
- 在 `RegimeRouterSignalProvider.precompute()` 中矩阵化计算 MA200 四态市场分类和 trade_mode
- 在 `day_signals()` 中按 trade_mode 三态分发信号（TREND_MAIN / TREND_LIGHT / NO_TRADE）
- 新增 EMA5/20 信号矩阵用于 TREND_LIGHT 路径
- trade_mode 联动 risk_budget 的 trend_multiplier（BULL=1.5, LIGHT=0.6, NO_TRADE=0）
- 在 LWC 收益率图表上绘制市场状态半透明色带

**Non-Goals:**
- 不删除 RSIReversalStrategy 类（保留代码，只改默认值）
- 不改变 RegimeFilter 三层趋势过滤器的逻辑（正交系统）
- 不修改 SMA/Generic signal provider（只影响 RegimeRouter 路径）
- 不实现 per-stock MA200 过滤（仅基于基准指数全局判断）

## Decisions

### D1: MA200 过滤器嵌入 RegimeRouterSignalProvider 而非独立模块

**选择**: 在 `RegimeRouterSignalProvider.precompute()` 中直接计算 MA200 相关指标。

**替代方案**: 创建独立 `Ma200MarketFilter` 类。

**理由**: precompute 已有 benchmark MA 计算的完整管线（MA60, MA120, MA200），新增计算与现有代码高度同构。独立模块增加了一层传参和状态管理，但收益不大——MA200 filter 只在 RegimeRouter 路径有意义。

### D2: slope 用简单差分而非线性回归

**选择**: `slope = MA200[t] - MA200[t - 20]`，正负判断即可。

**替代方案**: 线性回归斜率（更平滑）或 EMA(diff(MA200))。

**理由**: 与之前 MA200 四象限分析使用的方法一致，结果已验证。MA200 本身已极其平滑（200日均线），差分足够稳定。

### D3: trade_mode 在 precompute 阶段静态计算

**选择**: `_market_state[T]` 和 `_trade_mode[T]` 在 precompute 中一次性计算为数组。

**替代方案**: 在 day_signals 中逐日动态判断。

**理由**: precompute 矩阵化计算 O(T) 一次完成，day_signals 中只需 `int(self._trade_mode[i])` 查表 O(1)，保持性能优势。过渡态入场条件（MA20/MA60/breakout）也是纯价格指标，无持仓依赖，可静态预算。

### D4: EMA5/20 信号矩阵与 SMA 并行存储

**选择**: 在 precompute 中同时计算 `_ema_light_buy_ok[T,N]` / `_ema_light_sell_ok[T,N]` / `_ema_light_cand_idx`，与现有 `_sma_buy_ok` / `_sma_sell_ok` 并行。

**理由**: 复用完全相同的 close_filled + ewm 算法模板。内存开销为 2 × T × N bool（极小）。避免在 day_signals 中实时计算 EMA。

### D5: 图表蒙版使用 LWC Series Primitive

**选择**: 实现 `MarketStateOverlay` 类，通过 `series.attachPrimitive()` 挂载到 CandlestickSeries。

**替代方案 A**: HTML canvas overlay（需手动同步滚动/缩放）。
**替代方案 B**: HistogramSeries 模拟背景色（只能单向填充）。

**理由**: LWC v4 的 Series Primitive API 是官方推荐的自定义绘制方式。`paneViews() → renderer.draw()` 在每次图表重绘时自动调用，无需手动同步。`zOrder: 'bottom'` 确保色带在 K 线和 NAV 曲线下方。

### D6: 色带数据从 daily_row 读取而非前端独立计算

**选择**: 后端 daily_row 输出 `market_state` + `trade_mode`，前端解析后传入图表。

**替代方案**: 前端从 benchmark OHLC 独立计算 MA200。

**理由**: 确保图表显示的状态与引擎实际使用的状态完全一致。前端独立计算存在浮点精度差异和边界条件不一致的风险。

### D7: MA200 filter 与 RegimeFilter 三层正交

**选择**: MA200 filter 启用时替代 Mechanism A（MA60 二值 regime_on），但不影响 Mechanism B（RegimeFilter 三层 per-stock 过滤）。

**具体逻辑**: 如果 `_use_regime_filter == True`（三层启用），MA200 filter 作为额外的全局门控叠加——trade_mode == NO_TRADE 时即使个股 regime_on == True 也不产生买入。如果三层未启用，MA200 直接替代 MA60 路由。

## Risks / Trade-offs

**[风险] MA200 warmup 期间默认 BULL 可能产生错误信号** → 缓解: 前 220 个交易日（MA200 + slope_window）标记为 BULL，与现有 MA60 warmup 处理一致。实际回测通常有充足的预热数据。

**[风险] BEAR 态完全空仓可能错过底部反转** → 缓解: TRANS_UP（价格在 MA200 下但斜率转正）的入场条件允许在底部确认后重新进入。60 日突破 + MA20>MA60 是较严格的确认条件，避免假反弹。

**[风险] EMA5/20 信号矩阵增加内存占用** → 缓解: 额外 2 × T × N bool ≈ 2 × 2700 × 500 ≈ 2.7MB，可忽略。

**[权衡] MR 路径废弃意味着震荡市零收益** → 这是有意的设计决策。MA200 分析表明 MR 在所有象限中净亏损，纪律性空仓优于无效交易。

**[权衡] trend_multiplier 从静态变为动态可能影响现有实验对比** → 缓解: market_filter.enabled 默认 False，现有实验结果不受影响。
