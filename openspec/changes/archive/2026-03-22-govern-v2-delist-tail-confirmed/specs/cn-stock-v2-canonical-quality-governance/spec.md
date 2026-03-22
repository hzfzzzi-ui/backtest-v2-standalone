## MODIFIED Requirements

### Requirement: V2 canonical 行状态 MUST 显式区分确认停牌、终止尾段与低可信补行
系统 MUST 为 `pams_ohlcv_daily_v2` 提供显式行状态，至少包括 `traded`、`suspended_confirmed`、`delist_tail_confirmed`、`synthetic_gap_fill`、`source_unresolved`。系统 SHALL NOT 再把缺少 `daily` 且缺少 `suspend_d` 证据的补行伪装为正常停牌行，也 SHALL NOT 把正式终止边界尾段继续记为普通源缺失。

#### Scenario: 有成交源的交易日
- **WHEN** 某 `symbol + trade_date` 具有有效 `daily` 原始记录
- **THEN** canonical 行状态 MUST 记为 `traded`
- **THEN** 系统 MUST 保留对应的 `source_daily_present=true`

#### Scenario: 有停牌源但无成交源的交易日
- **WHEN** 某 `symbol + trade_date` 没有 `daily` 记录但存在有效 `suspend_d` 记录
- **THEN** canonical 行状态 MUST 记为 `suspended_confirmed`
- **THEN** 系统 SHALL NOT 将其记为 `synthetic_gap_fill`、`delist_tail_confirmed` 或 `source_unresolved`

#### Scenario: 正式终止边界尾段
- **WHEN** 某 `symbol + trade_date` 没有 `daily` 与 `suspend_d` 记录
- **AND** 系统存在该 symbol 的正式终止边界证据
- **AND** 该日期位于最后原始源日期之后且不晚于正式终止边界
- **THEN** canonical 行状态 MUST 记为 `delist_tail_confirmed`
- **THEN** 系统 SHALL NOT 将其记为 `suspended_confirmed`

#### Scenario: 无成交源且无停牌源的补位行
- **WHEN** 某 `symbol + trade_date` 需要补位但不存在 `daily` 与 `suspend_d` 证据
- **AND** 该行不满足正式终止边界条件
- **THEN** canonical 行状态 MUST 记为 `synthetic_gap_fill` 或 `source_unresolved`
- **THEN** 系统 SHALL NOT 将其记为 `suspended_confirmed`
