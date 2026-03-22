## ADDED Requirements

### Requirement: V2 canonical 行状态 MUST 显式区分确认停牌与低可信补行
系统 MUST 为 `pams_ohlcv_daily_v2` 提供显式行状态，至少包括 `traded`、`suspended_confirmed`、`synthetic_gap_fill`、`source_unresolved`。系统 SHALL NOT 再把缺少 `daily` 且缺少 `suspend_d` 证据的补行伪装为正常停牌行。

#### Scenario: 有成交源的交易日
- **WHEN** 某 `symbol + trade_date` 具有有效 `daily` 原始记录
- **THEN** canonical 行状态 MUST 记为 `traded`
- **THEN** 系统 MUST 保留对应的 `source_daily_present=true`

#### Scenario: 有停牌源但无成交源的交易日
- **WHEN** 某 `symbol + trade_date` 没有 `daily` 记录但存在有效 `suspend_d` 记录
- **THEN** canonical 行状态 MUST 记为 `suspended_confirmed`
- **THEN** 系统 SHALL NOT 将其记为 `synthetic_gap_fill` 或 `source_unresolved`

#### Scenario: 无成交源且无停牌源的补位行
- **WHEN** 某 `symbol + trade_date` 需要补位但不存在 `daily` 与 `suspend_d` 证据
- **THEN** canonical 行状态 MUST 记为 `synthetic_gap_fill` 或 `source_unresolved`
- **THEN** 系统 SHALL NOT 将其记为 `suspended_confirmed`

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
