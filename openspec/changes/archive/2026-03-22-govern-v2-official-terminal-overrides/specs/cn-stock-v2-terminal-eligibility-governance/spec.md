## MODIFIED Requirements

### Requirement: 终止边界证据 MUST 支持显式官方 override
系统 MUST 仅在存在显式、可追溯的终止边界证据时，才允许把补位行归类为 `delist_tail_confirmed`。除基于 `delist_date` 或代码变更边界的通用规则外，系统 MAY 为经审过的个别 symbol 维护显式官方 override；该 override MUST 明确列出 symbol、起止日期窗口和证据来源标签，且 SHALL NOT 被泛化为无界启发式。

#### Scenario: 命中显式官方 override 的 unresolved 行
- **WHEN** 某 `symbol + trade_date` 原本会被分类为 `source_unresolved`
- **AND** 系统存在该 symbol 的显式官方 terminal override
- **AND** `trade_date` 落在 override 的起止窗口内
- **THEN** 系统 MUST 将该行记为 `delist_tail_confirmed`
- **THEN** 系统 SHALL NOT 将该行继续记为 `eligible_no_source`

#### Scenario: 非 registry symbol 不得命中官方 override
- **WHEN** 某 `symbol + trade_date` 原本会被分类为 `source_unresolved`
- **AND** 系统不存在该 symbol 的显式官方 terminal override
- **THEN** 系统 SHALL NOT 仅凭交易所规则常识或辅助原始源延续去推断该行属于 `delist_tail_confirmed`

#### Scenario: override 只允许覆盖 unresolved 行
- **WHEN** 某行已经被分类为 `traded`、`suspended_confirmed` 或 `synthetic_gap_fill`
- **AND** 该行所在 symbol 存在显式官方 terminal override
- **THEN** 系统 SHALL NOT 因 override 再次重写该行状态
