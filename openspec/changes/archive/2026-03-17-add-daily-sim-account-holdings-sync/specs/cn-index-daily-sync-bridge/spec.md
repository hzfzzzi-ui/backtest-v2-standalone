## ADDED Requirements

### Requirement: 每日 A 股调度必须同步 `pit_index_daily`
系统在每日 A 股定时导入成功刷新 `pams_ohlcv_daily` 后，MUST 继续将最新 `CN_INDEX` 行情增量同步到 `pit_index_daily`。该步骤 SHALL 与同次 scheduler run 绑定，并在 run summary 中记录其结果。

#### Scenario: 调度成功后同步指数基准表
- **WHEN** `run_cn_daily_sync_once()` 成功将 `pams_ohlcv_daily` 刷新到目标交易日
- **THEN** 系统 MUST 在同一次调度内执行 `pit_index_daily` 增量导入
- **AND** run summary MUST 记录 `pit_index_daily_refresh` 或等价字段

#### Scenario: 指数基准同步失败时显式失败
- **WHEN** `pit_index_daily` 增量导入失败
- **THEN** 本次 scheduler run MUST 标记为 failed 或等价显式异常状态
- **AND** summary MUST 保留错误摘要

### Requirement: market snapshot 基准日期必须能追上最新日行情
当每日调度完成后，系统读取 `000001.SH`、`399001.SZ`、`399006.SZ`、`000906.SH` 等指数基准时，SHALL 能从 `pit_index_daily` 读取到与本次调度目标交易日一致或不落后的数据。

#### Scenario: 调度后 market snapshot 不再误报旧指数日期
- **WHEN** scheduler 已成功刷新到某个目标交易日
- **THEN** 使用 `pit_index_daily` 的 market snapshot SHALL 不再因为旧的 `pit_index_daily` 数据误报这些基准指数过期

