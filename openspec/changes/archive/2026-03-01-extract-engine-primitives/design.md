## Context

Phase 1（daily-row-normalize）已完成，两路径的 daily_row schema 已对齐。现在着手提取两路径中结构相同的代码为共享函数。

经分析，4 个最初的提取候选中：
- `_process_pending_fills`：两路径代码 95% 相同，差异仅在清仓时清理的状态字典数量（SMA: 6个, Generic: 3个），通过参数化解决
- `_build_price_indices`：两路径代码 100% 相同，直接提取
- `_build_daily_nav_row`：两路径结构相似但 daily_row 初始化字段已在 Phase 1 对齐，提取的价值在于 Phase 4 合并循环时才体现，此阶段暂缓
- `_build_benchmark_regime`：SMA 用 NumPy 数组（vectorized），Generic 用 dict（scalar），结构差异大，属于 Phase 4 统一信号协议的范畴

因此 Phase 2 聚焦提取前两个：`_process_pending_fills` 和 `_build_price_indices`。

## Goals / Non-Goals

**Goals:**
- 提取 `_process_pending_fills()` 消除订单成交逻辑的重复（~80行 × 2份）
- 提取 `_build_price_indices()` 消除价格索引构建的重复（~15行 × 2份）
- 统一清仓时的状态字典清理（SMA 额外清理 `peak_close_state`、`_raw_peak_state`、`break_streak_state`、`last_sell_day`、`entry_day`；Generic 额外清理 `_peak_close_state2`、`_entry_day2`）
- 回测结果与提取前完全一致（数值不变）

**Non-Goals:**
- 不提取 NAV 行构建（Phase 4）
- 不提取 benchmark regime 计算（Phase 4）
- 不改变成交逻辑或成本模型
- 不创建新文件（函数定义在同文件内）

## Decisions

### D1: `_process_pending_fills` 签名设计

```python
def _process_pending_fills(
    orders: list[dict[str, Any]],
    day: date,
    open_idx: dict[tuple[date, str], float],
    positions: dict[str, int],
    position_avg_cost: dict[str, float],
    cash: float,
    cost_slip_bps: float,
    cost_comm_rate: float,
    cost_comm_min: float,
    cost_stamp_rate: float,
    close_idx: dict[tuple[date, str], float],
    extra_state_dicts_on_clear: list[dict[str, Any]] | None = None,
    last_sell_day: dict[str, date] | None = None,
    entry_day_on_buy: dict[str, date] | None = None,
) -> tuple[float, float, list[dict[str, Any]]]:
    """返回 (updated_cash, traded_value, new_trade_rows)"""
```

**关键设计点：**
- `extra_state_dicts_on_clear`：清仓时额外需要清理的状态字典列表。SMA 传入 `[peak_close_state, _raw_peak_state, break_streak_state]`，Generic 传入 `[_peak_close_state2]`
- `last_sell_day`：SMA 路径需要在清仓时记录最后卖出日（用于 cooldown），通过可选参数传入
- `entry_day_on_buy`：SMA 路径在买入时记录 entry_day（用于 min_hold / time_exit）；Generic 路径条件不同（仅首次设置）。通过可选参数传入，None 则跳过
- 函数直接修改 `positions`、`position_avg_cost`（mutable dict 原地更新），与现有行为一致
- `close_idx` 用于 BUY 成交时初始化 peak_close_state（SMA 特有），通过 extra_state_dicts_on_clear 中的 dict.setdefault 处理

**替代方案：** 返回完整的新字典（不可变风格）→ 需要大量拷贝，性能开销不值得（每日循环内调用）

### D2: Generic 路径 entry_day 差异处理

SMA 路径买入时：`entry_day[sym] = day`（无条件覆盖）
Generic 路径买入时：`if sym not in _entry_day2: _entry_day2[sym] = day`（仅首次设置）

**选择：** 增加 `entry_day_overwrite: bool = True` 参数。SMA 传 True（默认），Generic 传 False。

### D3: peak_close_state 初始化差异

SMA 路径买入时：`peak_close_state.setdefault(sym, close_idx.get((day, sym), px))`
Generic 路径无此操作。

**选择：** 通过 `extra_state_dicts_on_clear` 列表中包含 peak_close_state 来标识需要此操作。如果该 dict 在列表中，则买入时 setdefault。更简洁的方式：增加 `peak_state_on_buy: dict | None = None` 可选参数。

## Risks / Trade-offs

- **[风险] 函数签名参数过多** → 缓解：成本参数可以打包为 tuple，但当前阶段保持扁平以减少间接层
- **[风险] mutable dict 原地修改** → 这是既有模式的延续，不是新引入的风险；Phase 4 可以重新审视
- **[权衡] 不提取 NAV 行和 benchmark regime** → 接受在 Phase 2 不处理，保持每阶段变更范围可控
