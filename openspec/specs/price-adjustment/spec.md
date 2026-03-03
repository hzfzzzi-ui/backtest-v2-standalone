## ADDED Requirements

### Requirement: 数据层加载 adj_factor

`pg_provider.load_ohlcv_daily()` 必须（SHALL）在返回的 DataFrame 中包含 `adj_factor` 列。当数据库中 `adj_factor` 为 NULL 时，先按股票前向填充（`groupby("symbol").ffill()`），兜底才填 1.0。

#### Scenario: 正常加载含 adj_factor 的行情数据
- **WHEN** 调用 `load_ohlcv_daily(symbols, start, end, source)` 加载一组股票
- **THEN** 返回的 DataFrame 包含 `adj_factor` 列，所有值为正浮点数

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

### Requirement: 复权价格转换函数

系统必须（SHALL）提供一个纯函数 `apply_price_adjustment(history, mode)`，接收包含 adj_factor 列的 OHLCV DataFrame 和复权模式字符串，返回一个新的 DataFrame，其中 OHLCV 价格列已按指定模式转换。原始 DataFrame 不得被修改（immutable）。

转换规则：
- `"hfq"`（后复权）：`adjusted_price = raw_price × adj_factor`
- `"qfq"`（前复权）：`adjusted_price = raw_price × (adj_factor / latest_adj_factor_per_symbol)`
- `"none"`（不复权）：价格不变，原样返回

仅转换 `open`, `high`, `low`, `close` 四列。`volume`, `adj_factor` 等其他列保持不变。

#### Scenario: 后复权模式转换
- **WHEN** 调用 `apply_price_adjustment(history, "hfq")`，某股票某日 `close=100.0`, `adj_factor=5.0`
- **THEN** 返回 DataFrame 中该行 `close=500.0`，`adj_factor` 列仍为 `5.0`

#### Scenario: 前复权模式转换
- **WHEN** 调用 `apply_price_adjustment(history, "qfq")`，某股票最新日 `adj_factor=10.0`，历史某日 `close=100.0`, `adj_factor=5.0`
- **THEN** 返回 DataFrame 中该历史行 `close=50.0`（= 100 × 5/10）

#### Scenario: 不复权模式
- **WHEN** 调用 `apply_price_adjustment(history, "none")`
- **THEN** 返回 DataFrame 中所有价格列与输入相同

#### Scenario: 输入 DataFrame 不可变
- **WHEN** 调用 `apply_price_adjustment(history, "hfq")`
- **THEN** 原始 `history` DataFrame 的任何列均未被修改

---

### Requirement: 信号计算使用复权价格

引擎的信号计算路径（均线、ATR、强度排名、多因子评分等技术指标）必须（SHALL）使用经过复权转换后的价格序列。

#### Scenario: 除权日前后信号连续性
- **WHEN** 某股票在日期 D 发生除权除息（如10送5），复权模式为 `"hfq"`
- **THEN** 日期 D-1 和 D 的复权收盘价序列连续（无大幅跳空），均线指标平滑过渡

#### Scenario: 复权模式影响信号生成
- **WHEN** 同一组数据分别用 `"hfq"` 和 `"none"` 模式运行回测
- **THEN** 两次运行的信号序列可能不同（除权除息事件期间差异更大）

---

### Requirement: 成交执行使用不复权价格

无论用户选择哪种复权模式，成交执行路径（计算成交金额、扣减现金、计算持仓市值）必须（SHALL）使用不复权（raw）价格。

#### Scenario: 后复权模式下的成交价格
- **WHEN** 复权模式为 `"hfq"`，某股票次日开盘不复权价=15.00，adj_factor=3.0
- **THEN** 买入成交价为 15.00（不复权），而非 45.00（后复权价）

#### Scenario: 成交记录中的价格字段
- **WHEN** 一笔交易完成
- **THEN** trades 表中的 `price` 字段为不复权价格

---

### Requirement: 前端价格口径控件接入

前端 `wbPriceAdj` 控件的选中值必须（SHALL）通过 `buildConfigDraft()` → `runPayloadFromDraft()` → API 请求传递到后端，最终影响引擎的复权行为。

#### Scenario: 用户选择后复权
- **WHEN** 用户在前端点击"后复权"按钮
- **THEN** `buildConfigDraft()` 返回的对象中 `universe.price_adj = "hfq"`
- **AND** API 请求 payload 中包含 `price_adj: "hfq"`

#### Scenario: 默认值
- **WHEN** 用户未修改价格口径控件（默认状态）
- **THEN** 使用默认值 `"hfq"`（后复权，量化回测最佳实践）

---

### Requirement: 产物可观测性

每次回测的 `run_meta` 必须（SHALL）记录实际使用的复权模式。

#### Scenario: run_meta 包含复权模式
- **WHEN** 回测完成
- **THEN** `run_meta.json` 中包含字段 `price_adj_mode`，值为 `"hfq"` / `"qfq"` / `"none"` 之一

#### Scenario: 产物中 adj_factor 统计
- **WHEN** 回测完成
- **THEN** `run_meta.json` 中包含 `adj_factor_stats`，记录 `min`, `max`, `null_count`，供用户验证数据质量

---

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
