## Context

VECTOR 引擎有两条执行路径：
1. **SMA 路径**（`run_vector_portfolio_backtest_strict` 主体）：SMA_CROSS / EMA_CROSS 使用，引擎内硬编码了完整的退出规则优先级链
2. **Generic 路径**（`_run_vector_portfolio_backtest_generic_signals`）：REGIME_ROUTER / ADAPTIVE_REGIME 使用，策略自行产生信号，引擎仅执行

当前 SMA 路径的退出优先级为 `RISK_OFF > TREND_BREAK > ATR_STOP > FIXED_STOP > TAKE_PROFIT > ATR_TRAIL > TIME > CROSS_DOWN`。止损类退出（ATR / 固定）排在趋势破坏之后，导致 ATR 止损实质上无法触发。Generic 路径完全没有退出规则引擎。

## Goals / Non-Goals

**Goals:**
- 调整 SMA 路径退出优先级，使止损类退出优先于趋势破坏
- 在 Generic 路径中增加退出规则检查层，使所有策略类型都能使用 ATR止损/止盈/移动止盈/固定止损
- 补齐 `atr_stop_exit_count` 和 `atr_trail_exit_count` 引擎级计数器

**Non-Goals:**
- 不修改退出规则的参数定义或前端 UI（已完备）
- 不实现用户可配置的退出优先级拖拽排序（仍为 TBD）
- 不修改配置编译逻辑（`_experiment_runner_api.py` 已正确传递参数）

## Decisions

### D1: 新退出优先级顺序

```
RISK_OFF_EXIT           (系统熔断)
ATR_STOP_LOSS           (ATR 止损 — 风控底线)
FIXED_STOP_LOSS         (固定止损 — 风控底线)
TREND_BREAK_EXIT        (趋势破坏)
TAKE_PROFIT             (止盈)
ATR_TRAIL_EXIT          (移动止盈)
TIME_EXIT               (持仓到期)
CROSS_DOWN / 信号反转    (信号退出)
```

**理由**：止损是硬性风控约束，当价格已跌穿止损线时，无论趋势是否已破坏，都应记录为止损退出。这使 reason_code 准确反映"为什么亏了钱"，而非"趋势也破了"。

### D2: Generic 路径退出规则 — 注入式检查

在 Generic 路径的日循环中，**策略产生信号之前**，先对所有持仓执行退出规则检查：

```
for each held symbol:
    compute ATR from history
    check ATR_STOP → FIXED_STOP → TAKE_PROFIT → ATR_TRAIL
    if triggered → prepend to sell_sigs with priority reason_code

strategy.generate_signals()  # 策略正常产生信号

merge: exit_rule_sells (high priority) + strategy_sells (dedup by symbol)
```

**关键决策**：
- 退出规则产生的 SELL 信号具有优先权。如果退出规则和策略同时产生同一个 symbol 的 SELL，使用退出规则的 reason_code。
- 退出规则检查需要 ATR 值：从 history 中逐 symbol 计算 14 日 ATR（与 SMA 路径使用 `feats.atr14` 等价，但 Generic 路径不使用 data_matrix/feature_matrix，需内联计算）。
- peak_close 追踪状态需在 Generic 路径中维护，与 SMA 路径一致。

### D3: 引擎级计数器补齐

在两条路径的模拟循环中：
- 声明 `atr_stop_exit_count = 0` 和 `atr_trail_exit_count = 0`
- 在 `reason == "ATR_STOP_LOSS"` 时 `atr_stop_exit_count += 1`
- 在 `reason == "ATR_TRAIL_EXIT"` 时 `atr_trail_exit_count += 1`
- 写入 metrics dict，传回顶层 API 响应

### D4: Generic 路径 ATR 计算方式

Generic 路径不使用 `build_ohlc_matrices_from_history` / `compute_feature_matrices` 矩阵化流程，而是逐日迭代。ATR 计算策略：

**方案**：在 Generic 路径启动时，对每个 symbol 预计算 ATR 序列（与 SMA 路径的 `feats.atr14` 逻辑一致），存为 `{symbol: {date: atr_value}}` 字典。日循环中直接查表。

**理由**：避免在热循环中重复计算 rolling ATR，一次性预计算性能更优。

## Risks / Trade-offs

- **Generic 路径 ATR 预计算内存**：对 N 个 symbol × T 天，存储 N×T 个 float。在典型 universe（<500 symbols, <2000 天）下约 8MB，可接受。
- **退出优先级硬编码**：暂不支持用户自定义排序（前端已有 TBD 占位），后续可通过 exit_priority 配置项实现。
- **策略自身的止损逻辑**：某些 Generic 策略（如 RSI_REVERSAL 的 `mr_stop_loss_pct`）可能有自己的内部止损。引擎级退出规则不冲突——引擎先检查，策略再产生信号，dedup 时引擎优先。
