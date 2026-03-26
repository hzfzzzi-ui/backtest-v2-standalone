## ADDED Requirements

### Requirement: research audit 必须引用 canonical ETF contract truth
当实验属于 `cn_etf` 或包含 ETF sleeve 时，`research_audit` MUST 引用 canonical ETF contract truth，而不是直接从 provider diagnostics、front-end snapshot 或其他中间层字段重复投影 ETF 语义。

#### Scenario: ETF 实验生成 research audit
- **WHEN** 系统为 ETF 实验生成 `research_audit`
- **THEN** ETF sleeve 相关 evidence MUST 来自 canonical ETF contract projection
- **THEN** audit SHALL NOT 直接把 raw diagnostics 当成正式 ETF 真相

### Requirement: research audit 必须引用 canonical combo truth
当实验属于 research combo 或只读组合锚点时，`research_audit` MUST 引用后端 canonical combo truth，而不是把组件实验结果在 audit 层再次拼接成组合结论。

#### Scenario: combo 结果进入 audit
- **WHEN** 系统为 research combo 结果生成或更新 `research_audit`
- **THEN** combo 结论 MUST 来自后端 canonical combo truth
- **THEN** audit SHALL NOT 各自维护另一套组合摘要拼装逻辑
