## ADDED Requirements

### Requirement: A股子系统必须提供统一的归因与审计层
系统 MUST 提供 `cn-a-attribution-audit` 能力，统一汇聚 `market_regime_engine`、`global_portfolio_governor`、各 sleeve 行为和人工 override 的解释链。该能力 SHALL 成为 A 股子系统正式的横切审计层，而 SHALL NOT 继续只作为散落在 `run_meta`、`audit` 和 debug 产物中的零散字段。

#### Scenario: 运行完成后生成 attribution 审计摘要
- **WHEN** 一次 A 股实验完成并进入标准产物稳定化阶段
- **THEN** 系统 MUST 生成统一的 attribution 摘要
- **THEN** 该摘要 MUST 可被 `run_meta.json`、`audit.json` 或等价产物引用

### Requirement: Attribution audit 必须覆盖状态、预算、sleeve 与人工干预
`cn-a-attribution-audit` MUST 至少覆盖四类审计日志：
- `state_logs`
- `budget_logs`
- `sleeve_logs`
- `manual_override_logs`

系统 MUST 允许通过这些日志回答“状态为何切换”“预算为何变化”“哪个 sleeve 被压缩”“人工判断是否介入”等问题。

#### Scenario: 预算变化有解释链
- **WHEN** 某一交易日的总预算或 sleeve 预算相较上一交易日发生变化
- **THEN** attribution audit MUST 记录相应的状态、回撤、恢复或 override 解释字段

#### Scenario: 人工干预有独立留痕
- **WHEN** 某一交易日存在 `manual_override`
- **THEN** attribution audit MUST 记录 `base_state`
- **THEN** attribution audit MUST 记录 `effective_state`
- **THEN** attribution audit MUST 记录 override 的来源、原因或作用域

### Requirement: Attribution audit 必须提供 reason code 汇总
`cn-a-attribution-audit` MUST 输出统一的 `reason_code_summary` 或等价汇总结构，用于统计各类状态切换、预算压缩、sleeve 拒单和人工干预在样本窗口中的分布。

#### Scenario: 可汇总统计主导原因
- **WHEN** 用户查看一次 A 股实验的归因结论
- **THEN** 系统 MUST 能按 reason code 汇总主要状态来源和预算来源
- **THEN** 系统 SHALL NOT 只提供难以聚合的自由文本日志

