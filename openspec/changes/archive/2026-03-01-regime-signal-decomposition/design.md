# Design: regime-signal-decomposition

## 架构概览

```
┌────────────────────────────────────────────────────────┐
│ RegimeRouter (Strategy)                                │
│                                                        │
│  ┌──────────────┐                                      │
│  │ RegimeDetector│  benchmark close vs MA(regime_ma)   │
│  └──────┬───────┘                                      │
│         │                                              │
│    TREND│    MEAN_REVERT                               │
│         ├──────────────┐                               │
│         ▼              ▼                               │
│  ┌─────────────┐ ┌──────────────────┐                  │
│  │trend_strategy│ │  mr_strategy     │                  │
│  │(Strategy)   │ │  (Strategy)      │                  │
│  │ SMA/EMA/... │ │ RSIReversal/...  │                  │
│  └─────────────┘ └──────────────────┘                  │
└────────────────────────────────────────────────────────┘
```

## 后端类结构

### 新增文件

**`backend/core/strategies/regime_router.py`**
- `RegimeDetector` — 独立的市况检测器（从 `adaptive_regime._detect_regime` 提取）
- `RegimeRouter(Strategy)` — 路由壳，持有 detector + 两个子策略

**`backend/core/strategies/rsi_reversal.py`**
- `RSIReversalStrategy(Strategy)` — 独立 RSI 均值回归策略（从 `adaptive_regime._generate_mr_signals` 提取）

### 修改文件

**`backend/core/strategies/registry.py`**
- `adaptive_regime` 分支改为构造 `RegimeRouter`:
  ```
  trend_strat = build_strategy(StrategyConfig(name=trend_name, params=trend_params))
  mr_strat = build_strategy(StrategyConfig(name=mr_name, params=mr_params))
  return RegimeRouter(detector=RegimeDetector(...), trend=trend_strat, mr=mr_strat)
  ```

**`backend/core/strategies/adaptive_regime.py`**
- 变为薄包装（向后兼容）或直接删除，由 `RegimeRouter` 取代
- 建议保留为 import alias 以兼容旧配置

**`backend/core/engine_vector/portfolio_simulator_strict.py`**
- `isinstance` 检查从 `AdaptiveRegimeStrategy` 改为 `RegimeRouter`

### MR 持仓跟踪策略

RegimeRouter 需要知道哪些持仓是 MR 模式产生的。方案：

**方案: 利用 Strategy.state**

RegimeRouter 在 `self.state["mr_positions"]` 中维护 MR 模式产生的持仓 symbol 集合。当 mr_strategy 产生 BUY 信号时，记录 symbol；当 mr_strategy 产生 SELL 信号时，移除 symbol。

这与现有 `adaptive_regime.py` 的 `mr_entry_date` / `mr_entry_price` 跟踪方式一致，但拆分后 entry tracking 移入 `RSIReversalStrategy.state` 内部。RegimeRouter 只需跟踪"哪些 symbol 是 MR 产生的"即可。

```
RegimeRouter.state["mr_symbols"] = {"600519.SH", "000001.SZ"}  # MR 产生的持仓
RSIReversalStrategy.state["mr_entry_date"] = {...}               # RSI 内部跟踪
RSIReversalStrategy.state["mr_entry_price"] = {...}              # RSI 内部跟踪
```

## 前端面板结构

### 当前 HTML 结构
```
<details> Signal Generation
  <select> wbStrategyFamily: [SMA | EMA | AR | BREAKOUT | MR]
  <div> wbSigParamsSMA (fast, slow, buffer)
  <div> wbSigParamsAR (全部 AR 参数混在一起)
  ...
```

### 重构后 HTML 结构
```
<details> Signal Generation
  ├─ <details> 市况判断 (Regime Detection)
  │    [✓] 启用
  │    regime_ma: [60]
  │
  ├─ <details> 趋势模式 (TREND Signal)
  │    <select> [SMA_CROSS | EMA_CROSS]
  │    (对应策略参数面板)
  │    (入场趋势过滤)
  │
  └─ <details> 震荡模式 (MR Signal)     ← 仅 regime 启用时显示
       <select> [RSI_REVERSAL]
       RSI周期, 买入阈值, 卖出阈值
       最大持仓天, 止损%
```

### 配置编译路径

**`_experiment_runner_api.py`**

```
新路径:
  sig.regime_detection.enabled = true
  → strategy.name = "regime_router"
  → strategy.params.regime_ma = sig.regime_detection.regime_ma
  → strategy.params.trend_strategy = sig.trend.strategy
  → strategy.params.trend_params = sig.trend.sma / sig.trend.ema
  → strategy.params.mr_strategy = sig.mr.strategy
  → strategy.params.mr_params = sig.mr.rsi

  sig.regime_detection.enabled = false (或不存在)
  → strategy.name = sig.trend.strategy.lower()  (退化为 sma_cross / ema_cross)
  → strategy.params = sig.trend.sma / sig.trend.ema
```

## 向后兼容

1. **策略名兼容**: `adaptive_regime` 在 registry 中仍可识别，内部构造 RegimeRouter(SMA + RSI)
2. **旧配置格式**: `_experiment_runner_api.py` 保留旧 `sig.adaptive_regime` 解析路径（检测到旧格式时自动转换）
3. **产物兼容**: Signal meta 字段、reason_code 不变

## 不变的部分

- 引擎路径: 仍走 `generic_signals`
- 产物协议: perf.json, trades, reason_codes 格式不变
- 现有 SMA/EMA 策略: 完全不受影响
- CompositeStrategy: 不受影响
