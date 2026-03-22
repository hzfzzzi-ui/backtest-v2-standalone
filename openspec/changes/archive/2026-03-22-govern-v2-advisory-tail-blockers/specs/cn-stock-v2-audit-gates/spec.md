## MODIFIED Requirements

### Requirement: advisory 全周期剩余 blocker MUST 只反映真实未治理样本

系统 MUST 在 advisory 全周期中区分“已被显式 terminal override 收口的连续尾段”和“仍需继续保留的真实 unresolved”。命中 pre-window pause override 的记录 SHALL NOT 继续计入 `eligible_no_source` 或有效 `critical_exception_rows`。

#### Scenario: pre-window pause override 命中的尾段不再计入 advisory blocker
- **WHEN** `2007-2026` audit 覆盖到命中 pre-window pause override 的 `delist_tail_confirmed` 行
- **THEN** 这些行 MUST 不再计入 `eligible_no_source_rows`
- **AND** 与之配对的 `pre_close_imputed_zero / turnover_rate_imputed_zero` SHALL 按既有 known source gap 规则处理
- **AND** advisory `critical_exception_rows` 只保留仍未收敛的真实 unresolved 或其他未治理异常
