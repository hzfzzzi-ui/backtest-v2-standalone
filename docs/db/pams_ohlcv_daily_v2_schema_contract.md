# `pams_ohlcv_daily_v2` Schema Contract

## 1. 目的

本合同约束 `V2` canonical 主表、moneyflow 侧表、审计表和异常表，确保字段新增、删除、降级和消费方式都以统一真相层为准。

当前适用对象：
- `pams_ohlcv_daily_v2`
- `pit_stock_moneyflow_v2`
- `pams_ohlcv_daily_v2_audit_daily`
- `pams_ohlcv_daily_v2_exceptions`

## 2. 核心原则

`V2` 的正式目标是：
- 可重建
- 可审计
- 可解释
- 可分层消费

重要约束：
- `V2` 必须覆盖 `SH + SZ + BJ`
- `BJ` 必须按 `2021-11-15` 前后分阶段治理
- canonical 表不等于 runtime 消费表
- 不允许再用“静默填零”掩盖来源缺失

## 3. 行状态合同

`pams_ohlcv_daily_v2.row_status` 正式允许值：
- `traded`
- `suspended_confirmed`
- `delist_tail_confirmed`
- `synthetic_gap_fill`
- `source_unresolved`

含义：
- `traded`：存在有效 `daily` 原始行
- `suspended_confirmed`：无 `daily` 但有 `suspend_d` 证据
- `delist_tail_confirmed`：正式终止边界已知，但终止尾段缺少 `daily/suspend_d` 原始源；可来自通用 terminal rule、显式官方 override，或“正式停牌证据早于 formal window 起点 + canonical `delist_date`”的显式 override
- `synthetic_gap_fill`：为满足连续性补位，但缺少完整一手证据
- `source_unresolved`：应有行存在，但主源与补源均未形成可接受证据链

约束：
- 无 `daily` 且无 `suspend_d` 的记录，禁止落成 `suspended_confirmed`
- `delist_tail_confirmed` 仅允许用于有显式终止边界的尾段；默认应位于最后原始源日期之后，例外仅限显式、已审过的 override symbol/date 窗口
- 当 explicit override 依赖“formal window 起点之前已暂停上市”的证据时，窗口终点必须仍由 canonical `delist_date` 锚定，不得脱离 `pit_security_master/raw_tushare_stock_basic` 单独外推
- `source_unresolved` 允许存在于 canonical，但不得被 runtime 默认无差别消费

## 4. 市场阶段合同

建议字段：
- `market_phase`

允许值：
- `sh`
- `sz`
- `bj_pre_20211115`
- `bj_post_20211115`

规则：
- `bj%` 且 `trade_date < 2021-11-15` 记为 `bj_pre_20211115`
- `bj%` 且 `trade_date >= 2021-11-15` 记为 `bj_post_20211115`

## 5. 主表字段合同

表名：`pams_ohlcv_daily_v2`

建议主键：
- `PRIMARY KEY (symbol, market, trade_date)`
- `UNIQUE (ts_code, trade_date)`

### 5.1 核心字段

| 字段 | 类型 | 非空 | 说明 |
|---|---|---:|---|
| `symbol` | `varchar(20)` | 是 | 内部标准代码，如 `sh600000` |
| `ts_code` | `varchar(12)` | 是 | 标准代码，如 `600000.SH` |
| `market` | `varchar(10)` | 是 | 当前固定 `CN_A` |
| `market_phase` | `varchar(24)` | 是 | `sh/sz/bj_pre_20211115/bj_post_20211115` |
| `trade_date` | `date` | 是 | 交易日 |
| `row_status` | `varchar(24)` | 是 | 五元状态 |
| `is_suspended` | `boolean` | 是 | 是否停牌 |
| `pre_close` | `numeric(12,4)` | 是 | 昨收或锚定价 |
| `open` | `numeric(12,4)` | 是 | 开盘价 |
| `high` | `numeric(12,4)` | 是 | 最高价 |
| `low` | `numeric(12,4)` | 是 | 最低价 |
| `close` | `numeric(12,4)` | 是 | 收盘价 |
| `volume` | `bigint` | 是 | 成交量，股 |
| `turnover` | `numeric(18,2)` | 是 | 成交额，元 |
| `adj_factor` | `numeric(14,6)` | 是 | 复权因子 |
| `limit_up` | `numeric(12,4)` | 是 | 涨停价 |
| `limit_down` | `numeric(12,4)` | 是 | 跌停价 |
| `turnover_rate` | `double precision` | 是 | 换手率 |

