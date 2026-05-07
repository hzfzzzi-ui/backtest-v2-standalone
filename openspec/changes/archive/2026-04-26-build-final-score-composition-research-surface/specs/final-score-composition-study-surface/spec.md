## ADDED Requirements

### Requirement: Final Score Composition Study Surface
系统 MUST 提供 `RESEARCH_ONLY` 的 final score composition study surface，使研究者可以通过 `study_run` 直接分析 `_final_score` 组成项和总分。

#### Scenario: Study runner executes final score composition surface
- **WHEN** 研究者通过 `.study.yaml` 调用 final score composition study surface
- **THEN** study runner MUST 生成 machine/human outputs
- **AND** 输出 MUST 区分原子组成项研究与组合分研究
- **AND** 输出 MUST 明确标记此能力为 `RESEARCH_ONLY`
