## Context

当前 `RegimeRouter` 策略走 `GenericSignalProvider` 路径。该路径每天调用 `strategy.generate_signals(day, history_view, positions)`，而 `RegimeRouter` 内部又调用子策略的 `generate_signals()`，每次都对全部历史做 groupby + sort + rolling MA/RSI 计算。复杂度 O(N×D²)，800 只股票 × 2400 交易日实测 360 秒。

相比之下，SMA 路径通过 `SMASignalProvider` 在 `precompute()` 阶段一次性构建矩阵，`day_signals()` 仅读取矩阵行，复杂度 O(N×D)，同规模数据仅需 17-29 秒。

现有基础设施已具备全部必要矩阵计算能力：
- `compute_feature_matrices()` 已预计算 RSI 矩阵（`FeatureMatrices.rsi`）
- `build_ohlc_matrices_from_history()` 已构建 OHLC + tradable 矩阵
- `build_signal_matrices()` 已构建 SMA 交叉信号矩阵
- `evaluate_engine_exits()` 已实现引擎级退出规则评估

约束条件：
- 不修改 `RegimeRouter` / `RSIReversalStrategy` / `SMACross` 策略本身
- 不修改 `GenericSignalProvider`（保持后备兼容）
- 必须与 GenericSignalProvider 路径产出完全一致的交易结果（零差异验证）

## Goals / Non-Goals

**Goals:**
- 将 `RegimeRouter` 的信号生成从 O(N×D²) 降至 O(N×D)，目标加速 10x-100x
- 新增 `RegimeRouterSignalProvider` 实现 `SignalProvider` 协议
- 复用现有矩阵基础设施（`FeatureMatrices`、`OhlcMatrices`、`build_signal_matrices`）
- 在 `portfolio_simulator_strict.py` 的 dispatch 逻辑中识别 `RegimeRouter` 并路由到新 provider

**Non-Goals:**
- 不优化 `CompositeStrategy` 或 `AdaptiveRegimeStrategy`（它们仍走 GenericSignalProvider）
- 不修改 RegimeRouter 策略接口或行为
- 不新增前端或 API 变更
- 不支持 RegimeRouter 以外的策略组合

## Decisions

### D1: 新建独立 Provider 而非扩展 SMASignalProvider

**选择**: 新增 `RegimeRouterSignalProvider` 类

**替代方案**: 在 SMASignalProvider 中添加 regime/RSI 逻辑

**理由**: SMASignalProvider 已有 656 行，职责单一（SMA/EMA 交叉策略）。RegimeRouter 需要管理双模态信号（趋势 SMA + 均值回归 RSI）和 MR 持仓状态跟踪，混入会破坏 SMA provider 的内聚性。独立类可以清晰地封装 regime 切换逻辑。

### D2: 预计算两套信号矩阵，运行时按 regime 选择

**选择**: `precompute()` 同时构建 SMA 交叉矩阵和 RSI 交叉矩阵，`day_signals()` 根据当日 regime 状态选择使用哪套

**设计**:
```
precompute():
  1. 构建 OhlcMatrices + FeatureMatrices（含 fast_ma、slow_ma、rsi、atr14）
  2. 构建 SMA 信号矩阵（cross_up、cross_down） → 趋势模式买卖信号
  3. 构建 RSI 信号矩阵:
     - rsi_buy = (rsi[i] <= buy_threshold) & (rsi[i-1] > buy_threshold)  # RSI 下穿阈值
     - rsi_sell = (rsi[i] >= sell_threshold) & (rsi[i-1] < sell_threshold)  # RSI 上穿阈值
  4. 构建 benchmark regime 数组:
     - regime_on[i] = bench_close[i] > bench_ma(regime_ma)[i]  # True=趋势, False=震荡

day_signals(day, day_idx, ctx):
  IF regime_on[day_idx]:  # 趋势模式
    卖出: 对持仓检查 SMA cross_down + 引擎退出规则 + MR 遗留持仓的 RSI 退出
    买入: SMA cross_up 候选（排除 MR 遗留持仓的 symbols）
  ELSE:  # 均值回归模式
    卖出: RSI overbought + MR stop_loss + MR time_exit + 引擎退出规则
    买入: RSI oversold 候选
```

**理由**: 所有信号条件（SMA cross、RSI cross、regime state）都可以表示为布尔矩阵，在 precompute 阶段一次性计算。`day_signals()` 只需读取矩阵行 + 管理少量状态（MR 持仓跟踪），不做任何 rolling 计算。

### D3: MR 持仓状态管理方式

**选择**: 在 provider 内部维护 `mr_symbols: set[str]`、`mr_entry_day: dict[str, date]`、`mr_entry_price: dict[str, float]`

