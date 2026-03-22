## Why

当前 `pams_ohlcv_daily` 的生成链路把原始抓取、字段补齐、停牌补行、`daily_basic` 融合和主表写入混在一个脚本里，导致历史覆盖缺口、审计边界和运行时合同纠缠在一起。既然已经确认 `daily_basic`、`moneyflow` 与现有主表在全历史上存在系统性缺口和超出，现在需要另开一条可审计、可回放、以 `security master` 为边界的 `pams_ohlcv_daily_v2` 重建链路，而不是继续补丁式修 `v1`。

## What Changes

- 新增 A 股日频原始分层落地能力，按 `trade_date + ts_code` 落库 Tushare `daily`、`adj_factor`、`daily_basic`、`moneyflow`、`trade_cal` 原始数据，并记录运行批次。
- 新增 `pams_ohlcv_daily_v2` 构建能力，以 `pit_security_master` 为证券边界、以原始 `daily` 为主行来源，重建 `CN_A` canonical 主表。
- 新增 `pit_stock_moneyflow_v2` 对齐侧表，使用 `pams_ohlcv_daily_v2` 主键对齐资金流，而不是直接依附旧表。
- 新增 `pams_ohlcv_daily_v2` 审计能力，输出原始层覆盖率、主表构建覆盖率、`daily_basic`/`moneyflow` 对齐率、异常样本和 `v1/v2` 差异摘要。
- 新增 shadow 切换配置与回归验证路径，在不修改现有默认 `stocks_table` 的前提下，让 V10.1 可对 `v2` 做平行验证。

## Capabilities

### New Capabilities
- `cn-stock-raw-staging`: 为 A 股日频原始行情、复权、换手率、资金流和交易日历建立可审计 raw staging 层。
- `cn-stock-daily-v2-canonical`: 构建 `pams_ohlcv_daily_v2`、`pit_stock_moneyflow_v2` 及其覆盖率/异常审计链路，并提供 shadow 消费入口。

### Modified Capabilities
- `api-runtime-config-compilation`: 运行时配置编译需要支持显式切换到 `pams_ohlcv_daily_v2` shadow 配置，但默认行为不变。

## Impact

- 数据库：新增 raw staging 表、`pams_ohlcv_daily_v2`、`pit_stock_moneyflow_v2`、审计表和必要索引/分区。
- 托管脚本：新增原始抓取、canonical build、差异审计和 shadow regression 入口。
- 配置与运行时：新增 `pams_cn_pg_v2.json` 或等价 shadow 配置，不直接替换现有 `pams_cn_pg.json`。
- 回测与验证：需要对 `2016-2026`、`2007-2017`、`2007-2026` 三窗口做 `v1/v2` 平行对比，确认股票池、停牌处理、换手率字段和价格口径差异。
