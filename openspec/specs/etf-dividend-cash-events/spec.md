# etf-dividend-cash-events Specification

## Purpose
TBD - created by archiving change add-explicit-etf-dividend-cash-events. Update Purpose after archive.
## Requirements
### Requirement: CN ETF 分红必须形成正式事件流
系统 MUST 为 `cn_etf` 主线提供正式的现金分红事件流，而不是仅依赖 `adj_factor` 在估值层隐含表达分红。

#### Scenario: provider 返回 ETF 分红事件
- **WHEN** 回测主路径请求 `cn_etf` 的市场数据窗口
- **THEN** provider 返回独立的 ETF 分红事件集合
- **AND** 每条事件至少包含 `event_id`、`symbol`、`ts_code`、`ex_date`、`pay_date` 与 `div_cash`

### Requirement: 除息日必须确认分红权益
系统 MUST 在 ETF 分红事件的除息日，按除息日前已持有的份额确认本次分红权益。

#### Scenario: ex-date 前持仓获得分红权益
- **WHEN** 某 ETF 在日期 `D` 为 `ex_date`
- **AND** 组合在 `D` 日 open fills 之前持有该 ETF
- **THEN** 系统按 `held_qty * div_cash` 计算本次分红权益
- **AND** 当日新买入仓位不得参与该笔分红

### Requirement: 分红到账口径必须可配置
系统 MUST 支持 `ex_date` 与 `pay_date` 两种正式 cash 入账口径。

#### Scenario: ex-date 口径直接入账 cash
- **WHEN** `execution.dividend_cash_timing_mode = "ex_date"`
- **AND** 除息日确认到有效分红权益
- **THEN** 分红金额当日直接计入 `cash`

#### Scenario: pay-date 口径先记应收后到账
- **WHEN** `execution.dividend_cash_timing_mode = "pay_date"`
- **AND** 除息日确认到有效分红权益
- **THEN** 分红金额当日先计入 `dividend_receivable`
- **AND** 到账日再从 `dividend_receivable` 转入 `cash`

### Requirement: 分红事件必须幂等
系统 MUST 保证同一 ETF 分红事件在运行时只被处理一次，不得因重复 prepare/day loop 导致重复入账。

#### Scenario: 同一事件不会重复记账
- **WHEN** 同一个 `event_id` 已经完成除息确认或到账结转
- **THEN** 后续同日重复执行不会再次增加 `cash` 或 `dividend_receivable`

