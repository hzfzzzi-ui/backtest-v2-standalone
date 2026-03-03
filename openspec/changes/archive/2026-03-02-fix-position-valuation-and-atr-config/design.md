## Context

引擎存在两个独立 bug：

**Bug 1 — 持仓估值虚假跳变**

`_build_price_indices(raw_df)` 只构建一套价格索引（不复权），同时用于成交填充和 NAV 估值。当股票发生除权除息时，raw close 突变但 `positions[sym]`（股数）不变，`compute_nav_snapshot()` 算出的 `market_value = qty × raw_close` 出现虚假暴跌。

```
compute_nav_snapshot (portfolio_builder.py:47-49)
    for sym, qty in positions.items():
        c = close_idx.get((day, sym), 0.0)   ← 不复权 close
        v = c * qty                           ← 股数未随分拆调整
```

同时 `mapping.py:118` 对 NULL adj_factor 用 `fillna(1.0)` 处理，导致最新交易日（adj_factor 数据滞后1天）hfq 价格断崖。

**Bug 2 — atr_stop_k 配置黑洞**

`loader.py:76-77` 显式过滤 exit 区的 `atr_stop_k`，`ExitConfig` 没有该字段。引擎从 `RiskBudgetConfig.atr_stop_k` 读值（默认 2.0），用户通过前端修改的值无效。

## Goals / Non-Goals

**Goals:**
- 持仓估值使用后复权价格，消除除权除息引起的 NAV 虚假跳变
- adj_factor NULL 改为按股票前向填充
- atr_stop_k 配置完整传递到引擎

**Non-Goals:**
- 不改变成交执行价格来源（仍用不复权价）
- 不改变信号计算价格来源（仍用 hfq 复权价）
- 不调整前端 UI（无新增控件）
- 不处理除权除息时的股数调整（采用方案 B：hfq 估值，而非方案 A：调股数）

## Decisions

### D1: 四索引 + 持仓股数调整方案

`_build_price_indices` 改为接收两套 DataFrame，返回四个索引：

```python
def _build_price_indices(
    raw_df: pd.DataFrame,
    hfq_df: pd.DataFrame | None = None,
) -> tuple[dict, dict, dict, dict]:  # open_idx, raw_close_idx, hfq_close_idx, adj_factor_idx
```

- `open_idx` — 从 raw_df 构建，用于次日开盘成交
- `raw_close_idx` — 从 raw_df 构建，用于成交价和 trades 记录
- `hfq_close_idx` — 从 hfq_df 构建，用于 NAV 估值（归一化后）
- `adj_factor_idx` — 从 raw_df 构建，用于除权除息检测和持仓调整

**实现发现**：单纯用 hfq 估值不够 — cash 在 raw 空间而 hfq 价格在调整空间，混合导致 NAV 膨胀。最终采用双重修复：
1. **持仓股数调整**：每日循环检测 adj_factor 变化，按比例调整 qty/avg_cost
2. **归一化估值**：`market_value = qty × hfq_close / entry_adj_factor`，保证与 raw 空间一致

### D2: close_idx 分流

调用路径分为两套：

| 用途 | 使用的索引 | 位置 |
|------|-----------|------|
| 成交填充 | `open_idx` (raw) | `_process_pending_fills` |
| 均成本计算 | `raw_close_idx` (raw) | `_process_pending_fills` 中的 fill_px |
| NAV 估值 | `hfq_close_idx` (hfq) + `position_entry_adj` | `compute_nav_snapshot` |
| ATR 退出检查 | `raw_close_idx` (raw) | `evaluate_engine_exits` 中 cclose 参数 |
| 除权检测 | `adj_factor_idx` | `_run_unified_loop` 日循环开头 |

关键修改点：
- `_run_unified_loop` 的 `close_idx` 参数拆为 `raw_close_idx` + `hfq_close_idx`
- `compute_nav_snapshot` 的 `close_idx` 参数改用 `hfq_close_idx`
- `_process_pending_fills` 保持使用 `open_idx`（raw）
- 退出规则中的价格比较（ATR止损、固定止损）仍用 raw close（因为 avg_cost 也是 raw）

### D3: adj_factor 前向填充

`mapping.py:118` 改为：

```python
out["adj_factor"] = pd.to_numeric(out["adj_factor"], errors="coerce")
out["adj_factor"] = out.groupby("symbol")["adj_factor"].ffill().fillna(1.0)
```

先 ffill（前向填充），再 fillna(1.0) 兜底。覆盖场景：
- 最新日数据滞后（96%的股票受影响）→ ffill 继承前日值
- 新上市第一天无历史 → 兜底 1.0

### D4: atr_stop_k 配置修复

三处修改：

1. `ExitConfig` 新增字段 `atr_stop_k: float = 2.0`
2. `loader.py:76-77` 移除 `("atr_stop_k",)` 过滤
3. 引擎三条路径（SMA/Generic/RegimeRouter）中，`atr_stop_k` 优先从 `exit_cfg.atr_stop_k` 取值，回退到 `risk_budget_cfg.atr_stop_k`

```python
_atr_k = _ec.atr_stop_k if _ec.atr_stop_k != 2.0 else _rb.atr_stop_k
```

不改动 `RiskBudgetConfig.atr_stop_k`（保留向后兼容），但新的配置路径优先走 `ExitConfig`。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| hfq 估值会让 trades.csv 中的 P&L 与 NAV 变动不完全对应（trades 用 raw 价，NAV 用 hfq 价） | 这是正确行为 — trades 反映实际成交价，NAV 反映真实资产价值。两者在无除权事件时一致。 |
| 修复后所有历史回测结果会变 | 旧结果本身就是错的（虚假回撤），变化是修正方向。 |
| ffill adj_factor 假设"数据只是滞后一天" | 如果某股票真的停止更新 adj_factor（退市等），ffill 会一直用最后已知值，这比 1.0 更合理。 |
| atr_stop_k 默认值判断 `!= 2.0` 有边界问题 | 如果用户确实想设 2.0，两个来源都是 2.0 也没影响。只有用户改了非 2.0 值时才需要区分优先级。 |
