# execution-lineage-ledger Specification

## Purpose
TBD - created by archiving change add-signal-order-fill-lineage-audit. Update Purpose after archive.
## Requirements
### Requirement: 执行链实体必须携带稳定 lineage id
系统 MUST 在正式执行链中为信号、订单和成交生成稳定且可复现的 lineage id，并显式表达 `signal_id -> order_id -> fill_id` 的父子关系。

#### Scenario: 信号生成稳定 signal_id
- **WHEN** 某条正式买入或卖出信号进入执行链
- **THEN** 系统 SHALL 为该信号生成稳定 `signal_id`
- **THEN** 相同输入条件下重新运行实验时，该信号 SHALL 生成相同的 `signal_id`

#### Scenario: 订单和成交继承父链路
- **WHEN** 某条信号被排程为订单并最终形成成交
- **THEN** 订单 SHALL 生成 `order_id` 并显式引用父 `signal_id`
- **THEN** 成交 SHALL 生成 `fill_id` 并显式引用父 `order_id`

### Requirement: 生命周期台账必须记录关键状态流转
系统 MUST 为进入正式执行链的实体记录最小生命周期状态流转，至少覆盖 `generated`、`scheduled`、`filled`、`rejected`、`canceled` 或 `expired` 等关键状态，以及对应日期、原因和核心诊断字段。

#### Scenario: 正常 next-day 成交
- **WHEN** 某条信号在交易日 T 生成，并在 T+1 被排程且成交
- **THEN** 台账 SHALL 记录该实体从 `generated` 到 `scheduled` 再到 `filled` 的状态流转
- **THEN** 每个状态 SHALL 带有对应日期与 lineage id

#### Scenario: 订单未成交而终止
- **WHEN** 某条订单未形成成交并以拒绝、取消或失效结束
- **THEN** 台账 SHALL 记录对应终态及原因
- **THEN** 审计链 SHALL 能区分它与“丢失记录”不是同一类问题

### Requirement: lineage 明细与摘要必须分层输出
系统 MUST 将全量生命周期明细输出到独立 ledger artifact，并在主审计文件中只保留摘要、异常样本和引用。

#### Scenario: 主审计引用台账
- **WHEN** 一次实验完成并生成标准 artifacts
- **THEN** 系统 SHALL 写出独立的 lineage ledger artifact
- **THEN** `audit.json` SHALL 仅包含 lineage 摘要、异常样本与 ledger 引用，而不是内联全量明细

