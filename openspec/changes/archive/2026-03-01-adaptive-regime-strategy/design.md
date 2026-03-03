# Design: Adaptive Regime Strategy

## 架构决策

### D1: 策略走 generic_signals 路径而非 vectorized 路径

**决策**: `AdaptiveRegimeStrategy` 走 `_run_vector_portfolio_backtest_generic_signals` 路径。

**原因**:
- vectorized 路径（SMA 快速路径）的信号逻辑硬编码在 `portfolio_simulator_strict.py` 中
- generic 路径通过每天调用 `strategy.generate_signals()` 来获取信号，灵活度高
- 均值回归模式需要 RSI 指标和不同的买卖逻辑，不适合嵌入现有 vectorized 信号矩阵
- 性能影响可接受：generic 路径已用于 CompositeStrategy 等复杂策略

**路由方式**: 在 `run_vector_portfolio_backtest_strict` 入口判断 `isinstance(strategy, AdaptiveRegimeStrategy)` 路由到 generic 路径。

### D2: Regime 检测在策略内部实现

**决策**: 不依赖引擎层的 `risk_on` 数组，在策略的 `generate_signals` 内自行计算 benchmark MA 判断 regime。

**原因**:
- generic 路径的 `generate_signals(day, history, positions)` 能拿到完整 history（含 benchmark）
- 策略内部实现 regime 检测可以使用自定义 regime_ma（默认 60，比引擎默认 120 更灵敏）
- 解耦引擎和策略——策略自给自足

### D3: RSI 计算在 features.py 中添加（矩阵化）

**决策**: 在 `FeatureMatrices` 添加 `rsi` 字段，`compute_feature_matrices` 新增 `rsi_period` 参数。

**原因**:
- 虽然 generic 路径不使用 feature matrix，但保持特征计算的集中管理
- 策略内部可以直接从 history 计算 RSI（per-symbol rolling），也可以使用 feature matrix
- 当前设计：策略内部 per-symbol 计算 RSI（因为 generic 路径传入 history DataFrame）
- features.py 的 RSI 矩阵备用，供未来 vectorized 优化

### D4: 模式切换不强制清仓

**决策**: regime 状态从 TREND 切换到 MEAN_REVERT（或反向）时，不强制清仓。

**原因**:
- 强制清仓产生大量不必要交易（参见基线实验中 take_profit 的反面教训）
- 持仓在新模式下由新模式的退出规则自然管理
- 例如：趋势模式买入的持仓，切换到均值回归后，如果 RSI > 70 会自然卖出

## 数据流

```
┌─────────────────────────────────────────────────────────────┐
│                  generic_signals 路径                         │
│                                                              │
│  每天 t:                                                     │
│    history = all data up to day t                            │
│    positions = current holdings                              │
│                                                              │
│    ┌─────────────────────────────────────┐                  │
│    │   AdaptiveRegimeStrategy            │                  │
│    │   .generate_signals(day, hist, pos) │                  │
│    │                                     │                  │
│    │   1. 取 benchmark 数据              │                  │
│    │   2. 计算 bench_close vs bench_MA   │                  │
│    │   3. regime_on = bench > bench_MA   │                  │
│    │                                     │                  │
│    │   if regime_on:                     │                  │
│    │     SMA cross 逻辑 → signals        │                  │
│    │   else:                             │                  │
│    │     RSI reversal 逻辑 → signals     │                  │
│    │                                     │                  │
│    │   return signals                    │                  │
│    └─────────────────────────────────────┘                  │
│                       │                                      │
│                       ▼                                      │
│    引擎执行: priority sell → buy allocation → fill          │
└─────────────────────────────────────────────────────────────┘
```

## 文件变更清单

| 文件 | 变更 |
|------|------|
| `backend/core/strategies/adaptive_regime.py` | **新建** — AdaptiveRegimeStrategy 类 |
| `backend/core/engine_vector/features.py` | 修改 — 新增 rsi 字段和 rsi_period 参数 |
| `backend/core/strategies/registry.py` | 修改 — 注册 adaptive_regime |
| `backend/core/engine_vector/portfolio_simulator_strict.py` | 修改 — 路由到 generic 路径 |
| `backend/api/endpoints/_experiment_runner_api.py` | 修改 — 新增 ADAPTIVE_REGIME 策略包编译 |
| `frontend/assets/js/ui-controls.js` | 修改 — 策略选择器 + 参数面板 |
