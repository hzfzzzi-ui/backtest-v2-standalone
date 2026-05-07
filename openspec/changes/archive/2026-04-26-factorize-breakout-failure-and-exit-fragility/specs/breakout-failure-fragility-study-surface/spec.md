## ADDED Requirements

### Requirement: Breakout Failure / Exit Fragility Study Surface
系统 MUST 提供 `RESEARCH_ONLY` 的 breakout failure / exit fragility study surface，使研究者可以通过 `study_run` 直接分析失败风险与脆弱性上下文。

#### Scenario: Study runner executes breakout failure / exit fragility surface
- **WHEN** 研究者通过 `.study.yaml` 调用 breakout failure / exit fragility study surface
- **THEN** study runner MUST 生成 machine/human outputs
- **AND** 输出 MUST 区分失败风险研究与一般排序研究
- **AND** 输出 MUST 明确标记此能力为 `RESEARCH_ONLY`
