## MODIFIED Requirements

### Requirement: adj_factor NULL 处理（修改）

原要求：NULL adj_factor 填充为 1.0。
新要求：NULL adj_factor 先按股票前向填充（`groupby("symbol").ffill()`），兜底才填 1.0。

#### Scenario: 最新交易日 adj_factor 数据滞后
- **WHEN** 某股票最新交易日 adj_factor 为 NULL，但前一交易日 adj_factor=24.839
- **THEN** 该行 adj_factor 填充为 24.839（前向填充），而非 1.0

#### Scenario: 新上市股票无历史 adj_factor
- **WHEN** 某股票所有行 adj_factor 均为 NULL
- **THEN** 所有行 adj_factor 填充为 1.0（兜底默认值）

#### Scenario: adj_factor 中间缺失
- **WHEN** 某股票日期序列中 adj_factor 出现间歇性 NULL
- **THEN** 每个 NULL 值从同股票前一个非 NULL 值前向填充

---

## ADDED Requirements

### Requirement: 持仓估值使用后复权价格

`compute_nav_snapshot()` 必须（SHALL）使用后复权（hfq）收盘价计算持仓市值和 NAV。成交执行路径仍使用不复权价格（不变）。

#### Scenario: 除权除息日 NAV 连续性
- **WHEN** 某股票在日期 D 发生 10转10（adj_factor 翻倍，raw close 减半）
- **AND** 引擎在日期 D 仍持有该股票
- **THEN** 日期 D-1 和 D 的 NAV 变动反映真实资产价值变化（±数个百分点），而非虚假暴跌（-50%）

#### Scenario: 无除权事件时行为不变
- **WHEN** 回测期间所有持仓股票无除权除息事件（adj_factor 恒定）
- **THEN** hfq 估值与 raw 估值结果完全一致

#### Scenario: 引擎入口传递 hfq 价格
- **WHEN** 调用 `run_portfolio_backtest(history=hfq_df, raw_history=raw_df, ...)`
- **THEN** `_build_price_indices` 必须从 `history`（hfq）构建估值用 close 索引
- **AND** 从 `raw_history`（不复权）构建成交用 open/close 索引

### Requirement: 双索引价格体系

`_build_price_indices` 必须（SHALL）同时构建不复权和后复权两套价格索引。

#### Scenario: 函数签名
- **WHEN** 调用 `_build_price_indices(raw_df, hfq_df)`
- **THEN** 返回 `(open_idx, raw_close_idx, hfq_close_idx)` 三个字典

#### Scenario: hfq_df 缺省时向后兼容
- **WHEN** 调用 `_build_price_indices(raw_df)` 不传 hfq_df
- **THEN** `hfq_close_idx` 等于 `raw_close_idx`（行为与修复前一致）
