## MODIFIED Requirements

### Requirement: source governance MUST 区分 pre-window pause terminal tail 与真无源缺口

系统 MUST 能区分“formal window 起点已经落在暂停上市后的 terminal tail”与“整个窗口内都没有任何可审计证据的真无源缺口”。前者可以进入显式 override；后者 SHALL 继续保留为 `source_unresolved`。

#### Scenario: pre-window pause 证据不足时不得进入 override
- **WHEN** 某个 symbol 虽然在 `2007-01-04 ~ delist_date` 连续无源
- **BUT** formal window 起点之前没有正式暂停上市证据
- **THEN** 系统 SHALL NOT 仅凭 `delist_date` 就把这段窗口并入 `delist_tail_confirmed`
- **AND** 这些行 MUST 继续保留为 `source_unresolved`
