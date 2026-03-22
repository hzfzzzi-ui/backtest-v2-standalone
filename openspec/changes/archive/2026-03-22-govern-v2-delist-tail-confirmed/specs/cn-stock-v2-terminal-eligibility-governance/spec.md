## ADDED Requirements

### Requirement: V2 MUST 将正式终止边界尾段与普通源缺失分开治理
系统 MUST 在 canonical 构建中把“正式终止边界已知，但对应交易日没有 `daily/suspend_d` 原始源”的尾段记录，与普通 `source_unresolved` 分开治理。系统 SHALL NOT 把这类尾段继续记为 `missing_in_all_sources`。

#### Scenario: 退市尾段进入 canonical
- **WHEN** 某 `symbol + trade_date` 原本会被分类为 `source_unresolved`
- **AND** 该 `symbol` 存在正式 `delist_date`
- **AND** `trade_date` 位于该 symbol 最后原始源日期之后且不晚于 `delist_date`
- **THEN** 系统 MUST 将该行记为 `delist_tail_confirmed`
- **THEN** 系统 SHALL NOT 将该行继续记为 `eligible_no_source`

#### Scenario: 代码变更退役尾段进入 canonical
- **WHEN** 某旧代码 symbol 原本会被分类为 `source_unresolved`
- **AND** 系统存在该 symbol 的显式代码变更退役边界
- **AND** `trade_date` 位于旧代码最后原始源日期之后且不晚于该退役边界
- **THEN** 系统 MUST 将该行记为 `delist_tail_confirmed`
- **THEN** 系统 MUST 将该边界视为“代码退役”，而不是普通退市或普通缺源

#### Scenario: 无终止边界证据时保持 unresolved
- **WHEN** 某 `symbol + trade_date` 没有 `daily/suspend_d` 原始源
- **AND** 系统既没有正式 `delist_date`，也没有显式代码退役边界
- **THEN** 系统 MUST 继续将该行记为 `source_unresolved`

### Requirement: 终止边界证据 MUST 显式可审计
系统 MUST 仅在存在显式、可追溯的终止边界证据时，才允许把尾段记录归类为 `delist_tail_confirmed`。系统 SHALL NOT 仅凭宽松启发式猜测终止边界。

#### Scenario: 使用退市日期作为终止边界
- **WHEN** 系统使用 `delist_date` 作为终止边界
- **THEN** 该日期 MUST 来自正式 master 数据
- **THEN** 系统 MUST 能追溯该 symbol 的最后原始源日期与终止边界日期

#### Scenario: 使用代码变更退役边界
- **WHEN** 系统使用代码变更退役边界
- **THEN** 该边界 MUST 来自显式维护的映射表或等价正式治理产物
- **THEN** 系统 MUST 保留 `mapping_source` 与可信度信息
