## Context

`portfolio_simulator_strict.py` 包含两条引擎路径，各自构造 `daily_row`：
- **SMA 路径**（L477-516 初始化，L866-932 补充）：输出 ~42 个字段，含完整的卖出/买入漏斗
- **Generic 路径**（L1435-1456 初始化，L1612-1659 补充）：输出 ~25 个字段，缺失卖出漏斗和大部分买入漏斗

这是 5 阶段引擎统一重构的 Phase 1，目标是在不改变引擎循环结构的前提下，将 daily_row schema 归一化。

## Goals / Non-Goals

**Goals:**
- 删除 SMA 路径 4 组冗余字段
- Generic 路径补齐 sell funnel（3 个字段）和 buy funnel（4 个字段）的实际计数
- 两条路径的初始化 dict 字段集对齐
- `_compute_metrics()` 适配字段名变更

**Non-Goals:**
- 不提取公共函数（Phase 2 的任务）
- 不改变引擎循环逻辑或信号处理流程
- 不统一退出规则（Phase 3）
- 不修改前端代码（前端不直接读取被删除的冗余字段）
- 不修改策略诊断字段（保持各路径按需输出）

## Decisions

### D1: 冗余字段直接删除而非 alias

**选择**：删除冗余字段代码，更新 `_compute_metrics()` 中的引用

**替代方案**：保留冗余字段但标记 deprecated → 增加维护负担，违背清理目标

**理由**：这些字段完全同值（同一行代码赋相同变量），不存在语义差异。`_compute_metrics()` 是唯一内部消费者，可一次性更新。

### D2: Generic 路径漏斗计数从 `debug_plan` 和信号列表提取

**选择**：利用已有的 `build_rebalance_orders()` 返回的 `debug_plan` dict，加上 `sell_sigs`/`buy_sigs` 列表长度

**实现**：
- `positions_before_sell`：在卖出信号处理前 `sum(1 for q in positions.values() if q > 0)`
- `sells_executed_count`：`len(sell_sigs)`（过滤 BLOCKED 后）
- `positions_after_sell`：`positions_before_sell - sells_executed_count`
- `raw_buy_signal_count`：策略返回的 BUY 信号总数（含 BLOCKED）
- `after_held_filter_count`：`raw_buy_signal_count - held_filter_blocked`
- `after_slot_filter_count`：`min(after_held_filter_count, buy_slots)`
- `after_cash_lot_count`：`debug_plan["selected_symbols"]` 的长度（实际下单数）

**理由**：不需要新增函数或修改 `build_rebalance_orders`，所有数据在 Generic 路径中已可获取。

### D3: daily_row 初始化统一为完整 schema

**选择**：两条路径的 `daily_rows.append({...})` 使用相同的完整字段集合（含所有漏斗字段），默认值为 0

**理由**：确保 `pd.DataFrame(daily_rows)` 生成的列一致，避免因缺失列导致下游 KeyError。后续 Phase 4 合并循环时可直接复用。

## Risks / Trade-offs

- **[风险] `_compute_metrics()` 引用已删字段** → 需全面检查该函数，搜索 4 个被删字段名；缓解：grep 确认所有引用点
- **[风险] Generic 路径 `raw_buy_signal_count` 统计口径与 SMA 不完全对齐** → SMA 的 `raw_buy_signal_count` 来自矩阵 `np.sum(buy_base[i])`，Generic 来自策略返回的信号列表；缓解：这是信号源差异而非 schema 问题，Phase 4 统一信号协议后自然对齐
- **[权衡] 策略诊断字段不强制对齐** → 接受两路径诊断字段不完全一致，以保持灵活性；代价是 daily_df 存在 NaN 列（对 SMA 特有字段，Generic 路径产出行填 NaN）
