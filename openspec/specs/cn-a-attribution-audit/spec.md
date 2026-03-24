# cn-a-attribution-audit Specification

## Purpose
定义 A 股子系统统一的状态、预算、sleeve 与人工干预归因审计层，确保 governed multi-sleeve 主线能够稳定回答“状态从哪里来、预算为什么变、谁影响了最终决策”。

## Requirements

### Requirement: A股子系统必须提供统一的归因与审计层
系统 MUST 提供 `cn-a-attribution-audit` 能力，统一汇聚 `market_regime_engine`、`global_portfolio_governor`、各 sleeve 行为和人工 override 的解释链。该能力 SHALL 成为 A 股子系统正式的横切审计层，而 SHALL NOT 继续只作为散落在 `run_meta`、`audit` 和 debug 产物中的零散字段。

#### Scenario: 运行完成后生成 attribution 审计摘要
- **WHEN** 一次 A 股实验完成并进入标准产物稳定化阶段
- **THEN** 系统 MUST 生成统一的 attribution 摘要
- **THEN** 该摘要 MUST 可被 `run_meta.json`、`audit.json` 或等价产物引用

### Requirement: Attribution audit 必须覆盖状态、预算、sleeve 与人工干预
`cn-a-attribution-audit` MUST 至少覆盖：
- `state_logs`
- `budget_logs`
- `sleeve_logs`
- `manual_override_logs`
- `reason_code_summary`

其中 regime 相关日志至少 MUST 记录：
- `base_state_5`
- `effective_state_5`
- `coarse_state`
- `effective_coarse_state`
- `regime_confidence`
- `regime_transition_reason`
- `reason_codes`
- `subscores`
- `manual_override`

Attribution audit SHALL NOT 仅引用最终 `market_state` 文本而丢失原始状态或干预来源。

#### Scenario: 归因日志包含状态双轨
- **WHEN** 系统生成归因审计产物
- **THEN** 归因日志 MUST 能同时回答“模型原始状态是什么”和“最终生效状态是什么”

#### Scenario: 归因日志记录人工干预
- **WHEN** 某交易日存在 manual override
- **THEN** 归因日志 MUST 记录 override 的原因、范围和生效对象

### Requirement: Attribution audit 必须提供 reason code 汇总
`cn-a-attribution-audit` MUST 输出统一的 `reason_code_summary` 或等价汇总结构，用于统计各类状态切换、预算压缩、sleeve 拒单和人工干预在样本窗口中的分布。

#### Scenario: 可汇总统计主导原因
- **WHEN** 用户查看一次 A 股实验的归因结论
- **THEN** 系统 MUST 能按 reason code 汇总主导状态来源和预算来源
- **THEN** 系统 SHALL NOT 只提供难以聚合的自由文本日志
