## Why

引擎存在两个已确认 bug，导致回测结果不可靠：

1. **持仓估值用不复权价但不调整股数**：`compute_nav_snapshot()` 使用 raw close × 原始股数计算市值。当股票发生送股/转增（如 sz002252 的 10转10），raw close 腰斩但股数未翻倍，引擎记录为虚假亏损 ~50%。数据库中有 7 次 adj_factor 跳变的股票（如 sz002252），每次都产生错误 NAV 波动，污染收益率、最大回撤、夏普等所有指标。
2. **atr_stop_k 配置静默丢弃**：`loader.py:76-77` 显式过滤掉 exit 区的 `atr_stop_k` 字段，用户在前端修改 ATR 止损倍数不生效。引擎实际从 `risk_budget.atr_stop_k` 读值，形成配置"黑洞"。

## What Changes

- **持仓估值改用后复权价格**：`_build_price_indices` 接收两套 DataFrame（raw 用于成交填充，hfq 用于 NAV 估值），`compute_nav_snapshot` 使用 hfq close_idx 计算市值，消除除权除息引起的虚假 NAV 跳变
- **adj_factor NULL 前向填充**：`mapping.py` 中 NULL adj_factor 改为按股票前向填充（`groupby.ffill()`），兜底才用 1.0，避免最新交易日数据延迟导致的价格断崖
- **移除 atr_stop_k 过滤**：`loader.py` 停止过滤 exit 区的 `atr_stop_k`，让用户配置正确传递到 `ExitConfig`
- **统一 atr_stop_k 来源**：引擎优先从 `exit.atr_stop_k` 读值，`risk_budget.atr_stop_k` 作为兼容回退

## Capabilities

### New Capabilities

（无新增能力）

### Modified Capabilities

- `price-adjustment`: 新增"持仓估值使用后复权价格"和"adj_factor NULL 前向填充"要求，修正现有"成交执行使用不复权价格"的范围（成交仍用不复权，但估值改用后复权）
- `pipeline-data-integrity`: 新增"atr_stop_k 配置不被静默丢弃"要求，确保 exit 区参数完整传递

## Impact

- **引擎核心**：`portfolio_simulator_strict.py`（估值路径）、`portfolio_builder.py`（`compute_nav_snapshot` 签名变更）
- **数据层**：`mapping.py`（adj_factor 填充逻辑）
- **配置加载**：`loader.py`（移除 atr_stop_k 过滤）
- **回测结果**：修复后所有历史回测的收益率/回撤/夏普会与之前不同（尤其是持仓期间经历除权事件的交易）
- **向后兼容**：无 API 变更，无前端变更，纯后端修复
