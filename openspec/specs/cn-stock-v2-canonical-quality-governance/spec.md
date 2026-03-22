# cn-stock-v2-canonical-quality-governance Specification

## Purpose
规范 V2 canonical 主表的行状态、关键字段来源与 terminal tail 收敛边界。

## Requirements

### Requirement: V2 canonical 行状态 MUST 显式区分确认停牌与低可信补行
系统 MUST 为 `pams_ohlcv_daily_v2` 提供显式行状态，至少包括 `traded`、`suspended_confirmed`、`synthetic_gap_fill`、`source_unresolved`。系统 SHALL NOT 再把缺少 `daily` 且缺少 `suspend_d` 证据的补位行伪装为正常停牌行。对于 `SH/SZ` 以及 `BJ post-2021-11-15` 中同日存在 `adj_factor`、`daily_basic` 或 `stk_limit` 侧证据，但缺少 `daily` 与 `suspend_d` 的补位行，系统 MUST 记为 `synthetic_gap_fill`，而 SHALL NOT 继续记为 `source_unresolved`。`BJ pre-2021-11-15` SHALL NOT 因本规则被重分类。

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

#### Scenario: BJ post-2021-11-15 侧证据补位行
- **WHEN** 某 `BJ post-2021-11-15` 行没有 `daily` 与 `suspend_d` 记录，但同日存在 `adj_factor`、`daily_basic` 或 `stk_limit` 任一侧证据
- **THEN** canonical 行状态 MUST 记为 `synthetic_gap_fill`
- **THEN** 系统 SHALL NOT 将其记为 `source_unresolved`
- **THEN** 系统 MUST 保留对应的 side-evidence 来源标记

#### Scenario: BJ pre-2021-11-15 不因本规则改类
- **WHEN** 某 `BJ pre-2021-11-15` 行缺少 `daily` 与 `suspend_d`
- **THEN** 系统 SHALL NOT 仅因存在本规则的 side evidence 就把它改类为 `synthetic_gap_fill`

#### Scenario: 真正无源的补位行
- **WHEN** 某 `symbol + trade_date` 需要补位，且不存在 `daily`、`suspend_d` 以及任何允许的 side evidence
- **THEN** canonical 行状态 MUST 记为 `source_unresolved`
- **THEN** 系统 SHALL NOT 将其记为 `synthetic_gap_fill` 或 `suspended_confirmed`

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

### Requirement: `v2` canonical MUST 仅在显式、可审计的 terminal 证据下收敛连续无源尾段
系统 MUST 仅在 terminal window 有显式、可审计证据时，才允许把原本的 `source_unresolved` 收敛为 `delist_tail_confirmed`。当 override 依赖的是 formal window 起点之前已暂停上市的证据时，窗口终点 MUST 仍由 canonical `delist_date` 锚定。

#### Scenario: formal window 起点前已暂停上市的连续无源尾段可显式收敛
- **WHEN** 某个 `SH/SZ` symbol 在 formal window 起点前已有正式暂停上市证据
- **AND** `pit_security_master / raw_tushare_stock_basic` 已给出 canonical `delist_date`
- **AND** `2007-01-04 ~ delist_date` 之间的当前 canonical 行都仍是 `source_unresolved`
- **THEN** 系统 MAY 通过显式 symbol/date override 将这段窗口收敛为 `delist_tail_confirmed`
- **AND** override SHALL NOT 覆盖任何原本已是 `traded`、`suspended_confirmed` 或 `synthetic_gap_fill` 的行

### Requirement: 关键字段 MUST 记录来源与可信度
系统 MUST 为 `pre_close`、`adj_factor`、`turnover_rate` 以及 `daily_basic` 关键派生字段提供来源与可信度表达。若字段值来自补源、推导或填充值，系统 MUST 能通过 `*_source` 与 `*_confidence` 区分，而不只是提供最终数值。

#### Scenario: 使用主源字段
- **WHEN** 关键字段由主源直接提供
- **THEN** 系统 MUST 记录该字段的主源标记
- **THEN** 系统 MUST 给予高可信度标记

#### Scenario: 使用补源或推导字段
- **WHEN** 关键字段由补源、推导公式或补位逻辑生成
- **THEN** 系统 MUST 记录具体来源
- **THEN** 系统 MUST 以低于主源的可信度标记表达该值

### Requirement: Canonical MUST 禁止把未解释缺失静默写成零值
系统 MUST 将 `pre_close=0`、`turnover_rate=0` 等零值区分为“真实零值”和“低可信填零”。若零值来自无源补位，系统 MUST 通过状态、来源和 exception 明确表达，且 SHALL NOT 仅通过最终字段值掩盖该事实。

#### Scenario: 真实零成交停牌日
- **WHEN** 某停牌日有明确停牌证据且 `volume=0`
- **THEN** 系统 MAY 记录 `turnover_rate=0`
- **THEN** 该零值 MUST 带有可解释的来源与状态

#### Scenario: 无源补位导致的零值
- **WHEN** 系统因缺少主源与补源只能对关键字段填零
- **THEN** 系统 MUST 记录对应异常
- **THEN** 系统 SHALL NOT 将该零值视为与真实零值等价
