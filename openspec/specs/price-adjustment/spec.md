# price-adjustment Specification

## Purpose
定义复权因子加载、价格口径转换、成交执行与持仓估值的正式合同，确保除权除息不会污染信号与 NAV。

## Requirements

### Requirement: 数据层加载 adj_factor

`pg_provider.load_ohlcv_daily()` SHALL 在返回的 DataFrame 中包含 `adj_factor` 列。当数据库中 `adj_factor` 为 NULL 时，先按股票前向填充（`groupby("symbol").ffill()`），兜底才填 `1.0`。

#### Scenario: 正常加载含 adj_factor 的行情数据
- **WHEN** 调用 `load_ohlcv_daily(symbols, start, end, source)` 加载一组股票
- **THEN** 返回的 DataFrame 包含 `adj_factor` 列，所有值为正浮点数

#### Scenario: 最新交易日 adj_factor 数据滞后
- **WHEN** 某股票最新交易日 `adj_factor` 为 NULL，但前一交易日 `adj_factor=24.839`
- **THEN** 该行 `adj_factor` 填充为 `24.839`（前向填充），而非 `1.0`

#### Scenario: 新上市股票无历史 adj_factor
- **WHEN** 某股票所有行 `adj_factor` 均为 NULL
- **THEN** 所有行 `adj_factor` 填充为 `1.0`（兜底默认值）

#### Scenario: adj_factor 中间缺失
- **WHEN** 某股票日期序列中 `adj_factor` 出现间歇性 NULL
- **THEN** 每个 NULL 值从同股票前一个非 NULL 值前向填充

#### Scenario: 原始 adj_factor 缺口需要正式修复入口
- **WHEN** `pams_ohlcv_daily` 在给定日期范围内存在 `market='CN_A' AND adj_factor IS NULL` 的记录
- **THEN** 系统 MUST 提供正式 repair 模式，只重抓该范围内存在缺口的交易日
- **THEN** 该模式 SHALL 复用正式的 `update_pams_ohlcv_daily` 抓取与 upsert 链路，而不是另造第二套写库逻辑

#### Scenario: repair 模式返回修复后完整性审计
- **WHEN** repair 模式执行完成
- **THEN** summary MUST 记录修复前命中的缺口交易日列表
- **THEN** summary MUST 记录修复后仍存在缺口的交易日列表与剩余缺口行数
- **THEN** summary MUST 提供布尔完整性结果，供同步服务与运维诊断消费

#### Scenario: 日常同步后的 adj_factor 缺口不得静默成功
- **WHEN** 正式日常同步已追到目标交易日，但本次覆盖的交易日仍存在 `adj_factor IS NULL` 的 `CN_A` 记录
- **THEN** 同步结果 SHALL 被判定为失败
- **THEN** 系统 SHALL NOT 仅因“最新交易日已追平”而把该次同步记为成功

### Requirement: 复权价格转换函数

系统 SHALL 提供一个纯函数 `apply_price_adjustment(history, mode)`，接收包含 `adj_factor` 列的 OHLCV DataFrame 和复权模式字符串，返回一个新的 DataFrame，其中 OHLCV 价格列已按指定模式转换。原始 DataFrame SHALL 保持不变。

转换规则：
- `"hfq"`：`adjusted_price = raw_price × adj_factor`
- `"qfq"`：`adjusted_price = raw_price × (adj_factor / latest_adj_factor_per_symbol)`
- `"none"`：价格不变，原样返回

仅转换 `open`、`high`、`low`、`close` 四列。`volume`、`adj_factor` 等其他列保持不变。

#### Scenario: 后复权模式转换
- **WHEN** 调用 `apply_price_adjustment(history, "hfq")`，某股票某日 `close=100.0`, `adj_factor=5.0`
- **THEN** 返回 DataFrame 中该行 `close=500.0`，`adj_factor` 列仍为 `5.0`

#### Scenario: 前复权模式转换
- **WHEN** 调用 `apply_price_adjustment(history, "qfq")`，某股票最新日 `adj_factor=10.0`，历史某日 `close=100.0`, `adj_factor=5.0`
- **THEN** 返回 DataFrame 中该历史行 `close=50.0`

#### Scenario: 不复权模式
- **WHEN** 调用 `apply_price_adjustment(history, "none")`
- **THEN** 返回 DataFrame 中所有价格列与输入相同

