## ADDED Requirements

### Requirement: research_audit 必须解释宽基 ETF 暴露政策如何生效
当实验属于宽基 ETF governed exposure policy 研究时，`research_audit` MUST 能解释该实验的目标暴露、实际暴露、分层承接与 fallback 使用情况。

#### Scenario: audit 能回答为什么今天不是满目标暴露
- **WHEN** 用户查看宽基 ETF 暴露政策研究的 `research_audit`
- **THEN** 审计结果 MUST 能说明当日 `target_exposure` 与 `actual_exposure` 是否存在差距
- **THEN** 审计结果 MUST 能通过 `under_deploy_reason_codes` 或等价字段解释差距原因

#### Scenario: audit 能回答是否触发分层承接
- **WHEN** 宽基 ETF sleeve 在 `LIGHT` 或 `TRANS_DOWN` 中保留或增加宽基 beta
- **THEN** 审计结果 MUST 暴露 `layering_band`、`fallback_usage` 或等价证据
- **THEN** 审计结果 SHALL NOT 只给 perf 指标而不解释暴露过程
