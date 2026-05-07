# cn-stock-raw-staging Specification

## Purpose
浠?2026-03-22 褰掓。鍙樻洿鎭㈠鐨勪富瑙勬牸銆?
## Requirements

### Requirement: A 股日频原始数据必须先落 raw staging
系统 MUST 在构建 `pams_ohlcv_daily_v2` 之前，先将 A 股日频原始源按 `ts_code + trade_date` 落入 raw staging。首版 raw staging MUST 至少覆盖 Tushare `daily`、`adj_factor`、`daily_basic`、`moneyflow` 和 `trade_cal`，并为每次写入记录 `source_run_id` 与 `ingested_at`。

#### Scenario: 单交易日原始抓取入库
- **WHEN** 系统执行某个 `trade_date` 的原始抓取
- **THEN** 系统 MUST 将该日抓取到的 `daily`、`adj_factor`、`daily_basic`、`moneyflow` 结果分别按各自 raw 表写入
- **THEN** 每一行 raw 记录 MUST 带有可追溯的批次标记

#### Scenario: 重跑同一批次保持幂等
- **WHEN** 系统重复抓取同一 `trade_date` 与同一 `ts_code`
- **THEN** 系统 SHALL 以幂等 upsert 或可追溯版本写入方式处理，而不是静默产生重复主键脏数据

### Requirement: 交易日历原始层必须覆盖 v2 重建窗口
系统 MUST 为 `pams_ohlcv_daily_v2` 的重建窗口提供可审计交易日历原始层。对于 `2007-01-04` 到当前最新可得交易日的重建，系统 MUST 能给出完整的开市日集合，而不能依赖当前不完整的 `pit_trade_cal` 作为唯一日期骨架。

#### Scenario: 2007-2026 日期骨架可用
- **WHEN** 系统准备执行 `2007-01-04` 到当前最新可得交易日的 v2 历史回填
- **THEN** 系统 MUST 先验证交易日历原始层覆盖整个回填窗口
- **THEN** 若日期骨架不完整，系统 SHALL 阻止 canonical build 继续执行

### Requirement: raw staging 必须显式记录抓取失败和源缺口
系统 MUST 区分“源返回空结果”、“抓取失败”和“后续 canonical 过滤掉的行”，而不能把这些状态混成同一类缺口。

#### Scenario: 原始抓取失败被记录
- **WHEN** 某个原始接口在某个 `trade_date` 抓取失败
- **THEN** 系统 MUST 记录失败批次、源接口名称和错误摘要
- **THEN** 系统 SHALL NOT 在不留痕的前提下把该日视为“正常无数据”
