## Context

Phases 1-3 已统一 daily_row schema、提取共享原语（fills, price indices, engine exits）。两路径仍保留完整的日循环代码（SMA ~560 行循环 + Generic ~310 行循环），其中以下步骤结构完全相同：
- 订单成交 (`_process_pending_fills`)
- NAV/回撤计算 (`compute_nav_snapshot`)
- Drawdown breaker
- 订单计划 (`build_rebalance_orders`)
- Daily row 记录（38 列 + 诊断回填）
- 订单入队 + 审计

唯一差异在**信号生成**（卖出信号 + 买入信号 + 诊断计数）。

## Goals / Non-Goals

**Goals:**
- 定义 `SignalProvider` Protocol 和 `DaySignals`/`DayContext` 数据类
- 实现 `SMASignalProvider` 和 `GenericSignalProvider`
- 提取统一引擎循环 `_run_unified_loop()`
- 删除 `_run_vector_portfolio_backtest_generic_signals()` 函数
- SMA 和 Generic 回测结果与重构前完全一致

**Non-Goals:**
- 不改变信号逻辑或退出规则行为
- 不优化性能（Phase 5）
- 不添加新的 SignalProvider 类型（未来扩展）

## Decisions

### D1: 文件组织

| 文件 | 内容 | 预计行数 |
|-----|------|---------|
| `signal_provider.py` | Protocol + DayContext + DaySignals + ExitCounts + `_evaluate_engine_exits()` | ~120 |
| `sma_signal_provider.py` | SMASignalProvider（矩阵预计算 + 逐日信号） | ~450 |
| `generic_signal_provider.py` | GenericSignalProvider（策略调用 + 引擎退出） + `_build_multifactor_and_fast_gate()` | ~300 |
| `portfolio_simulator_strict.py` | 入口 + `_run_unified_loop()` + 共享函数（`_build_price_indices`, `_process_pending_fills`） | ~600 |

ExitCounts 和 `_evaluate_engine_exits()` 从 `portfolio_simulator_strict.py` 移到 `signal_provider.py`，因为它们属于信号提供者层。

### D2: SignalProvider 协议

```python
class SignalProvider(Protocol):
    def precompute(self, *, history: pd.DataFrame, benchmark: pd.DataFrame,
                   raw_history: pd.DataFrame | None, trading_days: list[date],
                   strategy: Any, ...) -> None: ...

    def day_signals(self, day: date, day_idx: int, ctx: DayContext) -> DaySignals: ...

    # Fill hooks — 引擎在处理订单成交时使用
    extra_clear_dicts: list[dict]
    last_sell_day: dict[str, date] | None
    entry_day: dict[str, date]
    entry_day_overwrite: bool
    peak_state_on_buy: dict[str, float] | None
```

`precompute()` 负责一次性预计算（矩阵构建、regime 查询等），由入口函数在统一循环前调用。

`day_signals()` 每日调用，接收 DayContext（引擎状态只读快照），返回 DaySignals。

Fill hooks 是 provider 创建的可变字典，统一循环传递给 `_process_pending_fills()`。Provider 在 `day_signals()` 中也使用这些字典（如 entry_day 用于 TIME_EXIT），形成共享可变状态。

### D3: DayContext（引擎 → 信号提供者的只读快照）

```python
@dataclass(slots=True)
class DayContext:
    positions: dict[str, int]
    position_avg_cost: dict[str, float]
    cash: float
    nav: float
    base_order_value: float
    max_positions: int
    close_idx: dict[tuple[date, str], float]
    open_idx: dict[tuple[date, str], float]
    next_day: date | None
```

注意：positions/position_avg_cost 是引用而非拷贝（性能），provider MUST NOT 修改。

### D4: DaySignals（信号提供者 → 引擎）

```python
@dataclass(slots=True)
class DaySignals:
    sell_signals: list[Signal]
    buy_signals: list[Signal]
    strength_map: dict[str, float]
    mf_score_map: dict[str, float]
    mf_gate_on_today: bool
    strong_risk_on: bool
    exit_counts: ExitCounts
    diagnostics: dict[str, Any]
```

`diagnostics` 字典包含提供者特有的诊断数据，统一循环按 key 读取并回填到 daily_row。已知 keys：
- `positions_before_sell`, `raw_buy_signal_count`, `buy_candidate_count`, `after_held_filter_count`
- `slope_block_today`, `continuity_block_today` (SMA only, default 0)
- `base_trend_on_rate`, `quality_trend_on_rate` (SMA only, default 0.0)
- `diag_reason_counts` (SMA: 详细阻断原因计数；Generic: 从策略信号推断)

### D5: 统一循环与 Provider 的状态交互

```
┌─────────────────────────────────────────────────┐
│                  Unified Loop                    │
│                                                  │
│  owns: cash, peak_nav, pending, trade_rows,     │
│        daily_rows, candidate_rows, _breaker     │
│                                                  │
│  borrows from provider:                          │
│    extra_clear_dicts, last_sell_day, entry_day,  │
│    peak_state_on_buy → passed to fills           │
│                                                  │
│  ┌─────────────┐    DayContext    ┌────────────┐ │
│  │   Engine     │ ──────────────▶ │  Provider  │ │
│  │   State      │ ◀────────────── │  State     │ │
│  │              │    DaySignals   │            │ │
│  └─────────────┘                 └────────────┘ │
│                                                  │
│  Provider owns: signal matrices, regime arrays,  │
│    peak_state(exit), break_streak, feature mats, │
│    strategy object, ATR lookup, mf_fast gate     │
└─────────────────────────────────────────────────┘
```

### D6: `_build_multifactor_and_fast_gate()` 归属

此函数仅 Generic 路径使用，移动到 `generic_signal_provider.py`。

### D7: 入口函数路由逻辑

`run_vector_portfolio_backtest_strict()` 保持为唯一入口函数。原有的 `is_sma_strategy` 判断逻辑保留，用于选择 SMASignalProvider 或 GenericSignalProvider。

SMA 路径的大量参数提取（strategy 属性 → 局部变量）移入 SMASignalProvider.precompute()。

## Risks / Trade-offs

- **[风险] 重构规模大，回归风险高** → 缓解：逐步实施，每步验证数值一致
- **[风险] 共享可变状态（entry_day, peak_state 等）跨引擎和 provider** → 这是现有模式的延续，不引入新风险
- **[风险] SMA provider 行数可能超 400** → 可接受，因为它封装了完整的 SMA 信号逻辑（矩阵预计算 + sell/buy 生成 + 诊断）
- **[权衡] 引入 3 个新文件** → 为了满足文件大小限制（<800 行），必须拆分