### 5.2 来源与可信度字段

| 字段 | 类型 | 非空 | 说明 |
|---|---|---:|---|
| `pre_close_source` | `text` | 是 | `daily_pre_close / prev_close_carry / anchor_fill / imputed_zero` |
| `pre_close_confidence` | `smallint` | 是 | 建议 `0-3`，`3` 为最高 |
| `adj_factor_source` | `text` | 是 | `tushare_adj_factor / prev_adj_factor_carry / default_1` |
| `adj_factor_confidence` | `smallint` | 是 | 建议 `0-3` |
| `turnover_rate_source` | `text` | 是 | `tushare_daily_basic / akshare_stock_zh_a_hist / formula_from_float_share / suspended_zero / imputed_zero` |
| `turnover_rate_confidence` | `smallint` | 是 | 建议 `0-3` |

### 5.3 `daily_basic` 扩展字段

| 字段 | 类型 | 非空 | 说明 |
|---|---|---:|---|
| `turnover_rate_f` | `double precision` | 否 | 自由流通换手率 |
| `volume_ratio` | `double precision` | 否 | 量比 |
| `float_share` | `double precision` | 否 | 流通股本 |
| `free_share` | `double precision` | 否 | 自由流通股本 |
| `circ_mv` | `double precision` | 否 | 流通市值 |

### 5.4 原始源存在性字段

| 字段 | 类型 | 非空 | 说明 |
|---|---|---:|---|
| `source_daily_present` | `boolean` | 是 | 当日是否有 raw `daily` |
| `source_adj_factor_present` | `boolean` | 是 | 当日是否有 raw `adj_factor` |
| `source_daily_basic_present` | `boolean` | 是 | 当日是否有 raw `daily_basic` |
| `source_stk_limit_present` | `boolean` | 是 | 当日是否有 raw `stk_limit` |
| `source_suspend_present` | `boolean` | 是 | 当日是否有 raw `suspend_d` |

### 5.5 构建元数据

| 字段 | 类型 | 非空 | 说明 |
|---|---|---:|---|
| `build_run_id` | `text` | 是 | 构建批次 |
| `build_version` | `text` | 是 | 构建版本 |
| `created_at` | `timestamptz` | 是 | 创建时间 |
| `updated_at` | `timestamptz` | 是 | 更新时间 |

## 6. 侧表合同

`pit_stock_moneyflow_v2` 保持为侧表，不进入主表硬合同。

原则：
- 只按 `symbol + trade_date` 对齐
- 只服务 `traded` 行
- `net_mf_* = NULL` 必须解释为源缺失，不得当 `0`

## 7. 异常表合同

表名：`pams_ohlcv_daily_v2_exceptions`

建议字段：
- `cause_class`

允许值：
- `missing_in_all_sources`
- `fallback_available`
- `mapping_failure`
- `build_rule_rejected`
- `source_present_low_confidence_fill`

关键 `issue_type`：
- `eligible_no_source`
- `delist_tail_confirmed`
- `turnover_rate_imputed_zero`
- `pre_close_imputed_zero`
- `adj_factor_missing`
- `raw_only_not_in_master`
- `daily_basic_missing`
- `moneyflow_missing`
- `hard_field_null_after_build`
- `soft_field_null_after_build`

## 8. 审计表合同

`pams_ohlcv_daily_v2_audit_daily` 后续必须支撑两层门禁：
- `canonical gate`
- `runtime gate`

建议扩展字段：
- `market_phase`
- `runtime_eligible_count`
- `canonical_gate_blocked`
- `runtime_gate_blocked`

## 9. 升格纪律

`V2` 升格分两层：

### 9.1 Canonical 升格

要求：
- 全历史可重建
- 核心字段空值受控
- unresolved 行可解释
- `BJ` 前后阶段解释清晰
- source matrix 完整

### 9.2 Runtime 升格

要求：
- 已有独立 runtime compat 层
- `V10.1` 等 baseline 的三窗口回归通过
- 行为差异可解释
- 默认切换具备回退方案

## 10. 新增/删除字段纪律

新增字段前必须回答：
1. 主源是什么
2. 补源是什么
3. 是否需要 `*_source`
4. 是否需要 `*_confidence`
5. 是否进入 canonical、runtime，还是只进入侧表

删除字段前必须回答：
1. 哪些 build/audit/runtime 在消费它
2. 删除是否改变历史口径
3. 回退方案是什么
