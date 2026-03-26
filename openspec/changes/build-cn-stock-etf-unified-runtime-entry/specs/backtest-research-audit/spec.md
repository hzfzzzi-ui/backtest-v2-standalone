## ADDED Requirements

### Requirement: research audit 必须审计 unified runtime 的组合级与 sleeve 级一致性
当实验属于 `cn-stock-etf-unified-runtime-entry` 时，`research_audit` MUST 同时审计组合级结果与 sleeve 级结果，并能回答该实验是否真实同时包含股票 alpha 与 ETF beta 两条子腿。系统 SHALL NOT 因组合级结果存在，就默认认为 unified runtime 已经正确运行。

#### Scenario: 统一运行实验包含两条 sleeve
- **WHEN** unified runtime 实验完成并生成 `audit.json`
- **THEN** `research_audit` MUST 能证明股票 alpha sleeve 与 ETF beta sleeve 均已进入该实验
- **THEN** `research_audit` MUST 暴露至少一个组合级 gate 和一个 sleeve 完整性 gate

#### Scenario: 某条 sleeve 被静默跳过
- **WHEN** unified runtime 实验只实际运行了一条 sleeve 或某条 sleeve 被静默禁用
- **THEN** `research_audit` SHALL NOT 给出完整通过结论
- **THEN** 审计结果 MUST 说明是哪条 sleeve 缺失以及缺失原因
