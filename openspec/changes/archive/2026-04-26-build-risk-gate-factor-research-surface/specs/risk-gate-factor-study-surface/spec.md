## ADDED Requirements

### Requirement: risk gate factor study surface
系统 SHALL 提供基于 `study_run` 的 risk gate factor 单因子/组合因子研究入口。该入口 MUST 以 snapshot 为正式分析对象，并输出 machine/human 研究产物。研究默认 MUST 支持 veto/context 导向分析，而不是预设为正向 rank 因子。

#### Scenario: run risk gate factor study
- **WHEN** 用户运行 risk gate factor study
- **THEN** 系统 MUST 输出 factor catalog、factor snapshot、factor score snapshot 和 analysis
- **THEN** verdict MUST 标记为 `RESEARCH_ONLY`
- **THEN** analysis SHOULD 能区分 veto/context 方向与 rank 方向
