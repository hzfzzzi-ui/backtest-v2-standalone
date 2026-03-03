## Why

`portfolio_simulator_strict.py` 中 SMA 路径和 Generic 路径各自维护一套 `daily_row` 字段，字段集合不一致：SMA 路径输出 ~42 个字段，Generic 路径仅输出 ~25 个，导致同一套前端和指标计算逻辑面对两种不同的 schema。此外 SMA 路径存在 4 组冗余字段（同值不同名），增加维护负担。需要在引擎统一重构（Phase 4）之前先将 daily_row 归一化，为后续提取公共原语和统一引擎循环打好基础。

## What Changes

- **删除冗余字段**：移除 SMA 路径中 4 组同值冗余字段：
  - `positions_count_end_of_day`（与 `positions_count` 同值）
  - `candidates_after_held_filter_count`（与 `after_held_filter_count` 同值）
  - `buy_slots_after_sell`、`buy_slots_calculated`（与 `buy_slots_before_buy` 同值）
- **定义统一漏斗 schema**：将 daily_row 字段按层级分类，两条路径输出一致的字段集合：
  - **引擎核心层**（Engine Core）：date, nav, cash, positions_count, daily_return, drawdown, gross_exposure, turnover_pct, top5_positions_json
  - **卖出漏斗**（Sell Funnel）：positions_before_sell → sells_executed_count → positions_after_sell
  - **买入漏斗**（Buy Funnel）：raw_buy_signal_count → after_held_filter_count → after_slot_filter_count → after_cash_lot_count
  - **买入槽位**（Buy Slots）：buy_slots_before_buy
  - **订单规划**（Order Planner）：candidates_count, selected_count, sorting_triggered
  - **策略诊断**（Strategy Diagnostics）：mean_order_value_scale, weak/strong_trend_buy_rate, mf_* 系列, strong_risk_on 等
- **Generic 路径补齐漏斗字段**：Generic 路径补充实际的 sell funnel 和 buy funnel 计数（目前缺失或写 0）
- **更新下游消费者**：`_compute_metrics()` 中引用冗余字段名的地方同步更新

## Capabilities

### New Capabilities
- `daily-funnel-schema`：定义 daily_row 的统一漏斗输出 schema，确保两条引擎路径输出一致的信号漏斗计数字段

### Modified Capabilities

（无现有 spec 级别的需求变更）

## Impact

- **后端**：`portfolio_simulator_strict.py`（两条路径的 daily_row 构造）、`portfolio_builder.py`（`_compute_metrics` 若引用冗余字段）
- **前端**：`backtest_v2.js` 不直接读取被删除的字段（仅通过 perf.json 间接消费），但需验证无硬编码引用
- **产物协议**：`portfolio_daily.csv` 列名变化（删除冗余列、新增 Generic 路径缺失列）
- **风险**：低——仅删除同值冗余字段和补齐缺失字段，不改变计算逻辑