#### Scenario: 输入 DataFrame 不可变
- **WHEN** 调用 `apply_price_adjustment(history, "hfq")`
- **THEN** 原始 `history` DataFrame 的任何列均未被修改

### Requirement: 信号计算使用复权价格

引擎的信号计算路径 SHALL 使用经过复权转换后的价格序列，包括均线、ATR、强度排名和多因子评分等技术指标。

#### Scenario: 除权日前后信号连续性
- **WHEN** 某股票在日期 D 发生除权除息，复权模式为 `"hfq"`
- **THEN** 日期 `D-1` 和 `D` 的复权收盘价序列连续，均线指标平滑过渡

#### Scenario: 复权模式影响信号生成
- **WHEN** 同一组数据分别用 `"hfq"` 和 `"none"` 模式运行回测
- **THEN** 两次运行的信号序列 MAY 不同

### Requirement: 成交执行使用不复权价格

无论用户选择哪种复权模式，成交执行路径 SHALL 使用不复权价格计算成交金额、扣减现金和记录成交价格。

#### Scenario: 后复权模式下的成交价格
- **WHEN** 复权模式为 `"hfq"`，某股票次日开盘不复权价为 `15.00`
- **THEN** 买入成交价为 `15.00`，而非后复权价

#### Scenario: 成交记录中的价格字段
- **WHEN** 一笔交易完成
- **THEN** trades 表中的 `price` 字段为不复权价格

### Requirement: 前端价格口径控件接入

前端 `wbPriceAdj` 控件的选中值 SHALL 通过 `buildConfigDraft()`、`runPayloadFromDraft()` 和 API 请求传递到后端，最终影响引擎的复权行为。

#### Scenario: 用户选择后复权
- **WHEN** 用户在前端点击“后复权”
- **THEN** `buildConfigDraft()` 返回的对象中包含 `universe.price_adj = "hfq"`
- **THEN** API 请求 payload 中包含 `price_adj: "hfq"`

#### Scenario: 默认值
- **WHEN** 用户未修改价格口径控件
- **THEN** 系统使用默认值 `"hfq"`

### Requirement: 产物可观测性

每次回测的 `run_meta` SHALL 记录实际使用的复权模式及其基础审计统计。

#### Scenario: run_meta 包含复权模式
- **WHEN** 回测完成
- **THEN** `run_meta.json` 中包含字段 `price_adj_mode`

#### Scenario: 产物中 adj_factor 统计
- **WHEN** 回测完成
- **THEN** `run_meta.json` 中包含 `adj_factor_stats`，记录 `min`、`max` 和 `null_count`

### Requirement: 持仓估值使用后复权价格

`compute_nav_snapshot()` SHALL 使用后复权收盘价计算持仓市值和 NAV；成交执行路径继续使用不复权价格。

#### Scenario: 除权除息日 NAV 连续性
- **WHEN** 某股票在日期 D 发生除权除息且引擎在日期 D 仍持有该股票
- **THEN** 日期 `D-1` 和 `D` 的 NAV 变动反映真实资产价值变化，而非虚假暴跌

#### Scenario: 无除权事件时行为不变
- **WHEN** 回测期间所有持仓股票无除权除息事件
- **THEN** HFQ 估值与 raw 估值结果完全一致

#### Scenario: 引擎入口传递 hfq 价格
- **WHEN** 调用 `run_portfolio_backtest(history=hfq_df, raw_history=raw_df, ...)`
- **THEN** `_build_price_indices` 必须从 `history` 构建估值用 close 索引
- **THEN** `_build_price_indices` 必须从 `raw_history` 构建成交用 open/close 索引

### Requirement: 双索引价格体系

`_build_price_indices` SHALL 同时构建不复权和后复权两套价格索引。

#### Scenario: 函数签名
- **WHEN** 调用 `_build_price_indices(raw_df, hfq_df)`
- **THEN** 返回 `(open_idx, raw_close_idx, hfq_close_idx)` 三个字典

#### Scenario: hfq_df 缺省时向后兼容
- **WHEN** 调用 `_build_price_indices(raw_df)` 不传 `hfq_df`
- **THEN** `hfq_close_idx` 等于 `raw_close_idx`
