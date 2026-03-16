## ADDED Requirements

### Requirement: 系统必须按前一交易日定时同步 A 股日线数据
系统 MUST 在启用日更调度时，按配置时间自动尝试把 `pams_ohlcv_daily` 同步到前一交易日。目标日期 MUST 基于正式交易日历判定，而 SHALL NOT 直接使用自然日前一天。该正式交易日历来源 MUST 是当前活数据源，而 SHALL NOT 依赖已停更的库内旧表。

#### Scenario: 交易日收盘后触发日更
- **WHEN** 调度器已启用，且当前时间到达配置的日更触发时间
- **THEN** 系统 MUST 计算当前时点之前最近一个已开市的 A 股交易日作为 `target_trade_date`
- **THEN** 系统 MUST 尝试把 `pams_ohlcv_daily` 补到该 `target_trade_date`

#### Scenario: 非交易日不盲目同步自然日前一天
- **WHEN** 当前日期是周末或节假日
- **THEN** 系统 MUST 继续以交易日历返回的最近开市日作为 `target_trade_date`
- **THEN** 系统 SHALL NOT 因自然日变化而把同步目标错误推进到一个不开市的日期

#### Scenario: 库内旧交易日历落后时仍使用活数据源
- **WHEN** 库内历史交易日历表落后于当前活行情数据
- **THEN** 系统 MUST 继续以活交易日历源解析 `target_trade_date`
- **THEN** 系统 SHALL NOT 因旧表停更而把 `target_trade_date` 静默拉回旧日期

### Requirement: 同步器必须复用正式写库链路并保持幂等
系统 MUST 复用现有 `update_pams_ohlcv_daily` 的正式写库逻辑完成日更，而 SHALL NOT 另行实现第二套抓数与落库链路。对同一 `target_trade_date` 的重复执行 MUST 保持幂等，不得制造重复记录或破坏现有数据。

#### Scenario: 同一目标交易日重复执行
- **WHEN** 调度器或人工补跑再次针对同一个 `target_trade_date` 执行同步
- **THEN** 系统 MUST 继续通过正式 upsert 链路写入 `pams_ohlcv_daily`
- **THEN** 重复执行 SHALL NOT 在 `pams_ohlcv_daily` 中制造重复行

#### Scenario: 系统存在落后天数时追平到目标交易日
- **WHEN** 当前数据库最新 CN_A 交易日早于本次 `target_trade_date`
- **THEN** 系统 MUST 从现有最新日期之后开始追平
- **THEN** 系统 MUST 在单次执行结束后把数据补到 `target_trade_date` 或写出明确失败状态

### Requirement: 系统必须持久化每次同步运行状态
系统 MUST 为每次日更尝试持久化结构化同步状态，至少包括目标交易日、运行状态、开始/结束时间、同步前后最新交易日、摘要信息和错误信息。同步状态 MUST 能支持后续 API 和前端读取“最新成功同步日期”和“最近一次运行状态”。

#### Scenario: 成功同步写入成功状态
- **WHEN** 某次日更执行成功并完成写库
- **THEN** 系统 MUST 持久化一条 `success` 状态记录
- **THEN** 该记录 MUST 包含 `target_trade_date`、`latest_trade_date_before`、`latest_trade_date_after` 和运行摘要

#### Scenario: 同步失败写入失败状态
- **WHEN** 某次日更执行失败，例如交易日历缺失、数据库异常或数据源异常
- **THEN** 系统 MUST 持久化一条 `failed` 或等价失败状态记录
- **THEN** 该记录 MUST 保留错误摘要，供后续 API 和前端显式展示
