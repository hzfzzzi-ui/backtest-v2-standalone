## MODIFIED Requirements

### Requirement: research audit 必须引用A股统一归因证据链
当实验属于 Governed A 股主线时，`research_audit` MUST 引用统一的 `attribution_audit` 证据链，而不是自行重算或拼接 regime 语义。

它至少 MUST 引用：
- regime 的 `base_state_5 / effective_state_5`
- `regime_confidence`
- `regime_transition_reason`
- `reason_codes`
- `manual_override`
- Governor 的 `budget_reason_codes`
- 正式执行链的 `candidate_boundary / candidate_plan / execution_kernel` 摘要

当 ETF 子系统需要额外研究解释时，`research_audit` MAY 进一步引用 ETF 研究视图证据，但 SHALL NOT 再把 `sleeve_budget` 或等价历史别名当成正式归因真相。

`research_audit` SHALL NOT 仅根据 `market_state`、`trade_mode` 或收益结果对状态来源做推断。

#### Scenario: Governed A股实验引用统一证据链
- **WHEN** 实验运行属于 Governed A 股主线
- **THEN** `research_audit` MUST 引用统一 attribution 证据，而不是独立再拼 regime 解释
- **THEN** `research_audit` MUST 优先消费正式执行链摘要，而不是依赖历史 `sleeve_budget` 别名

### Requirement: research audit 必须能回答仓位与状态来源
当实验属于 Governed A 股主线时，research audit MUST 能回答以下问题：
- 今天的有效市场状态是什么
- 这个状态主要由什么原因形成或未切换
- 当前预算是如何被 regime / drawdown / cooldown / override 共同决定的
- 股票 alpha 子系统与 ETF 子系统为什么拿到当前预算

对应产物至少 MUST 暴露：
- 当前 `effective_state_5`
- 当前 `regime_transition_reason`
- 当前 `budget_reason_codes`
- 当前 `manual_override` 摘要
- 当前正式执行链的 `candidate_boundary / candidate_plan / execution_kernel` 摘要

当 ETF 预算、节奏或缺口需要进一步解释时，`research_audit` SHALL 通过 ETF 研究证据回答，而不是要求正式审计继续暴露 ETF 私有中间字段。

#### Scenario: audit 能解释为什么今天不是满仓
- **WHEN** 用户查看 Governed A 股实验的 research audit
- **THEN** 审计结果 MUST 能明确回答当前总仓位为什么没有开满，以及这是由状态、drawdown、override 或 ETF 研究解释共同导致
- **THEN** `research_audit` SHALL NOT 再要求正式产物提供 `sleeve_budget` 历史别名
