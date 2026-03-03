## Why

`portfolio_simulator_strict.py` 中 SMA 路径和 Generic 路径各自内联了相同的订单成交逻辑（~80行/份）和价格索引构建逻辑（~15行/份），代码重复率高达 95%。当需要修改成交逻辑（如调整滑点、佣金）或价格索引（如增加 high/low 索引）时，必须同时修改两处，容易产生不一致。此外，SMA 路径在卖出清仓时清理 6 个状态字典，Generic 路径仅清理 3 个——这类不一致是双路径维护的典型风险。

这是引擎统一重构的 Phase 2，目标是将两条路径中结构相同的原语提取为共享函数，为 Phase 3（统一退出规则）和 Phase 4（信号提供者协议）铺路。

## What Changes

- **提取 `_process_pending_fills()`**：将两路径的订单成交循环（含滑点、佣金、印花税、仓位更新、trade_row 构建）提取为共享函数
- **提取 `_build_price_indices()`**：将两路径的原始价格索引构建（open_idx / close_idx dict 从 DataFrame 迭代构建）提取为共享函数
- **统一清仓状态清理**：SMA 路径清仓时清理 `peak_close_state`、`_raw_peak_state`、`break_streak_state`、`last_sell_day`、`entry_day`、`position_avg_cost`；Generic 路径仅清理 `_peak_close_state2`、`_entry_day2`、`position_avg_cost`。提取后通过传入可选的状态字典列表实现统一

## Capabilities

### New Capabilities
- `engine-shared-primitives`：定义引擎公共原语函数的接口和行为契约

### Modified Capabilities
（无现有 spec 级别的需求变更）

## Impact

- **后端**：`portfolio_simulator_strict.py`（两条路径的成交和价格索引代码替换为函数调用）
- **新增函数位于同文件**：不创建新文件，函数定义在模块顶部（`compute_nav_snapshot` 附近）
- **风险**：低——纯重构，不改变计算逻辑，可通过对比回测结果验证
