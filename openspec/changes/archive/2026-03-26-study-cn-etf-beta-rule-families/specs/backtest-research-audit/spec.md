## ADDED Requirements

### Requirement: ETF 规则族研究必须审计 fallback 是否真实生效
当实验属于 ETF 规则族研究时，`research_audit` MUST 能证明 fallback 规则是否真实参与了决策，而不能仅根据结果收益推断。

最小证据至少 MUST 包含：
- fallback 类型
- fallback 触发次数
- fallback 持有天数或占比
- 对应 reason code 或等价证据引用

#### Scenario: fallback 被触发
- **WHEN** ETF 规则族研究在某段时间切入 `511010` 或现金代理
- **THEN** `research_audit` MUST 能说明 fallback 是何时、因何触发
- **THEN** `research_audit` MUST 能引用对应的 reason code 或证据字段

### Requirement: ETF 规则族研究必须审计缓冲带与风险缩放是否生效
当实验属于 `Dual Momentum + 缓冲带` 或 `Dual Momentum + Vol Target` 时，`research_audit` MUST 能证明缓冲带或风险缩放确实生效。

最小证据至少 MUST 包含：
- 未切换但本可切换的样本计数，或等价缓冲带证据
- 风险缩放前后预算变化摘要，或等价 vol target 证据

#### Scenario: 缓冲带抑制了一次原本可发生的切换
- **WHEN** 新候选满足排名条件但未超过缓冲阈值
- **THEN** `research_audit` MUST 能记录该次未切换事件

#### Scenario: Vol target 改变了 ETF sleeve 预算
- **WHEN** 近期波动上升导致 ETF sleeve 预算收缩
- **THEN** `research_audit` MUST 能说明预算变化与波动缩放之间的因果关系
