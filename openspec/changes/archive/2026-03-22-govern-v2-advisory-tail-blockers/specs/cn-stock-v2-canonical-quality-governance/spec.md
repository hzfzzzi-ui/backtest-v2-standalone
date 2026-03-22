## MODIFIED Requirements

### Requirement: `v2` canonical MUST 仅在显式、可审计的 terminal 证据下收敛连续无源尾段

系统 MUST 仅在 terminal window 有显式、可审计证据时，才允许把原本的 `source_unresolved` 收敛为 `delist_tail_confirmed`。当 override 依赖的是 formal window 起点之前已暂停上市的证据时，窗口终点 MUST 仍由 canonical `delist_date` 锚定。

#### Scenario: formal window 起点前已暂停上市的连续无源尾段可显式收敛
- **WHEN** 某个 `SH/SZ` symbol 在 formal window 起点前已有正式暂停上市证据
- **AND** `pit_security_master / raw_tushare_stock_basic` 已给出 canonical `delist_date`
- **AND** `2007-01-04 ~ delist_date` 之间的当前 canonical 行都仍是 `source_unresolved`
- **THEN** 系统 MAY 通过显式 symbol/date override 将这段窗口收敛为 `delist_tail_confirmed`
- **AND** override SHALL NOT 覆盖任何原本已是 `traded`、`suspended_confirmed` 或 `synthetic_gap_fill` 的行
