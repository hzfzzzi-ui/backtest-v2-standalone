## MODIFIED Requirements

### Requirement: Attribution audit 必须覆盖状态、预算、sleeve 与人工干预
`attribution_audit` MUST 将 A 股系统的 regime、Governor、sleeve 与人工干预统一组织成可审计证据链。

它至少 MUST 覆盖：

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
- **THEN** 归因日志 MUST 能同时回答“模型原始状态是什么”与“最终生效状态是什么”

#### Scenario: 归因日志记录人工干预
- **WHEN** 某交易日存在 manual override
- **THEN** 归因日志 MUST 记录 override 的原因、范围和生效对象
