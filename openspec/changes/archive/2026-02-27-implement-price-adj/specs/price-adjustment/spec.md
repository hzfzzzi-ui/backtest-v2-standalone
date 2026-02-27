## ADDED Requirements

### Requirement: 数据层加载 adj_factor

`pg_provider.load_ohlcv_daily()` 必须（SHALL）在返回的 DataFrame 中包含 `adj_factor` 列。当数据库中 `adj_factor` 为 NULL 时，必须填充为 `1.0`。

#### Scenario: 正常加载含 adj_factor 的行情数据
- **WHEN** 调用 `load_ohlcv_daily(symbols, start, end, source)` 加载一组股票
- **THEN** 返回的 DataFrame 包含 `adj_factor` 列，所有值为正浮点数

#### Scenario: adj_factor 为 NULL 时的默认值
- **WHEN** 数据库中某行的 `adj_factor` 为 NULL（如最新日期数据尚未补全）
- **THEN** 该行的 `adj_factor` 填充为 `1.0`

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
