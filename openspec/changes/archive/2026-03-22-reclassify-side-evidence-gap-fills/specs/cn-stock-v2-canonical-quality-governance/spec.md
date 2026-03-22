## MODIFIED Requirements

### Requirement: V2 canonical 行状态 MUST 显式区分确认停牌与低可信补行
系统 MUST 为 `pams_ohlcv_daily_v2` 提供显式行状态，至少包括 `traded`、`suspended_confirmed`、`synthetic_gap_fill`、`source_unresolved`。系统 SHALL NOT 再把缺少 `daily` 且缺少 `suspend_d` 证据的补行伪装为正常停牌行。对于 `SH/SZ` 中同日存在 `adj_factor`、`daily_basic` 或 `stk_limit` 侧证据，但缺少 `daily` 与 `suspend_d` 的补位行，系统 MUST 记为 `synthetic_gap_fill`，而 SHALL NOT 继续记为 `source_unresolved`。

#### Scenario: 有成交源的交易日
- **WHEN** 某 `symbol + trade_date` 具有有效 `daily` 原始记录
- **THEN** canonical 行状态 MUST 记为 `traded`
- **THEN** 系统 MUST 保留对应的 `source_daily_present=true`

#### Scenario: 有停牌源但无成交源的交易日
- **WHEN** 某 `symbol + trade_date` 没有 `daily` 记录但存在有效 `suspend_d` 记录
- **THEN** canonical 行状态 MUST 记为 `suspended_confirmed`
- **THEN** 系统 SHALL NOT 将其记为 `synthetic_gap_fill` 或 `source_unresolved`

#### Scenario: SH/SZ 侧证据补位行
- **WHEN** 某 `SH/SZ` 行没有 `daily` 与 `suspend_d` 记录，但同日存在 `adj_factor`、`daily_basic` 或 `stk_limit` 任一侧证据
- **THEN** canonical 行状态 MUST 记为 `synthetic_gap_fill`
- **THEN** 系统 SHALL NOT 将其记为 `source_unresolved`
- **THEN** 系统 MUST 保留对应的 side-evidence 来源标记

#### Scenario: 真正无源的补位行
- **WHEN** 某 `symbol + trade_date` 需要补位，且不存在 `daily`、`suspend_d` 以及任何允许的 side evidence
- **THEN** canonical 行状态 MUST 记为 `source_unresolved`
- **THEN** 系统 SHALL NOT 将其记为 `synthetic_gap_fill` 或 `suspended_confirmed`
