## MODIFIED Requirements

### Requirement: V2 canonical 行状态 MUST 显式区分确认停牌与低可信补位
系统 MUST 为 `pams_ohlcv_daily_v2` 提供显式行状态，至少包括 `traded`、`suspended_confirmed`、`synthetic_gap_fill`、`source_unresolved`。系统 SHALL NOT 再把缺少 `daily` 且缺少 `suspend_d` 证据的补位行伪装为正常停牌行。对于 `SH/SZ` 以及 `BJ post-2021-11-15` 中同日存在 `adj_factor`、`daily_basic` 或 `stk_limit` 侧证据，但缺少 `daily` 与 `suspend_d` 的补位行，系统 MUST 记为 `synthetic_gap_fill`，而 SHALL NOT 继续记为 `source_unresolved`。`bj_pre_20211115` SHALL NOT 因本规则被重分类。

#### Scenario: SH/SZ 侧证据补位行
- **WHEN** 某 `SH/SZ` 行没有 `daily` 与 `suspend_d` 记录，但同日存在 `adj_factor`、`daily_basic` 或 `stk_limit` 任一侧证据
- **THEN** canonical 行状态 MUST 记为 `synthetic_gap_fill`
- **THEN** 系统 SHALL NOT 将其记为 `source_unresolved`
- **THEN** 系统 MUST 保留对应的 side-evidence 来源标记

#### Scenario: BJ post-2021-11-15 侧证据补位行
- **WHEN** 某 `BJ post-2021-11-15` 行没有 `daily` 与 `suspend_d` 记录，但同日存在 `adj_factor`、`daily_basic` 或 `stk_limit` 任一侧证据
- **THEN** canonical 行状态 MUST 记为 `synthetic_gap_fill`
- **THEN** 系统 SHALL NOT 将其记为 `source_unresolved`
- **THEN** 系统 MUST 保留对应的 side-evidence 来源标记

#### Scenario: BJ pre-2021-11-15 不因本规则改类
- **WHEN** 某 `BJ pre-2021-11-15` 行缺少 `daily` 与 `suspend_d`
- **THEN** 系统 SHALL NOT 仅因存在本规则的 side evidence 就把它改类为 `synthetic_gap_fill`
