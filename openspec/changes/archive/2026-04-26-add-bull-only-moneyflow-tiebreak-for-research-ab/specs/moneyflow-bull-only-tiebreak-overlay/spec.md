## ADDED Requirements

### Requirement: BULL-only moneyflow tiebreak overlay
系统 SHALL 支持一个研究态 moneyflow overlay 模式，使 `monthly_divergence_rate` 仅在当日股票腿 `effective_state_5` 为 `BULL` 时参与候选并列打破；在非 `BULL` 日子中，该 overlay MUST 不改变候选选择结果。

#### Scenario: Overlay activates inside BULL
- **WHEN** moneyflow overlay mode 为 `bull_only_tiebreak` 且当日 `effective_state_5` 为 `BULL`
- **THEN** 系统 MUST 仅在现有候选并列打破逻辑中应用 moneyflow overlay，而不改变主排序主干

#### Scenario: Overlay is suppressed outside BULL
- **WHEN** moneyflow overlay mode 为 `bull_only_tiebreak` 且当日 `effective_state_5` 不为 `BULL`
- **THEN** 系统 MUST 退化为 overlay 关闭，并保持与 baseline 相同的候选计划行为

### Requirement: BULL-only overlay diagnostics
系统 SHALL 输出最小诊断信息，用于审计 `bull_only_tiebreak` 是否真实启用以及是否因非 `BULL` 状态被抑制。

#### Scenario: Daily diagnostics expose BULL gating
- **WHEN** 回测以 `bull_only_tiebreak` 模式运行
- **THEN** 日级诊断 MUST 能区分 overlay 已启用、`BULL` gate 已打开、以及因非 `BULL` 被抑制的天数

#### Scenario: Existing overlay modes remain unchanged
- **WHEN** moneyflow overlay mode 为 `shadow`、`tiebreak`、`soft_weight` 或 `veto_bottom*`
- **THEN** 系统 MUST 保持这些模式的既有行为不变
