## ADDED Requirements

### Requirement: moneyflow factor study surface
系统 SHALL 提供基于 `study_run` 的 moneyflow factor 单因子/组合因子研究入口。该入口 MUST 以 snapshot 为正式分析对象，并输出 machine/human 研究产物。

#### Scenario: run moneyflow factor study
- **WHEN** 用户运行 moneyflow factor study
- **THEN** 系统 MUST 输出 factor catalog、factor snapshot、factor score snapshot 和 analysis
- **THEN** verdict MUST 标记为 `RESEARCH_ONLY`
