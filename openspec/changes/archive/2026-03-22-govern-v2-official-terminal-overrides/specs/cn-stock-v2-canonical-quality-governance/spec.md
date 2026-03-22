## MODIFIED Requirements

### Requirement: V2 canonical 行状态 MUST 显式区分确认停牌、正式 terminal 尾段与真无源
系统 MUST 为 `pams_ohlcv_daily_v2` 提供显式行状态，至少包括 `traded`、`suspended_confirmed`、`delist_tail_confirmed`、`synthetic_gap_fill`、`source_unresolved`。其中 `delist_tail_confirmed` 既可来自通用 terminal boundary 规则，也可来自显式官方 override；系统 SHALL NOT 把这两类记录继续记为 `source_unresolved`。

#### Scenario: 通用 terminal boundary 命中
- **WHEN** 某 `symbol + trade_date` 原本会被分类为 `source_unresolved`
- **AND** 该行满足通用的 terminal boundary 条件
- **THEN** 系统 MUST 将该行记为 `delist_tail_confirmed`

#### Scenario: 显式官方 override 命中
- **WHEN** 某 `symbol + trade_date` 原本会被分类为 `source_unresolved`
- **AND** 该行命中显式官方 terminal override
- **THEN** 系统 MUST 将该行记为 `delist_tail_confirmed`
- **THEN** 系统 MUST 保留对应的证据来源标签，供 exception 与审计追溯

#### Scenario: 真无源样本保持 unresolved
- **WHEN** 某 `symbol + trade_date` 没有 `daily/suspend_d` 原始源
- **AND** 该行既不满足通用 terminal boundary 条件，也未命中显式官方 override
- **THEN** 系统 MUST 继续将该行记为 `source_unresolved`
