## MODIFIED Requirements

### Requirement: Source governance MUST 区分源缺失与构建缺失
系统 MUST 在 `v2` 审计与异常分类中区分“源本身缺失”和“构建阶段未正确消费源”。对于 `eligible_no_source`、`turnover_rate_imputed_zero`、`pre_close_imputed_zero` 等异常，系统 MUST 能说明该异常是由于所有候选源均无数据、主源缺失但补源可得、历史左截断导致当前窗口内缺少价格锚点，还是构建规则拒绝落行。

#### Scenario: 生成异常分类
- **WHEN** 系统为 `v2` 生成 exceptions
- **THEN** 每条异常 MUST 至少能归入一种来源解释分类
- **THEN** 异常汇总 MUST 能按来源解释分类聚合输出

#### Scenario: `pre_close` 左截断锚点缺口单独归类
- **WHEN** 某条非 `traded` 的 canonical 行无法从 `daily_pre_close`、`prev_close_carry`、`basic_close_anchor`、`daily_close_anchor` 获得正 `pre_close`
- **AND** 该行属于窗口起始连续缺锚点区段，而不是已有正锚点后的中段回归
- **THEN** 系统 MUST 将 `pre_close_imputed_zero` 归类为 `left_censored_anchor_gap`
- **THEN** 系统 SHALL NOT 继续将该样本记为泛化的 `source_present_low_confidence_fill`

#### Scenario: 真无源 `pre_close` 不得并入左截断已知源缺口
- **WHEN** 行状态仍为 `source_unresolved`
- **THEN** 系统 SHALL NOT 仅因为该行也出现 `pre_close_imputed_zero` 就将其并入 `left_censored_anchor_gap`
- **THEN** 系统 MUST 继续保留其真无源语义