**行为**:
- MR 模式下买入成功 → 加入 `mr_symbols`，记录 `mr_entry_day` 和 `mr_entry_price`
- MR 持仓卖出 → 从三个集合中移除
- 趋势模式下，MR 遗留持仓仍需检查 RSI 退出规则（overbought / stop_loss / time_exit）
- 通过 `entry_day_overwrite = False` 确保引擎的 `_process_pending_fills` 不会覆盖 MR entry 记录

**理由**: 这与 `RegimeRouter` 策略中 `mr_symbols` 的追踪逻辑一致。MR 持仓是跨 regime 持续的（趋势切回时不立即卖出，而是等退出条件触发）。

### D4: RSI 信号矩阵的计算方式

**选择**: 复用 `FeatureMatrices.rsi` 矩阵（已由 `_rsi_matrix()` 预计算），在此基础上构建交叉信号

**RSI 买入信号矩阵**:
```python
rsi_buy[i, :] = (rsi[i, :] <= buy_threshold) & (rsi[i-1, :] > buy_threshold) & tradable[i, :]
```

**RSI 卖出信号矩阵**（overbought 退出）:
```python
rsi_overbought[i, :] = (rsi[i, :] >= sell_threshold) & (rsi[i-1, :] < sell_threshold)
```

**MR stop_loss 和 time_exit**: 这两个退出条件依赖运行时状态（entry_price、entry_day），无法矩阵预计算，在 `day_signals()` 中逐持仓检查。

**理由**: `_rsi_matrix()` 使用 Wilder's smoothed RSI（与 `RSIReversalStrategy` 一致），已按列式批量计算。交叉信号只需简单的移位比较，O(N×D) 复杂度。

### D5: Dispatch 路由策略

**选择**: 在 `run_vector_portfolio_backtest_strict()` 中，当检测到 `RegimeRouter` 实例时，使用 `RegimeRouterSignalProvider` 替代 `GenericSignalProvider`

**实现**: 修改 `_run_generic_path` 之前的 dispatch 逻辑：
```python
from backend.core.strategies.regime_router import RegimeRouter

if isinstance(strategy, RegimeRouter):
    return _run_regime_router_path(...)  # 新增的 thin wrapper
elif isinstance(strategy, (CompositeStrategy, AdaptiveRegimeStrategy)):
    return _run_generic_path(...)  # 原有逻辑不变
else:
    return _run_sma_path(...)
```

`_run_regime_router_path` 与 `_run_sma_path` 结构相同：创建 provider → precompute → `_run_unified_loop` → 收集 metrics。

**理由**: 最小化对现有代码的侵入。`GenericSignalProvider` 仍为 `CompositeStrategy` 等策略服务，`RegimeRouter` 独立路由。

### D6: 退出规则的处理方式

**选择**: 在 provider 内部直接检查退出条件（与 SMASignalProvider 一致），不调用 `evaluate_engine_exits()`

**理由**: `evaluate_engine_exits()` 使用 `close_idx` 字典查找价格，而 provider 已持有矩阵数据可直接按索引访问，效率更高。同时 RegimeRouter 需要区分"趋势持仓退出"和"MR 持仓退出"两套逻辑，自行检查更灵活。SMASignalProvider 已经验证了这种模式的正确性。

## Risks / Trade-offs

**[Risk] RSI 计算精度差异** → 使用相同的 `_rsi_matrix()` 函数（Wilder's smoothed, `ewm(alpha=1/period)`），与 `RSIReversalStrategy` 的实现一致。验证时通过逐日 RSI 值对比确认。

**[Risk] MR 遗留持仓退出时机不一致** → RegimeRouter 在趋势模式下调用 `rsi_reversal.generate_exit_only_signals()`，该函数检查 overbought + stop_loss + time_exit。provider 需精确复现这三个条件的优先级和判断逻辑。验证时对比 trades.csv 的 reason_code 分布。

**[Risk] `entry_day_overwrite` 行为差异** → GenericSignalProvider 设置 `entry_day_overwrite = False`，意味着引擎不会覆盖已有的 entry_day 记录。新 provider 必须保持此行为，特别是 MR 持仓在 regime 切换时 entry_day 不被重置。

**[Trade-off] 内存占用增加** → 同时持有 SMA 信号矩阵 + RSI 信号矩阵（各约 N×D×8 bytes）。800 symbols × 2400 days ≈ 29 MB/矩阵，增加 ~100 MB 总计。相比 360s→20s 的加速收益，可接受。

**[Trade-off] 代码重复** → provider 内部的退出规则检查与 SMASignalProvider 有部分重复。但这是有意为之的设计选择——每个 provider 封装自己的信号逻辑，避免跨 provider 耦合。
