## MODIFIED Requirements

### Requirement: 系统必须按前一交易日定时同步 A 股主线日更流水线
系统 MUST 在启用日更调度时，按配置时间自动尝试把 A 股正式主线补到前一交易日。目标日期 MUST 基于正式交易日历判定，而 SHALL NOT 直接使用自然日前一天。该正式交易日历来源 MUST 是当前活数据源，而 SHALL NOT 依赖已停更的库内旧表。正式主线日更 MUST 至少包含 `pams_ohlcv_daily` 兼容桥接、`pit_index_daily`、`raw_tushare_*`、`pams_ohlcv_daily_v2`、`pit_stock_moneyflow_v2`、`pit_stock_moneyflow_v2_whitelist_daily` 与 `csi800 PIT`。

#### Scenario: 交易日收盘后触发主线日更
- **WHEN** 调度器已启用，且当前时间到达配置的日更触发时间
- **THEN** 系统 MUST 计算当前时点之前最近一个已开市的 A 股交易日作为 `target_trade_date`
- **THEN** 系统 MUST 在同一次 scheduler run 内尝试把 V2 主线及其必要桥接表补到该 `target_trade_date`

#### Scenario: 旧表已新但 V2 主线落后时不得跳过
- **WHEN** `pams_ohlcv_daily` 已经达到本次 `target_trade_date`，但 `pams_ohlcv_daily_v2` 或 `pit_stock_moneyflow_v2` 或 `pit_stock_moneyflow_v2_whitelist_daily` 仍落后
- **THEN** 系统 SHALL NOT 仅因旧表已新而将本次 run 标记为 `skipped`
- **THEN** 系统 MUST 继续执行 V2 主线补齐步骤，直到 V2 主线到达 `target_trade_date` 或显式失败

#### Scenario: 非交易日不盲目同步自然日前一天
- **WHEN** 当前日期是周末或节假日
- **THEN** 系统 MUST 继续以交易日历返回的最近开市日作为 `target_trade_date`
- **THEN** 系统 SHALL NOT 因自然日变化而把同步目标错误推进到一个不开市的日期

### Requirement: 同步器必须按正式依赖顺序复用现有写库链路并保持幂等
系统 MUST 复用现有 managed updater 的正式写库逻辑完成日更，而 SHALL NOT 另行实现第二套抓数与落库链路。系统 MUST 保持以下依赖顺序：先执行 `update_pams_ohlcv_daily`，再执行 `update_pit_index_daily`；先执行 `update_pams_ohlcv_daily_v2_raw`，再执行 `update_pams_ohlcv_daily_v2`；先执行 `update_pams_ohlcv_daily_v2`，再执行 `update_pit_stock_moneyflow_v2`。对同一 `target_trade_date` 的重复执行 MUST 保持幂等，不得制造重复记录或破坏现有数据。

#### Scenario: 同一目标交易日重复执行主线日更
- **WHEN** 调度器或人工补跑再次针对同一个 `target_trade_date` 执行同步
- **THEN** 系统 MUST 继续通过各正式 updater 的 upsert 链路写入 legacy/V2 相关表
- **THEN** 重复执行 SHALL NOT 在目标表中制造重复行

#### Scenario: 系统存在落后天数时按顺序追平到目标交易日
- **WHEN** 当前 V2 主线最新交易日早于本次 `target_trade_date`
- **THEN** 系统 MUST 按依赖顺序执行 legacy bridge、index bridge、V2 raw、V2 canonical、V2 moneyflow 与 PIT sidecar
- **THEN** 系统 MUST 在单次执行结束后把 V2 主线补到 `target_trade_date` 或写出明确失败状态

### Requirement: 系统必须持久化以 V2 主线为锚点的每次同步运行状态
系统 MUST 为每次日更尝试持久化结构化同步状态，至少包括目标交易日、运行状态、开始/结束时间、同步前后最新交易日、摘要信息和错误信息。`latest_trade_date_after`、skip 判定和 success 判定 MUST 以 V2 主线日期为锚点，而 SHALL NOT 以 `pams_ohlcv_daily` 的最新日期替代。同步状态 MUST 支持后续 API 和前端读取“最新成功同步日期”和“最近一次运行状态”，并在 `summary_json` 中保留各阶段结果。

#### Scenario: V2 主线补齐成功时写入 success 状态
- **WHEN** 某次日更执行成功，且 `pams_ohlcv_daily_v2`、`pit_stock_moneyflow_v2` 与 `pit_stock_moneyflow_v2_whitelist_daily` 都到达 `target_trade_date`
- **THEN** 系统 MUST 持久化一条 `success` 状态记录
- **THEN** 该记录的 `latest_trade_date_after` MUST 等于 V2 主线锚点日期，而不是旧表日期

#### Scenario: 旧表已新但 V2 主线未到目标日时写入失败状态
- **WHEN** 本次 run 完成后 `pams_ohlcv_daily` 已达到 `target_trade_date`，但 V2 主线仍未达到该日期
- **THEN** 系统 MUST 将本次 run 标记为 `failed` 或等价显式失败状态
- **THEN** 系统 MUST 在 `summary_json` 中保留 legacy/V2 各阶段结果，供后续审计具体卡点
