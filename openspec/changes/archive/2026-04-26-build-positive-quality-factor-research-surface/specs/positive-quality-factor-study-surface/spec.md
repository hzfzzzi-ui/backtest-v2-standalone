## ADDED Requirements

### Requirement: positive quality factor study surface
系统 SHALL 提供独立的正向质量因子研究入口，并能在三窗口合同下运行真实样例。

#### Scenario: study runner executes positive quality surface
- **WHEN** 用户通过 `study_run` 执行 positive quality real study
- **THEN** 系统 SHALL 输出 machine/human bundle
- **THEN** 输出 MUST 标记 `RESEARCH_ONLY`
- **THEN** 研究运行 MUST 不改变正式主线 runtime 行为
